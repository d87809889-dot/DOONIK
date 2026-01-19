import streamlit as st
import streamlit.components.v1 as components

# === YANGI GOOGLE GEN AI SDK ===
from google import genai

from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium

import io, gc, base64, time, random, html, re, threading
from datetime import datetime
from collections import Counter, deque

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
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

# ==========================================
# 2) APP CONSTANTS
# ==========================================
THEME = "DARK_GOLD"
DEMO_LIMIT_PAGES = 3
STARTER_CREDITS = 10
HISTORY_LIMIT = 20

# ======== LIMITLAR (XAVFSIZ) ========
MAX_OUT_TOKENS = 1536          # pasaytirildi (TPM uchun)
GEMINI_RPM_LIMIT = 15
SAFE_RPM = 12
RATE_WINDOW_SEC = 60

# ======== MODEL ========
MODEL_ID = "gemini-1.5-flash-latest"   # SIZ XOHLAgan "flash latest" liniyasi

# ==========================================
# 3) THEMES
# ==========================================
THEMES = {
    "DARK_GOLD": {
        "app_bg": "#0b1220",
        "surface": "#10182b",
        "sidebar_bg": "#0c1421",
        "text": "#eaf0ff",
        "muted": "#c7d0e6",
        "gold": "#c5a059",
        "gold2": "#d4af37",
    }
}
C = THEMES["DARK_GOLD"]

# ==========================================
# 4) CSS (O'ZGARMAYDI)
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

footer {{visibility: hidden !important;}}
.stAppDeployButton {{display:none !important;}}
#stDecoration {{display:none !important;}}
header[data-testid="stHeader"] {{ background: rgba(0,0,0,0) !important; }}

section[data-testid="stSidebar"] {{
  background: var(--sidebar-bg) !important;
  border-right: 2px solid var(--gold) !important;
}}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5) SERVICES
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

# ======== GOOGLE GENAI CLIENT ========
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# ========= Global Rate Limiter =========
class RateLimiter:
    def __init__(self, rpm: int, window_sec: int = 60):
        self.rpm = max(1, int(rpm))
        self.window = int(window_sec)
        self.lock = threading.Lock()
        self.ts = deque()

    def wait_for_slot(self):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.ts and (now - self.ts[0]) > self.window:
                    self.ts.popleft()

                if len(self.ts) < self.rpm:
                    self.ts.append(now)
                    return

                sleep_for = (self.window - (now - self.ts[0])) + 0.05
            time.sleep(max(0.2, sleep_for))

@st.cache_resource
def get_rate_limiter():
    return RateLimiter(rpm=SAFE_RPM, window_sec=RATE_WINDOW_SEC)

rate_limiter = get_rate_limiter()

# ==========================================
# 6) STATE
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""
if "last_fn" not in st.session_state: st.session_state.last_fn = None
if "page_bytes" not in st.session_state: st.session_state.page_bytes = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}
if "warn_db" not in st.session_state: st.session_state.warn_db = False

# ==========================================
# 7) HELPERS
# ==========================================
def pil_to_jpeg_bytes(img: Image.Image, quality: int = 75, max_side: int = 1600) -> bytes:
    """Rasmni kichraytirib, yengillashtirib JPEG qilamiz"""
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
    out = []
    try:
        n = min(len(pdf), max_pages)
        for i in range(n):
            pil_img = pdf[i].render(scale=scale).to_pil()
            out.append(pil_to_jpeg_bytes(pil_img))
    finally:
        try: pdf.close()
        except Exception: pass
    return out

@st.cache_data(show_spinner=False, max_entries=256)
def preprocess_bytes(img_bytes: bytes, brightness: float, contrast: float, rotate: int, sharpen: float) -> bytes:
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageOps.exif_transpose(img)
    if rotate:
        img = img.rotate(rotate, expand=True)

    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)

    if sharpen > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(120 * sharpen), threshold=2))

    return pil_to_jpeg_bytes(img)

def parse_pages(spec: str, max_n: int) -> list[int]:
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

# ======== GEMINI WRAPPER (RATE LIMIT + BACKOFF) ========
def call_gemini_with_retry(prompt: str, img_bytes: bytes | None = None, tries: int = 6) -> str:
    last_err = None

    for attempt in range(tries):
        try:
            rate_limiter.wait_for_slot()

            contents = [prompt]
            if img_bytes:
                img = Image.open(io.BytesIO(img_bytes))
                contents.append(img)

            resp = client.models.generate_content(
                model=MODEL_ID,
                contents=contents,
                config={"max_output_tokens": MAX_OUT_TOKENS}
            )
            return resp.text or ""

        except Exception as e:
            last_err = e
            msg = str(e).lower()

            if ("429" in msg) or ("rate" in msg) or ("quota" in msg) or ("exhausted" in msg):
                base = min(45, (2 ** attempt))
                time.sleep(base + random.uniform(0.5, 1.5))
                continue
            raise

    raise RuntimeError("So'rovlar ko'p (429). Birozdan keyin qayta urinib ko'ring.") from last_err

# ==========================================
# SINGLE-REQUEST PROMPT (ENG MUHIM QISM)
# ==========================================
def build_single_prompt(hint_lang: str, hint_era: str) -> str:
    hl = hint_lang or "yo‘q"
    he = hint_era or "yo‘q"

    return (
        "Siz qo‘lyozma o‘qish va tarjima bo‘yicha mutaxassissiz.\n"
        "Vazifa: rasm ichidagi matnni o‘qing va faqat quyidagi bo‘limlarda chiqaring.\n\n"
        "QOIDALAR:\n"
        "- Hech narsa uydirmang.\n"
        "- O‘qilmagan joy: [o‘qilmadi] yoki [?].\n"
        "- Ism/son/sana/joy nomlarini aynan matndek saqlang.\n"
        "- Transliteratsiya satrma-satr bo‘lsin.\n"
        "- Tarjima oddiy o‘zbekcha, to‘liq.\n\n"
        f"HINTLAR: til='{hl}', xat uslubi='{he}'. Agar hint 'yo‘q' bo‘lsa, o‘zingiz aniqlang.\n\n"
        "FORMAT (ANIQ SHU TARTIBDA):\n"
        "0) Tashxis:\n"
        "Til: <aniqlangan til yoki Noma'lum>\n"
        "Xat uslubi: <aniqlangan xat yoki Noma'lum>\n"
        "Ishonchlilik: <Yuqori/O‘rtacha/Past>\n\n"
        "1) Transliteratsiya:\n"
        "<satrma-satr matn>\n\n"
        "2) To‘g‘ridan-to‘g‘ri tarjima:\n"
        "<oddiy o‘zbekcha, to‘liq>\n\n"
        "6) Izoh:\n"
        "<kontekst va noaniqliklar; ehtiyotkor izoh>\n"
    )

# ==========================================
# 10) SIDEBAR (ASOSAN O'ZGARMAYDI)
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)

    st.markdown("### ✉️ Email bilan kirish")
    email_in = st.text_input("Email", placeholder="example@mail.com")
    if st.button("KIRISH"):
        email = (email_in or "").strip().lower()
        if not email or "@" not in email:
            st.error("Emailni to‘g‘ri kiriting.")
        else:
            st.session_state.auth = True
            st.session_state.u_email = email
            st.rerun()

    st.markdown("### 🧠 Hintlar")
    auto_detect = st.checkbox("🧠 Avto aniqlash (tavsiya)", value=True)
    lang = st.selectbox("Taxminiy matn tili (hint):",
                        ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Taxminiy xat uslubi (hint):",
                       ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"])

    st.markdown("### 🧪 Skan sozlamalari")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.35)
    sharpen = st.slider("Sharpen:", 0.0, 1.5, 0.9, 0.1)

    # ==== PDF scale pasaytirildi ====
    scale = st.slider("PDF render scale:", 1.2, 2.4, 1.5, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 60, 30)

# ==========================================
# 11) MAIN UI
# ==========================================
st.title("📜 Manuscript AI Center")
uploaded_file = st.file_uploader(
    "Faylni yuklang",
    type=["pdf", "png", "jpg", "jpeg"],
    label_visibility="collapsed"
)

if uploaded_file is None:
    st.stop()

# ======= PDF / IMAGE LOAD =======
if st.session_state.last_fn != uploaded_file.name:
    with st.spinner("Preparing..."):
        file_bytes = uploaded_file.getvalue()
        if uploaded_file.type == "application/pdf":
            pages = render_pdf_pages_to_bytes(file_bytes, max_pages=max_pages, scale=scale)
        else:
            img = Image.open(io.BytesIO(file_bytes))
            pages = [pil_to_jpeg_bytes(img)]

        st.session_state.page_bytes = pages
        st.session_state.last_fn = uploaded_file.name
        st.session_state.results = {}
        st.session_state.chats = {}
        gc.collect()

processed_pages = [
    preprocess_bytes(b, brightness=brightness, contrast=contrast, rotate=rotate, sharpen=sharpen)
    for b in st.session_state.page_bytes
]

total_pages = len(processed_pages)
st.caption(f"Yuklandi: **{total_pages}** sahifa.")

selected_indices = st.multiselect(
    "Sahifalarni tanlang:",
    options=list(range(total_pages)),
    default=[0] if total_pages else [],
    format_func=lambda x: f"{x+1}-sahifa"
)

# ==========================================
# RUN ANALYSIS (1 REQUEST PER PAGE)
# ==========================================
if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
    if not selected_indices:
        st.warning("Avval sahifani tanlang.")
        st.stop()

    hint_lang = "" if (auto_detect or lang == "Noma'lum") else lang
    hint_era = "" if (auto_detect or era == "Noma'lum") else era

    total = len(selected_indices)
    done = 0
    bar = st.progress(0.0)

    for idx in selected_indices:
        with st.status(f"Sahifa {idx+1}..."):
            try:
                img_bytes = processed_pages[idx]
                prompt = build_single_prompt(hint_lang, hint_era)
                result_text = call_gemini_with_retry(prompt, img_bytes, tries=6)

                if not result_text:
                    raise RuntimeError("Bo‘sh natija qaytdi.")

                st.session_state.results[idx] = result_text
                st.success(f"Sahifa {idx+1} tayyor!")

            except Exception as e:
                st.session_state.results[idx] = f"Xato: {e}"
                st.error(f"Sahifa {idx+1}: {e}")

        done += 1
        bar.progress(done / total)

# ==========================================
# RESULTS VIEW
# ==========================================
if st.session_state.results:
    st.divider()
    for idx, res in sorted(st.session_state.results.items()):
        with st.expander(f"📖 Varaq {idx+1}", expanded=True):
            st.text_area("Natija:", value=res, height=300)
