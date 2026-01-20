import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium
import io, gc, time, base64, re, html, threading
from collections import deque
from docx import Document
from supabase import create_client

# ==========================================
# 1) CONFIG
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Enterprise Pro 2026",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden !important;}
.main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }
.result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; font-size: 17px; white-space: pre-wrap; }
.stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
.chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; margin-bottom: 5px; white-space: pre-wrap; }
.chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; white-space: pre-wrap; }
section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; color: white !important; }
.stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; width: 100%; padding: 10px; border: 1px solid #c5a059; border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2) SECRETS + AUTH
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("Secrets sozlanmagan! (APP_PASSWORD / GEMINI_API_KEY / SUPABASE_URL / SUPABASE_KEY)")
    st.stop()

db = None
try:
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    db = None

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingiz")
        pwd_in = st.text_input("Maxfiy parol", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD and email_in.strip():
                st.session_state.auth, st.session_state.u_email = True, email_in.strip().lower()
                st.rerun()
            else:
                st.error("Email yoki parol xato!")
    st.stop()

# ==========================================
# 3) GEMINI (LOCKED MODEL)
# ==========================================
MODEL_NAME = "gemini-flash-latest"  # ✅ FAQAT SHU

genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def get_model():
    return genai.GenerativeModel(model_name=MODEL_NAME)

model = get_model()

# ==========================================
# 4) SAFE RATE LIMITER (429 ni kamaytirish)
# ==========================================
SAFE_RPM = 8          # 15 RPM bo'lsa ham 8 xavfsiz (demo uchun barqaror)
WINDOW_SEC = 60
MAX_RETRIES = 7

class RateLimiter:
    def __init__(self, rpm: int, window_sec: int = 60):
        self.rpm = max(1, int(rpm))
        self.window = int(window_sec)
        self.lock = threading.Lock()
        self.ts = deque()

    def wait_slot(self):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.ts and (now - self.ts[0]) > self.window:
                    self.ts.popleft()
                if len(self.ts) < self.rpm:
                    self.ts.append(now)
                    return
                sleep_for = (self.window - (now - self.ts[0])) + 0.2
            time.sleep(max(0.4, sleep_for))

@st.cache_resource
def get_limiter():
    return RateLimiter(SAFE_RPM, WINDOW_SEC)

limiter = get_limiter()

def _retry_delay_seconds(err: str) -> int:
    if not err:
        return 0
    m = re.search(r"retry_delay\s*{[^}]*seconds\s*:\s*(\d+)", err, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    m2 = re.search(r"retry\s+in\s+(\d+)", err, flags=re.IGNORECASE)
    if m2:
        return int(m2.group(1))
    return 0

def gemini_call(parts, max_output_tokens=4096):
    last = None
    for attempt in range(MAX_RETRIES):
        try:
            limiter.wait_slot()
            resp = model.generate_content(
                parts,
                generation_config={"max_output_tokens": max_output_tokens, "temperature": 0.2}
            )
            return getattr(resp, "text", "") or ""
        except Exception as e:
            last = str(e)
            low = last.lower()
            if ("429" in low) or ("quota" in low) or ("rate" in low):
                d = _retry_delay_seconds(last)
                if d <= 0:
                    d = min(60, 6 + attempt * 8)
                time.sleep(d + 0.5)
                continue
            return f"Xato: {type(e).__name__}: {e}"
    return f"Xato: 429/quota. Oxirgi xabar: {last}"

# ==========================================
# 5) HELPERS (IMG/PDF)
# ==========================================
def fetch_live_credits(email: str) -> int:
    if db is None:
        return 0
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return int(res.data["credits"]) if res.data and "credits" in res.data else 0
    except Exception:
        return 0

@st.cache_data(show_spinner=False, max_entries=64)
def render_pdf_page(pdf_bytes: bytes, page_idx: int, scale: float) -> Image.Image:
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        return pdf[page_idx].render(scale=scale).to_pil()
    finally:
        try: pdf.close()
        except Exception: pass

def img_to_payload(img: Image.Image, max_side: int = 2100, quality: int = 85):
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > max_side:
        ratio = max_side / float(long_side)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode("utf-8")}

def build_prompt(lang: str, era: str) -> str:
    return (
        "Siz qo‘lyozma o‘qish va tarjima bo‘yicha mutaxassissiz.\n"
        f"Til taxmini: {lang}. Xat uslubi: {era}.\n\n"
        "Qoidalar:\n"
        "- Hech narsa uydirmang.\n"
        "- Bironta so‘zni tashlab ketmang.\n"
        "- O‘qilmagan joyga: [o‘qilmadi] yoki [?] yozing.\n"
        "- Natijani qisqartirmang.\n\n"
        "FORMAT (aniq shunday):\n"
        "1) Transliteratsiya:\n<matn satrma-satr>\n\n"
        "2) To‘g‘ridan-to‘g‘ri tarjima:\n<zamonaviy o‘zbekcha, to‘liq>\n\n"
        "3) Izoh:\n<tarixiy/kontekst izoh; noaniq joylarni ehtiyotkor izohlang>\n"
    )

# ==========================================
# 6) UI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **User:** `{st.session_state.u_email}`")
    st.write(f"🤖 **Model:** `{MODEL_NAME}`")
    st.metric("💳 Credits", fetch_live_credits(st.session_state.u_email))

    st.divider()
    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])

    st.divider()
    pdf_scale = st.slider("PDF render scale:", 1.6, 3.0, 2.1, 0.1)
    contrast = st.slider("Kontrast:", 0.7, 2.5, 1.4, 0.05)
    sharpen = st.checkbox("Sharpen", value=True)

    if st.button("🚪 LOGOUT"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Markazi")
file = st.file_uploader("Faylni yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if "imgs" not in st.session_state: st.session_state.imgs = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}
if "last_fn" not in st.session_state: st.session_state.last_fn = None

if file:
    data = file.getvalue()

    # fayl yangilansa qayta tayyorlaymiz
    if st.session_state.last_fn != file.name:
        with st.spinner("Preparing..."):
            st.session_state.last_fn = file.name
            st.session_state.results = {}
            st.session_state.chats = {}

            imgs = []
            if file.type == "application/pdf":
                pdf = pdfium.PdfDocument(data)
                try:
                    n = min(len(pdf), 15)  # demo: 15 bet
                finally:
                    try: pdf.close()
                    except Exception: pass

                for i in range(n):
                    imgs.append(render_pdf_page(data, i, pdf_scale))
            else:
                imgs.append(Image.open(io.BytesIO(data)).convert("RGB"))

            st.session_state.imgs = imgs
            gc.collect()

    # preview
    if not st.session_state.results and st.session_state.imgs:
        cols = st.columns(min(len(st.session_state.imgs), 4))
        for idx, img in enumerate(st.session_state.imgs):
            cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    # run
    if st.button("✨ TAHLILNI BOSHLASH"):
        prompt = build_prompt(lang, era)

        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"{i+1}-sahifa tahlil qilinmoqda...") as s:
                try:
                    # preprocess
                    im = ImageEnhance.Contrast(img).enhance(contrast)
                    if sharpen:
                        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=2))

                    payload = img_to_payload(im)
                    text = gemini_call([prompt, payload])

                    st.session_state.results[i] = text

                    if text.lower().startswith("xato: 429") or "quota" in text.lower():
                        s.update(label=f"{i+1}-sahifa: 429/quota (kutish kerak)", state="error")
                    elif text.lower().startswith("xato:"):
                        s.update(label=f"{i+1}-sahifa: xato", state="error")
                    else:
                        s.update(label=f"{i+1}-sahifa: tayyor", state="complete")

                except Exception as e:
                    st.session_state.results[i] = f"Xato: {type(e).__name__}: {e}"
                    s.update(label=f"{i+1}-sahifa: xato", state="error")

        st.rerun()

    # results
    if st.session_state.results:
        for idx, img in enumerate(st.session_state.imgs):
            if idx in st.session_state.results:
                st.markdown(f"#### 📖 Varaq {idx+1}")
                c1, c2 = st.columns([1, 1.2])
                with c1:
                    st.image(img, use_container_width=True)
                with c2:
                    res = st.session_state.results[idx] or ""
                    st.markdown(f"<div class='result-box'>{html.escape(res).replace(chr(10), '<br/>')}</div>", unsafe_allow_html=True)

                    st.session_state.results[idx] = st.text_area(
                        "Tahrir:", value=res, key=f"ed_{idx}", height=280
                    )

                    # Chat
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user'><b>Q:</b> {html.escape(ch['q'])}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai'><b>AI:</b> {html.escape(ch['a'])}</div>", unsafe_allow_html=True)

                    user_q = st.text_input("Savol bering:", key=f"q_{idx}")
                    if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                        if user_q.strip():
                            chat_prompt = f"Quyidagi natija:\n{res}\n\nSavol: {user_q}\nJavobni o‘zbekcha, aniq va qisqa yoz."
                            chat_txt = gemini_call([chat_prompt], max_output_tokens=1200)
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_txt})
                            st.rerun()

        # Word export
        doc = Document()
        doc.add_paragraph(f"Manuscript AI export — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        doc.add_paragraph(f"File: {st.session_state.last_fn}")
        doc.add_paragraph(f"Model: {MODEL_NAME}")
        doc.add_paragraph("")

        for k in sorted(st.session_state.results.keys()):
            doc.add_heading(f"Varaq {k+1}", level=1)
            doc.add_paragraph(st.session_state.results[k] or "")
            doc.add_paragraph("")

        bio = io.BytesIO()
        doc.save(bio)
        st.download_button("📥 Wordda yuklab olish", bio.getvalue(), "analysis.docx")

gc.collect()
