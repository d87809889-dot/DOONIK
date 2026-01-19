import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium

import io, gc, base64, time, random
from docx import Document
from supabase import create_client

# ==========================================
# 1. TIZIM SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================
# THEME
# =========================
THEME = "DARK_GOLD"  # "DARK_GOLD" | "PARCHMENT" | "MIDNIGHT"

THEMES = {
    "DARK_GOLD": {
        "app_bg": "#0b1220",
        "surface": "#111a2e",
        "sidebar_bg": "#0c1421",
        "text": "#e9eefb",
        "muted": "#b9c2d4",
        "gold": "#c5a059",
        "gold2": "#d4af37",
        "card": "#ffffff",
        "card_text": "#111827",
    },
    "PARCHMENT": {
        "app_bg": "#f4ecd8",
        "surface": "#fff7e6",
        "sidebar_bg": "#0c1421",
        "text": "#0c1421",
        "muted": "#3b4252",
        "gold": "#b98a2c",
        "gold2": "#c5a059",
        "card": "#ffffff",
        "card_text": "#111827",
    },
    "MIDNIGHT": {
        "app_bg": "#070b16",
        "surface": "#0e1630",
        "sidebar_bg": "#0b1020",
        "text": "#e6ecff",
        "muted": "#aab6d6",
        "gold": "#5aa6ff",
        "gold2": "#7cc4ff",
        "card": "#ffffff",
        "card_text": "#111827",
    },
}

C = THEMES.get(THEME, THEMES["DARK_GOLD"])

# ==========================================
# UI CSS
# ==========================================
st.markdown(f"""
<style>
:root {{
  --app-bg: {C["app_bg"]};
  --surface: {C["surface"]};
  --sidebar-bg: {C["sidebar_bg"]};
  --text: {C["text"]};
  --muted: {C["muted"]};
  --gold: {C["gold"]};
  --gold2: {C["gold2"]};
  --card: {C["card"]};
  --card-text: {C["card_text"]};
}}

html, body {{
  background: var(--app-bg) !important;
  margin: 0 !important;
  padding: 0 !important;
}}
.stApp, div[data-testid="stAppViewContainer"] {{
  background: var(--app-bg) !important;
  min-height: 100vh !important;
}}
div[data-testid="stAppViewContainer"] .main .block-container {{
  padding-top: 3.25rem !important;
  padding-bottom: 1.25rem !important;
}}

footer {{visibility: hidden !important;}}
.stAppDeployButton {{display:none !important;}}
#stDecoration {{display:none !important;}}
header[data-testid="stHeader"] {{ background: rgba(0,0,0,0) !important; }}

section[data-testid="stSidebar"] {{
  background: var(--sidebar-bg) !important;
  border-right: 2px solid var(--gold) !important;
}}
section[data-testid="stSidebar"] * {{
  color: var(--text) !important;
}}
section[data-testid="stSidebar"] .stCaption {{
  color: var(--muted) !important;
}}

h1, h2, h3, h4 {{
  color: var(--gold) !important;
  font-family: 'Georgia', serif;
  border-bottom: 2px solid var(--gold) !important;
  padding-bottom: 8px !important;
  text-align: center !important;
}}
.stMarkdown p {{
  color: var(--muted) !important;
}}

.stButton>button {{
  background: linear-gradient(135deg, var(--sidebar-bg) 0%, #1e3a8a 100%) !important;
  color: var(--gold) !important;
  font-weight: 800 !important;
  width: 100% !important;
  padding: 11px 12px !important;
  border: 1px solid var(--gold) !important;
  border-radius: 12px !important;
  box-shadow: 0 10px 22px rgba(0,0,0,0.25) !important;
}}
.stButton>button:hover {{
  transform: translateY(-1px);
  filter: brightness(1.05);
}}

.stTextInput input, .stSelectbox select, .stTextArea textarea {{
  background-color: rgba(255,255,255,0.06) !important;
  color: var(--text) !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}

.result-box {{
  background-color: var(--card) !important;
  padding: 20px !important;
  border-radius: 16px !important;
  border-left: 10px solid var(--gold) !important;
  box-shadow: 0 10px 30px rgba(0,0,0,0.18) !important;
  color: var(--card-text) !important;
  font-size: 16px;
  line-height: 1.75;
  white-space: pre-wrap;
}}

.premium-alert {{
  background: rgba(255,243,224,1);
  border: 1px solid #ffb74d;
  padding: 12px;
  border-radius: 12px;
  text-align: center;
  color: #e65100;
  font-weight: 800;
  margin-bottom: 12px;
}}

.sticky-preview {{
  position: sticky;
  top: 4.6rem;
  border-radius: 14px;
  border: 2px solid var(--gold);
  overflow: hidden;
  box-shadow: 0 14px 35px rgba(0,0,0,0.22);
  background: rgba(0,0,0,0.15);
}}
.sticky-preview img {{
  width: 100%;
  height: auto;
  display: block;
  transition: transform .25s ease;
}}
.sticky-preview:hover img {{
  transform: scale(2.05);
  transform-origin: center;
  cursor: zoom-in;
}}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2) CORE SERVICES
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(model_name="gemini-flash-latest")  # o'zgarmaydi

# ==========================================
# 3) SESSION STATE
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = "Mehmon"

if "imgs" not in st.session_state: st.session_state.imgs = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}
if "last_fn" not in st.session_state: st.session_state.last_fn = None

# ✅ Barqarorlik: tugma 2 marta ishlamasin
if "is_running" not in st.session_state:
    st.session_state.is_running = False

# ✅ Barqarorlik: rate-limitni yumshatish
def throttle(min_interval_sec: float = 2.2):
    last = st.session_state.get("_last_api_call_ts", 0.0)
    now = time.time()
    wait = (last + min_interval_sec) - now
    if wait > 0:
        time.sleep(wait)
    st.session_state["_last_api_call_ts"] = time.time()

def call_gemini_with_retry(prompt: str, payloads: list[dict], tries: int = 7) -> str:
    last_err = None
    for i in range(tries):
        try:
            throttle(2.2)  # ✅ majburiy interval
            resp = model.generate_content(
                [prompt, *payloads],
                generation_config={
                    "max_output_tokens": 1600,  # ✅ hozir: tarjima+izoh uchun yetarli va yengil
                    "temperature": 0.2,
                }
            )
            return getattr(resp, "text", "") or ""
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if ("429" in msg) or ("rate" in msg) or ("quota" in msg) or ("resource" in msg):
                sleep_s = min(25, (2 ** i)) + random.uniform(0.4, 1.2)
                time.sleep(sleep_s)
                continue
            raise
    raise RuntimeError("Gemini limit (429): kvota/rate limit. Keyinroq qayta urinib ko‘ring.") from last_err

def image_to_payload(img: Image.Image) -> dict:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode("utf-8")}

def safe_get_credits(email: str) -> int:
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return int(res.data["credits"]) if res.data and "credits" in res.data else 0
    except Exception:
        return 0

def safe_decrement_credit(email: str, n: int = 1) -> None:
    # Minimal va xavfsiz: avval o‘qiydi, keyin update qiladi (eski kodingizdagi usul).
    try:
        cur = safe_get_credits(email)
        db.table("profiles").update({"credits": max(cur - n, 0)}).eq("email", email).execute()
    except Exception:
        pass

# ==========================================
# 4) SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)

    if not st.session_state.auth:
        st.markdown("### 🔑 Tizimga kirish")
        st.caption("Kreditlaringizdan foydalanish uchun kiring.")
        email_in = st.text_input("Email", placeholder="example@mail.com")
        pwd_in = st.text_input("Parol", type="password", placeholder="****")
        if st.button("KIRISH"):
            if pwd_in == st.secrets.get("APP_PASSWORD", ""):
                st.session_state.auth = True
                st.session_state.u_email = (email_in or "").strip() or "Foydalanuvchi"
                st.rerun()
            else:
                st.error("Xato!")
    else:
        st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
        live_credits = safe_get_credits(st.session_state.u_email)
        st.metric("💳 Kreditlar", f"{live_credits} sahifa")
        if st.button("🚪 TIZIMDAN CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = "Mehmon"
            st.rerun()

    st.divider()
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)

# ==========================================
# 5) MAIN
# ==========================================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qadimiy hujjatlarni yuklang va AI yordamida tahlil qiling.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Faylni yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

if uploaded_file:
    # load/render once per file
    if st.session_state.last_fn != uploaded_file.name:
        with st.spinner("Preparing..."):
            file_bytes = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(file_bytes)
                for i in range(min(len(pdf), 20)):
                    imgs.append(pdf[i].render(scale=2.0).to_pil())
                try:
                    pdf.close()
                except Exception:
                    pass
            else:
                imgs.append(Image.open(io.BytesIO(file_bytes)))

            st.session_state.imgs = imgs
            st.session_state.last_fn = uploaded_file.name
            st.session_state.results = {}
            st.session_state.chats = {}
            gc.collect()

    # preprocess
    processed_imgs = []
    for img in st.session_state.imgs:
        img = ImageOps.exif_transpose(img)
        p_img = ImageEnhance.Brightness(img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    selected_indices = st.multiselect(
        "Sahifalarni tanlang:",
        options=range(len(processed_imgs)),
        default=[0] if processed_imgs else [],
        format_func=lambda x: f"{x+1}-sahifa"
    )

    # Preview
    if not st.session_state.results and selected_indices:
        cols = st.columns(min(len(selected_indices), 4))
        for i, idx in enumerate(selected_indices):
            with cols[i % min(len(cols), 4)]:
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", use_container_width=True)

    # ✅ Siz xohlagan qisqa prompt: faqat tarjima + izoh
    def build_prompt(_lang: str, _era: str) -> str:
        return (
            "Siz qadimiy qo‘lyozmalar bilan ishlovchi tarjimonsiz.\n"
            f"Hint: til={_lang}, xat uslubi={_era}.\n\n"
            "Vazifa: rasm matnini o‘qib, faqat quyidagi 2 bo‘limni yozing.\n"
            "Qoidalar: qisqartirmang; o‘qilmasa [o‘qilmadi] yoki [?] yozing; uydirma qilmang.\n\n"
            "FORMAT (aniq):\n"
            "1) To‘g‘ridan-to‘g‘ri tarjima (satrma-satr):\n"
            "2) Izoh (kontekst; aniq bo‘lmasa ehtiyot bo‘l):\n"
        )

    run = st.button("✨ AKADEMIK TAHLILNI BOSHLASH", disabled=st.session_state.is_running or (not selected_indices))
    if run:
        st.session_state.is_running = True
        try:
            prompt = build_prompt(lang, era)

            for idx in selected_indices:
                with st.status(f"Sahifa {idx+1}...") as s:
                    try:
                        payload = image_to_payload(processed_imgs[idx])
                        text = call_gemini_with_retry(prompt, [payload], tries=7)
                        st.session_state.results[idx] = text.strip() if text else "[Natija bo‘sh chiqdi]"

                        if st.session_state.auth:
                            safe_decrement_credit(st.session_state.u_email, 1)

                        s.update(label="Tayyor!", state="complete")
                    except Exception as e:
                        st.session_state.results[idx] = f"Xato: {e}"
                        s.update(label="Xato", state="error")
        finally:
            st.session_state.is_running = False
            gc.collect()
            st.rerun()

    # RESULTS
    if st.session_state.results:
        st.divider()
        final_doc = ""

        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res = st.session_state.results[idx]

            c1, c2 = st.columns([1, 1.35], gap="large")

            with c1:
                b64_payload = image_to_payload(processed_imgs[idx])["data"]
                st.markdown(
                    f"""
                    <div class="sticky-preview">
                        <img src="data:image/jpeg;base64,{b64_payload}" alt="page {idx+1}" />
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with c2:
                st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)

                if not st.session_state.auth:
                    st.markdown(
                        "<div class='premium-alert'>🔒 Word hisobot va AI Chat uchun tizimga kiring!</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.session_state.results[idx] = st.text_area(
                        f"Tahrir ({idx+1}):",
                        value=st.session_state.results[idx],
                        height=320,
                        key=f"ed_{idx}"
                    )
                    final_doc += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}"

                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai' style='color:black;'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                    user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                    if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                        if user_q:
                            with st.spinner("..."):
                                chat_text = call_gemini_with_retry(
                                    f"Matn:\n{st.session_state.results[idx]}\n\nSavol: {user_q}\nJavobni o‘zbekcha, qisqa va aniq yoz.",
                                    [],
                                    tries=6
                                )
                                st.session_state.chats[idx].append({"q": user_q, "a": chat_text})
                                st.rerun()

            st.markdown("---")

        # Word export (faqat auth)
        if st.session_state.auth and final_doc.strip():
            doc = Document()
            doc.add_paragraph(final_doc)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 DOWNLOAD REPORT", bio.getvalue(), "report.docx")

gc.collect()
