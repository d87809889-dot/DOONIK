import io
import gc
import base64
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import streamlit as st
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
from docx import Document
from supabase import create_client

# New (recommended) Google GenAI SDK
from google import genai
from google.genai import types


# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MAX_PDF_PAGES_PREVIEW = 30
DEFAULT_SCALE = 2.2
MAX_IMAGE_LONG_SIDE = 2200  # keep request size reasonable
JPEG_QUALITY = 85


# =========================
# STYLE
# =========================
st.markdown(
    """
<style>
footer {visibility: hidden !important;}
.stAppDeployButton {display:none !important;}
#stDecoration {display:none !important;}

header[data-testid="stHeader"] { background: rgba(0,0,0,0) !important; visibility: visible !important; }
button[data-testid="stSidebarCollapseButton"] {
    background-color: #0c1421 !important;
    color: #c5a059 !important;
    border: 1px solid #c5a059 !important;
    border-radius: 8px !important;
}

.main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }

.result-box {
    background-color: #ffffff !important; padding: 18px !important; border-radius: 14px !important;
    border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 30px rgba(0,0,0,0.1) !important;
    color: #1a1a1a !important; font-size: 16px; line-height: 1.7;
}

.stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 1px solid #c5a059 !important; }
.chat-user { background-color: #e2e8f0; color: #000; padding: 10px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 6px; }
.chat-ai { background-color: #ffffff; color: #1a1a1a; padding: 10px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 14px; }

section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }

.stButton>button {
    background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
    color: #c5a059 !important; font-weight: bold !important; width: 100% !important;
    padding: 10px !important; border: 1px solid #c5a059;
}

.magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 10px; cursor: zoom-in; }
.magnifier-container img { transition: transform 0.3s ease; }
.magnifier-container:hover img { transform: scale(2.5); }

.premium-alert { background: #fff3e0; border: 1px solid #ffb74d; padding: 12px; border-radius: 10px;
    text-align: center; color: #e65100; font-weight: bold; margin-bottom: 14px; }
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# SERVICES
# =========================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_resource
def get_ai_client():
    # Recommended GenAI SDK client
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

db = get_db()
ai = get_ai_client()


def pick_best_model_id() -> str:
    """
    Pick a live model that supports generateContent.
    Preference order (fast + vision-friendly):
      gemini-3-flash-preview -> gemini-3-flash -> gemini-2.5-flash -> gemini-2.5-flash-lite -> gemini-2.0-flash
    """
    preferred = [
        "gemini-3-flash-preview",
        "gemini-3-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
    ]

    available = set()
    try:
        for m in ai.models.list():
            # pydantic object, fields may be snake_case
            base = getattr(m, "base_model_id", None) or getattr(m, "baseModelId", None)
            name = getattr(m, "name", None)
            supported = getattr(m, "supported_actions", None) or getattr(m, "supportedActions", None) or []
            if supported and "generateContent" not in supported:
                continue
            if base:
                available.add(base)
            if name and isinstance(name, str):
                # name looks like "models/gemini-1.5-flash-001" -> base "gemini-1.5-flash"
                s = name.replace("models/", "")
                if "-" in s:
                    # heuristic: chop version suffix
                    available.add("-".join(s.split("-")[:-1]))
    except Exception:
        # If listing fails, fallback to a commonly available id
        return "gemini-2.5-flash"

    for p in preferred:
        if p in available:
            return p

    # any available model is better than hard fail
    return next(iter(available)) if available else "gemini-2.5-flash"


MODEL_ID = pick_best_model_id()


# =========================
# AUTH STATE
# =========================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "u_email" not in st.session_state:
    st.session_state.u_email = "Mehmon"

if "imgs" not in st.session_state:
    st.session_state.imgs = []
if "results" not in st.session_state:
    st.session_state.results = {}
if "chats" not in st.session_state:
    st.session_state.chats = {}
if "last_fn" not in st.session_state:
    st.session_state.last_fn = None


# =========================
# DB HELPERS
# =========================
def ensure_profile(email: str, default_credits: int = 10) -> None:
    """Create profile row if missing (demo-friendly)."""
    try:
        res = db.table("profiles").select("email").eq("email", email).limit(1).execute()
        if not res.data:
            db.table("profiles").insert({"email": email, "credits": default_credits}).execute()
    except Exception:
        # Don't crash demo if DB policy blocks it
        pass

@st.cache_data(ttl=5)
def get_credits(email: str) -> int:
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return int(res.data["credits"]) if res.data and "credits" in res.data else 0
    except Exception:
        return 0

def consume_credit_atomic(email: str, n: int = 1) -> Tuple[bool, Optional[int], str]:
    """
    Best practice: use RPC function consume_credits(p_email, p_n) that does atomic UPDATE ... RETURNING.
    Returns (ok, new_credits, message).
    """
    try:
        out = db.rpc("consume_credits", {"p_email": email, "p_n": n}).execute()
        # can be int or dict depending on your SQL return
        if out.data is None:
            return True, None, "OK"
        if isinstance(out.data, int):
            return True, out.data, "OK"
        if isinstance(out.data, dict) and "credits" in out.data:
            return True, int(out.data["credits"]), "OK"
        if isinstance(out.data, list) and out.data and isinstance(out.data[0], dict) and "credits" in out.data[0]:
            return True, int(out.data[0]["credits"]), "OK"
        return True, None, "OK"
    except Exception:
        # Fallback (NOT race-safe): only for demo if RPC not installed
        current = get_credits(email)
        if current <= 0:
            return False, current, "Credits tugagan."
        try:
            db.table("profiles").update({"credits": current - n}).eq("email", email).execute()
            # invalidate cache
            get_credits.clear()
            return True, current - n, "OK"
        except Exception as e:
            return False, current, f"DB error: {e}"


# =========================
# IMAGE HELPERS
# =========================
def downscale_keep_aspect(img: Image.Image, max_long_side: int) -> Image.Image:
    w, h = img.size
    long_side = max(w, h)
    if long_side <= max_long_side:
        return img
    ratio = max_long_side / float(long_side)
    new_size = (int(w * ratio), int(h * ratio))
    return img.resize(new_size, Image.LANCZOS)

def pil_to_jpeg_bytes(img: Image.Image, quality: int = JPEG_QUALITY) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

@st.cache_data(show_spinner=False)
def render_pdf_pages(file_bytes: bytes, max_pages: int, scale: float) -> List[Image.Image]:
    pdf = pdfium.PdfDocument(file_bytes)
    imgs: List[Image.Image] = []
    try:
        count = min(len(pdf), max_pages)
        for i in range(count):
            page = pdf[i]
            pil_img = page.render(scale=scale).to_pil()
            imgs.append(pil_img)
    finally:
        try:
            pdf.close()
        except Exception:
            pass
    return imgs

@st.cache_data(show_spinner=False)
def preprocess_image(img: Image.Image, brightness: float, contrast: float, rotate_deg: int) -> Image.Image:
    # Fix EXIF rotation first
    img = ImageOps.exif_transpose(img)
    if rotate_deg:
        img = img.rotate(rotate_deg, expand=True)
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = downscale_keep_aspect(img, MAX_IMAGE_LONG_SIDE)
    return img


# =========================
# PROMPTS
# =========================
def build_prompt(lang: str, era: str, mode: str) -> str:
    # mode: "Diplomatik" or "Semantik"
    mode_rule = (
        "Diplomatik: matnni harfma-harf ko'chir, qisqartmalarni belgilab, ilmiy aniqlikni saqla."
        if mode == "Diplomatik"
        else "Semantik: ma'noni saqla, tushunarli akademik tarjima ber, badiiy ohangni yo'qotma."
    )
    return f"""
Siz Manuscript AI mutaxassisisiz. Vazifa: qadimiy qo'lyozma sahifasini akademik uslubda tahlil qilish.
Til: {lang}. Xat uslubi: {era}.
Rejim: {mode_rule}

Natijani quyidagi qat'iy bo'limlar bilan qaytar:
1) Paleografik tavsif (qisqa, aniq)
2) Transliteratsiya (satrma-satr, iloji boricha original imloni saqla)
3) Akademik tarjima (silliq, ammo ilmiy)
4) Arxaik lug'at (5–10 ta murakkab so'z, jadval ko'rinishida: So'z — Izoh)
5) Tarixiy izoh (kontekst, sanalar/ism/shahar bo'lsa alohida qayd et)
"""


def analysis_cache_key(image_bytes: bytes, prompt: str, model_id: str) -> str:
    h = hashlib.sha256()
    h.update(image_bytes)
    h.update(prompt.encode("utf-8"))
    h.update(model_id.encode("utf-8"))
    return h.hexdigest()


def run_analysis_one(image_bytes: bytes, prompt: str) -> str:
    part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    # prompt after image part is recommended for text-in-image tasks
    resp = ai.models.generate_content(
        model=MODEL_ID,
        contents=[part, prompt],
        config=types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=2048,
        ),
    )
    return resp.text or ""


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.caption(f"Model: `{MODEL_ID}`")

    if not st.session_state.auth:
        st.markdown("### 🔑 Tizimga kirish")
        email_in = st.text_input("Email", placeholder="example@mail.com")
        pwd_in = st.text_input("Parol", type="password", placeholder="****")

        if st.button("KIRISH"):
            if pwd_in == st.secrets["APP_PASSWORD"]:
                st.session_state.auth = True
                st.session_state.u_email = email_in.strip() or "demo@mail.com"
                ensure_profile(st.session_state.u_email)
                get_credits.clear()
                st.rerun()
            else:
                st.error("Xato parol!")
    else:
        st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
        live_credits = get_credits(st.session_state.u_email)
        st.metric("💳 Kreditlar", f"{live_credits} sahifa")

        if st.button("🚪 TIZIMDAN CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = "Mehmon"
            st.rerun()

    st.divider()
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    mode = st.radio("Tahlil rejimi:", ["Diplomatik", "Semantik"], horizontal=True)

    scale = st.slider("PDF render (DPI/scale):", 1.5, 3.5, float(DEFAULT_SCALE), 0.1)
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)
    max_pages = st.slider("PDF max sahifa (preview):", 1, 50, MAX_PDF_PAGES_PREVIEW)


# =========================
# MAIN
# =========================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qadimiy hujjatlarni yuklang va AI yordamida tahlil qiling.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Faylni yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

if uploaded_file:
    if st.session_state.last_fn != uploaded_file.name:
        with st.spinner("Preparing..."):
            file_bytes = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                imgs = render_pdf_pages(file_bytes, max_pages=max_pages, scale=scale)
            else:
                imgs = [Image.open(io.BytesIO(file_bytes))]
            st.session_state.imgs = imgs
            st.session_state.last_fn = uploaded_file.name
            st.session_state.results = {}
            st.session_state.chats = {}
            gc.collect()

    # preprocess
    processed_imgs = [
        preprocess_image(img, brightness=brightness, contrast=contrast, rotate_deg=int(rotate))
        for img in st.session_state.imgs
    ]

    st.caption(f"Yuklandi: **{len(processed_imgs)}** sahifa (preview limit: {max_pages}).")

    selected_indices = st.multiselect(
        "Sahifalarni tanlang:",
        options=list(range(len(processed_imgs))),
        default=[0],
        format_func=lambda x: f"{x+1}-sahifa",
    )

    if selected_indices and not st.session_state.results:
        cols = st.columns(min(len(selected_indices), 4))
        for i, idx in enumerate(selected_indices):
            with cols[i % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

    prompt = build_prompt(lang=lang, era=era, mode=mode)

    with st.form("analyze_form", clear_on_submit=False):
        run_btn = st.form_submit_button("✨ AKADEMIK TAHLILNI BOSHLASH")

    if run_btn:
        # credits gate for logged-in users
        if st.session_state.auth:
            live_credits = get_credits(st.session_state.u_email)
            need = len(selected_indices)
            if live_credits <= 0:
                st.error("Kredit tugagan. Iltimos, kredit qo'shing.")
                st.stop()

        for idx in selected_indices:
            with st.status(f"Sahifa {idx+1} tahlil qilinmoqda...") as s:
                try:
                    img_bytes = pil_to_jpeg_bytes(processed_imgs[idx])
                    key = analysis_cache_key(img_bytes, prompt, MODEL_ID)

                    if key in st.session_state.results:
                        s.update(label=f"Sahifa {idx+1}: cache'dan olindi", state="complete")
                        continue

                    # If logged-in, consume credit BEFORE heavy call (or after success — your choice).
                    # For demo stability, consume after success.
                    text = run_analysis_one(img_bytes, prompt)
                    st.session_state.results[idx] = text

                    if st.session_state.auth:
                        ok, newc, msg = consume_credit_atomic(st.session_state.u_email, n=1)
                        get_credits.clear()
                        if not ok:
                            st.warning(f"Kredit yechishda muammo: {msg}")

                    s.update(label=f"Sahifa {idx+1}: tayyor!", state="complete")

                except Exception as e:
                    st.error(f"Xato: {e}")

        gc.collect()
        st.rerun()

    # RESULTS
    if st.session_state.results:
        st.divider()
        final_doc_parts: List[Tuple[int, str]] = []

        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res = st.session_state.results[idx]

            c1, c2 = st.columns([1, 1.2])
            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with c2:
                st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)

                if not st.session_state.auth:
                    st.markdown(
                        "<div class='premium-alert'>🔒 Word hisobotni yuklab olish va AI Chat uchun tizimga kiring!</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    edited = st.text_area(f"Tahrir ({idx+1}):", value=res, height=320, key=f"ed_{idx}")
                    st.session_state.results[idx] = edited
                    final_doc_parts.append((idx + 1, edited))

                    # Page-specific chat
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai' style='color:black;'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                    user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                    if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                        if user_q.strip():
                            with st.spinner("Javob tayyorlanmoqda..."):
                                chat_prompt = (
                                    "Siz Manuscript AI mutaxassisisiz. Quyidagi tahrirlangan matn bo'yicha aniq va ilmiy javob bering.\n\n"
                                    f"MATN:\n{st.session_state.results[idx]}\n\nSAVOL: {user_q}"
                                )
                                chat_resp = ai.models.generate_content(
                                    model=MODEL_ID,
                                    contents=chat_prompt,
                                    config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=1024),
                                )
                                st.session_state.chats[idx].append({"q": user_q, "a": chat_resp.text or ""})
                                st.rerun()

            st.markdown("---")

        # EXPORT WORD
        if st.session_state.auth and final_doc_parts:
            doc = Document()
            doc.add_heading("Manuscript AI — Academic Report", level=1)
            doc.add_paragraph(f"Model: {MODEL_ID}")
            doc.add_paragraph(f"Til: {lang} | Xat uslubi: {era} | Rejim: {mode}")

            for page_no, text in final_doc_parts:
                doc.add_heading(f"Varaq {page_no}", level=2)
                for line in text.splitlines():
                    doc.add_paragraph(line)

            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 DOWNLOAD REPORT", bio.getvalue(), file_name="report.docx")

gc.collect()
