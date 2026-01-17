import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, base64, time, random, re, html
from datetime import datetime
from docx import Document
from docx.shared import Pt
from supabase import create_client

# ==========================================
# 1) CONFIG
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- THEME (xohlasangiz o'zgartiring) ---
THEME = "DARK_GOLD"  # "DARK_GOLD" | "PARCHMENT" | "MIDNIGHT"
THEMES = {
    "DARK_GOLD": {
        "app_bg": "#0b1220",
        "sidebar_bg": "#0c1421",
        "text": "#e9eefb",
        "muted": "#b9c2d4",
        "gold": "#c5a059",
        "card": "#ffffff",
        "card_text": "#111827",
    },
    "PARCHMENT": {
        "app_bg": "#f4ecd8",
        "sidebar_bg": "#0c1421",
        "text": "#0c1421",
        "muted": "#3b4252",
        "gold": "#b98a2c",
        "card": "#ffffff",
        "card_text": "#111827",
    },
    "MIDNIGHT": {
        "app_bg": "#070b16",
        "sidebar_bg": "#0b1020",
        "text": "#e6ecff",
        "muted": "#aab6d6",
        "gold": "#5aa6ff",
        "card": "#ffffff",
        "card_text": "#111827",
    },
}
C = THEMES.get(THEME, THEMES["DARK_GOLD"])

# ==========================================
# 2) CSS FIXES (contrast + no white gap + scrollable result + sticky image)
# ==========================================
st.markdown(f"""
<style>
:root {{
  --app-bg: {C["app_bg"]};
  --sidebar-bg: {C["sidebar_bg"]};
  --text: {C["text"]};
  --muted: {C["muted"]};
  --gold: {C["gold"]};
  --card: {C["card"]};
  --card-text: {C["card_text"]};
}}

/* White gap fix */
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

/* Sidebar */
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

/* Headings */
h1, h2, h3, h4 {{
  color: var(--gold) !important;
  font-family: 'Georgia', serif;
  border-bottom: 2px solid var(--gold) !important;
  padding-bottom: 8px !important;
  text-align: center !important;
  text-shadow: 0 1px 1px rgba(0,0,0,0.35);
}}
.stMarkdown p {{ color: var(--muted) !important; }}

/* Buttons */
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

/* Inputs */
.stTextInput input, .stSelectbox select {{
  background-color: rgba(255,255,255,0.06) !important;
  color: var(--text) !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}
/* Editor: always readable (light bg + black text) */
.stTextArea textarea {{
  background-color: #fdfaf1 !important;
  color: #000000 !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}

/* Result card: scroll only here, not whole page */
.result-box {{
  background-color: var(--card) !important;
  padding: 18px !important;
  border-radius: 16px !important;
  border-left: 10px solid var(--gold) !important;
  box-shadow: 0 10px 30px rgba(0,0,0,0.18) !important;
  color: var(--card-text) !important;
  font-size: 16px;
  line-height: 1.75;

  max-height: 520px;
  overflow-y: auto;
  white-space: pre-wrap; /* NEWLINES + spaces */
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

.chat-user {{
  background-color: #e2e8f0; color: #000; padding: 10px; border-radius: 10px;
  border-left: 5px solid #1e3a8a; margin-bottom: 6px;
}}
.chat-ai {{
  background-color: #ffffff; color: #1a1a1a; padding: 10px; border-radius: 10px;
  border: 1px solid #d4af37; margin-bottom: 14px;
}}

/* Sticky image: never stretch */
.sticky-preview {{
  position: sticky;
  top: 4.6rem;
  border-radius: 14px;
  border: 2px solid var(--gold);
  overflow: hidden;
  box-shadow: 0 14px 35px rgba(0,0,0,0.22);
  background: rgba(0,0,0,0.15);

  max-height: 520px;
}}
.sticky-preview img {{
  width: 100%;
  height: 520px;
  object-fit: contain; /* NO STRETCH */
  display: block;
  transition: transform .25s ease;
}}
.sticky-preview:hover img {{
  transform: scale(1.6);
  transform-origin: center;
  cursor: zoom-in;
}}

@media (max-width: 768px) {{
  div[data-testid="stAppViewContainer"] .main .block-container {{
    padding-top: 3.5rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }}
  .result-box {{ max-height: 58vh; }}
  .sticky-preview {{ position: relative; top: 0; max-height: 48vh; }}
  .sticky-preview img {{ height: 48vh; }}
}}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3) SERVICES
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

# ✅ MODELNI O'ZGARTIRMAYMIZ
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(model_name="gemini-flash-latest")

# ==========================================
# 4) STATE
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = "Mehmon"
if "last_fn" not in st.session_state: st.session_state.last_fn = None

# store rendered pages as JPEG bytes to be cache-safe
if "page_bytes" not in st.session_state: st.session_state.page_bytes = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}

# once-per-run warnings
if "warn_rpc" not in st.session_state: st.session_state.warn_rpc = False

# ==========================================
# 5) HELPERS (cache-safe bytes)
# ==========================================
def pil_to_jpeg_bytes(img: Image.Image, quality: int = 88, max_side: int = 2400) -> bytes:
    img = img.convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > max_side:
        ratio = max_side / float(long_side)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

@st.cache_data(show_spinner=False, max_entries=12)
def render_pdf_pages_to_bytes(file_bytes: bytes, max_pages: int, scale: float) -> list[bytes]:
    pdf = pdfium.PdfDocument(file_bytes)
    out: list[bytes] = []
    try:
        n = min(len(pdf), max_pages)
        for i in range(n):
            pil_img = pdf[i].render(scale=scale).to_pil()
            out.append(pil_to_jpeg_bytes(pil_img, quality=86, max_side=2600))
    finally:
        try:
            pdf.close()
        except Exception:
            pass
    return out

@st.cache_data(show_spinner=False, max_entries=48)
def preprocess_bytes(img_bytes: bytes, brightness: float, contrast: float, rotate: int) -> bytes:
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageOps.exif_transpose(img)
    if rotate:
        img = img.rotate(rotate, expand=True)
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    return pil_to_jpeg_bytes(img, quality=90, max_side=2400)

def parse_pages(spec: str, max_n: int) -> list[int]:
    """
    '1-5, 9, 12-20' -> [0..4, 8, 11..19]
    Invalid tokens ignored safely.
    """
    spec = (spec or "").strip()
    if not spec:
        return [0] if max_n > 0 else []
    out = set()
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for part in parts:
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                a = int(a.strip()); b = int(b.strip())
                if a > b: a, b = b, a
                for p in range(a, b + 1):
                    if 1 <= p <= max_n:
                        out.add(p - 1)
            else:
                p = int(part)
                if 1 <= p <= max_n:
                    out.add(p - 1)
        except Exception:
            continue
    return sorted(out) if out else ([0] if max_n > 0 else [])

def call_gemini_with_retry(prompt: str, payload: dict, tries: int = 4) -> str:
    """
    429/rate-limit bo'lsa backoff qiladi.
    Boshqa xatolarni yashirmaydi.
    """
    last_err = None
    for i in range(tries):
        try:
            resp = model.generate_content([prompt, payload])
            return getattr(resp, "text", "") or ""
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if ("429" in msg) or ("rate" in msg) or ("resource" in msg) or ("quota" in msg):
                time.sleep((2 ** i) + random.random())
                continue
            raise
    raise RuntimeError("Juda ko'p so'rov (429). Birozdan keyin qayta urinib ko'ring.") from last_err

def consume_credit(email: str) -> None:
    """
    Eng to'g'ri yechim: db.rpc('consume_credits', ...) bo'lsa ishlatadi.
    Bo'lmasa fallback: select -> update (race-proof emas).
    """
    try:
        db.rpc("consume_credits", {"p_email": email, "p_n": 1}).execute()
        return
    except Exception:
        # fallback
        try:
            res = db.table("profiles").select("credits").eq("email", email).single().execute()
            live = int(res.data["credits"]) if res.data else 0
        except Exception:
            live = 0
        try:
            db.table("profiles").update({"credits": max(live - 1, 0)}).eq("email", email).execute()
        except Exception:
            pass
        st.session_state.warn_rpc = True

def build_word_report(app_name: str, meta: dict, pages: dict[int, str]) -> bytes:
    doc = Document()

    # Global font (world-standard)
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    doc.add_heading(app_name, level=1)
    doc.add_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Meta table
    t = doc.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    for k, v in meta.items():
        row = t.add_row().cells
        row[0].text = str(k)
        row[1].text = str(v)

    doc.add_paragraph("")

    for idx in sorted(pages.keys()):
        doc.add_heading(f"Varaq {idx+1}", level=2)
        text = pages[idx] or ""
        for line in text.splitlines():
            doc.add_paragraph(line)
        # page break between pages (except last)
        if idx != sorted(pages.keys())[-1]:
            doc.add_page_break()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

# ==========================================
# 6) SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)

    if not st.session_state.auth:
        st.markdown("### 🔑 Tizimga kirish")
        st.caption("Kreditlardan foydalanish uchun kiring.")
        email_in = st.text_input("Email", placeholder="example@mail.com")
        pwd_in = st.text_input("Parol", type="password", placeholder="****")
        if st.button("KIRISH"):
            if pwd_in == st.secrets["APP_PASSWORD"]:
                st.session_state.auth = True
                st.session_state.u_email = (email_in or "demo@mail.com").strip()
                st.rerun()
            else:
                st.error("Xato!")
    else:
        st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
        try:
            res = db.table("profiles").select("credits").eq("email", st.session_state.u_email).single().execute()
            live_credits = res.data["credits"] if res.data else 0
        except:
            live_credits = 0
        st.metric("💳 Kreditlar", f"{live_credits} sahifa")

        if st.session_state.warn_rpc:
            st.warning("Eslatma: consume_credits() RPC topilmadi. Kredit yechish fallback rejimda (race-proof emas).")

        if st.button("🚪 TIZIMDAN CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = "Mehmon"
            st.rerun()

    st.divider()
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])

    st.markdown("### 🧪 Laboratoriya")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)
    scale = st.slider("PDF render scale:", 1.5, 3.8, 2.2, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 60, 30)

    st.markdown("### 🧭 Ko'rinish")
    view_mode = st.radio("Natija ko'rinishi:", ["Yonma-yon", "Tabs"], index=0, horizontal=True)

# ==========================================
# 7) MAIN
# ==========================================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qadimiy hujjatlarni yuklang va AI yordamida tahlil qiling.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Faylni yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

if uploaded_file:
    # load new file
    if st.session_state.last_fn != uploaded_file.name:
        with st.spinner("Preparing..."):
            file_bytes = uploaded_file.getvalue()
            pages = []
            if uploaded_file.type == "application/pdf":
                pages = render_pdf_pages_to_bytes(file_bytes, max_pages=max_pages, scale=scale)
            else:
                img = Image.open(io.BytesIO(file_bytes))
                pages = [pil_to_jpeg_bytes(img, quality=90, max_side=2600)]

            st.session_state.page_bytes = pages
            st.session_state.last_fn = uploaded_file.name
            st.session_state.results = {}
            st.session_state.chats = {}
            gc.collect()

    # preprocess all preview pages (cached)
    processed_pages = [preprocess_bytes(b, brightness=brightness, contrast=contrast, rotate=rotate) for b in st.session_state.page_bytes]

    # PAGE SELECTION UX
    total_pages = len(processed_pages)
    st.caption(f"Yuklandi: **{total_pages}** sahifa (preview limit: {max_pages}).")

    if total_pages <= 30:
        selected_indices = st.multiselect(
            "Sahifalarni tanlang:",
            options=list(range(total_pages)),
            default=[0] if total_pages else [],
            format_func=lambda x: f"{x+1}-sahifa"
        )
        st.caption("Ko'p sahifali kitoblar uchun: pastdagi 'Range' inputdan foydalaning.")
        page_spec = st.text_input("Range (masalan: 1-3, 7, 10-12):", value="1")
        selected_by_range = parse_pages(page_spec, total_pages)
        if st.button("Range bo'yicha tanlash"):
            selected_indices = selected_by_range
            st.session_state["_tmp_selected"] = selected_indices
    else:
        page_spec = st.text_input("Sahifalar (masalan: 1-5, 9, 12-20):", value="1")
        selected_indices = parse_pages(page_spec, total_pages)
        st.caption("Maslahat: juda ko'p sahifani biryo'la yubormang (429 kamayadi).")

    # Keep selection stable if button used
    if "_tmp_selected" in st.session_state:
        selected_indices = st.session_state.pop("_tmp_selected")

    # Preview thumbnails (before analysis)
    if not st.session_state.results and selected_indices:
        cols = st.columns(min(len(selected_indices), 4))
        for i, idx in enumerate(selected_indices[:16]):  # avoid huge grids
            with cols[i % min(len(cols), 4)]:
                st.image(processed_pages[idx], caption=f"Varaq {idx+1}", use_container_width=True)
        if len(selected_indices) > 16:
            st.info(f"Previewda faqat 16 ta ko'rsatildi. Tanlangan jami: {len(selected_indices)}.")

    # ANALYZE
    if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
        prompt = (
            f"Siz Manuscript AI mutaxassisiz. {lang} va {era} uslubidagi manbani tahlil qiling:\n"
            "1) Paleografiya\n2) Transliteratsiya (satrma-satr)\n3) Tarjima (akademik)\n4) Arxaik lug'at\n5) Izoh\n\n"
            "Qoidalar: O‘qilmagan joyni taxmin qilmang, [o‘qilmadi] yoki [?] bilan belgilang. Ism/son/sana bo‘lsa aynan ko‘ringanicha yozing."
        )

        for idx in selected_indices:
            with st.status(f"Sahifa {idx+1}...") as s:
                try:
                    img_bytes = processed_pages[idx]
                    payload = {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}
                    text = call_gemini_with_retry(prompt, payload, tries=4)
                    st.session_state.results[idx] = text

                    if st.session_state.auth:
                        consume_credit(st.session_state.u_email)

                    s.update(label="Tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato: {e}")

        gc.collect()
        st.rerun()

    # RESULTS
    if st.session_state.results:
        st.divider()

        for idx in sorted(st.session_state.results.keys()):
            with st.expander(f"📖 Varaq {idx+1}", expanded=(idx == sorted(st.session_state.results.keys())[0])):
                res = st.session_state.results[idx]
                safe_res = html.escape(res or "")

                img_b64 = base64.b64encode(processed_pages[idx]).decode("utf-8")
                img_html = f"""
                <div class="sticky-preview">
                    <img src="data:image/jpeg;base64,{img_b64}" alt="page {idx+1}" />
                </div>
                """

                if view_mode == "Tabs":
                    tabs = st.tabs(["📷 Rasm", "📝 Natija", "✍️ Tahrir", "💬 Chat"])
                    with tabs[0]:
                        st.markdown(img_html, unsafe_allow_html=True)

                    with tabs[1]:
                        st.markdown(f"<div class='result-box'>{safe_res}</div>", unsafe_allow_html=True)

                    with tabs[2]:
                        if not st.session_state.auth:
                            st.markdown("<div class='premium-alert'>🔒 Tahrir/Word/Chat uchun tizimga kiring!</div>", unsafe_allow_html=True)
                        else:
                            st.session_state.results[idx] = st.text_area(
                                f"Tahrir ({idx+1}):",
                                value=st.session_state.results[idx],
                                height=260,
                                key=f"ed_{idx}"
                            )

                    with tabs[3]:
                        if not st.session_state.auth:
                            st.markdown("<div class='premium-alert'>🔒 Chat uchun tizimga kiring!</div>", unsafe_allow_html=True)
                        else:
                            st.session_state.chats.setdefault(idx, [])
                            for ch in st.session_state.chats[idx]:
                                st.markdown(f"<div class='chat-user'><b>S:</b> {html.escape(ch['q'])}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='chat-ai'><b>AI:</b> {html.escape(ch['a'])}</div>", unsafe_allow_html=True)

                            user_q = st.text_input("Savol bering:", key=f"q_{idx}")
                            if st.button(f"So'rash ({idx+1})", key=f"btn_{idx}"):
                                if user_q.strip():
                                    with st.spinner("..."):
                                        chat_prompt = f"Doc: {st.session_state.results[idx]}\nQ: {user_q}"
                                        chat_resp = model.generate_content([chat_prompt])
                                        st.session_state.chats[idx].append({"q": user_q, "a": getattr(chat_resp, "text", "") or ""})
                                        st.rerun()

                else:
                    c1, c2 = st.columns([1, 1.35], gap="large")
                    with c1:
                        st.markdown(img_html, unsafe_allow_html=True)

                    with c2:
                        st.markdown(f"<div class='result-box'>{safe_res}</div>", unsafe_allow_html=True)

                        if not st.session_state.auth:
                            st.markdown("<div class='premium-alert'>🔒 Tahrir/Word/Chat uchun tizimga kiring!</div>", unsafe_allow_html=True)
                        else:
                            st.session_state.results[idx] = st.text_area(
                                f"Tahrir ({idx+1}):",
                                value=st.session_state.results[idx],
                                height=280,
                                key=f"ed_{idx}"
                            )

                            st.session_state.chats.setdefault(idx, [])
                            for ch in st.session_state.chats[idx]:
                                st.markdown(f"<div class='chat-user'><b>S:</b> {html.escape(ch['q'])}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='chat-ai'><b>AI:</b> {html.escape(ch['a'])}</div>", unsafe_allow_html=True)

                            user_q = st.text_input("Savol bering:", key=f"q_{idx}")
                            if st.button(f"So'rash ({idx+1})", key=f"btn_{idx}"):
                                if user_q.strip():
                                    with st.spinner("..."):
                                        chat_prompt = f"Doc: {st.session_state.results[idx]}\nQ: {user_q}"
                                        chat_resp = model.generate_content([chat_prompt])
                                        st.session_state.chats[idx].append({"q": user_q, "a": getattr(chat_resp, "text", "") or ""})
                                        st.rerun()

        # WORD EXPORT (single, clean build: no duplicates)
        if st.session_state.auth and st.session_state.results:
            meta = {
                "File": st.session_state.last_fn,
                "Language": lang,
                "Script": era,
                "Pages exported": ", ".join(str(i+1) for i in sorted(st.session_state.results.keys())),
                "Model": "gemini-flash-latest (legacy)",
            }
            report_bytes = build_word_report("Manuscript AI — Academic Report", meta, st.session_state.results)
            st.download_button("📥 DOWNLOAD REPORT (.docx)", report_bytes, file_name="Manuscript_AI_Report.docx")

gc.collect()

