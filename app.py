import streamlit as st
import streamlit.components.v1 as components

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium

import io, gc, base64, time, random, html, re, threading
from datetime import datetime
from collections import deque

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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

# ===== LIMIT (XAVFSIZ, LEKIN MATN CHIQADI) =====
MAX_OUT_TOKENS = 2200      # ko‘paytirildi (natija bo‘sh qolmasin)
SAFE_RPM = 8               # 429 kamaytirish uchun
RATE_WINDOW_SEC = 60

# ===== MODEL (siz xohlagan alias) =====
MODEL_NAME = "gemini-flash-latest"

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
html, body {{ background: var(--app-bg) !important; margin:0 !important; padding:0 !important; }}
.stApp, div[data-testid="stAppViewContainer"] {{ background: var(--app-bg) !important; min-height: 100vh !important; }}
footer {{visibility: hidden !important;}}
.stAppDeployButton {{display:none !important;}}
#stDecoration {{display:none !important;}}
header[data-testid="stHeader"] {{ background: rgba(0,0,0,0) !important; }}
section[data-testid="stSidebar"] {{
  background: var(--sidebar-bg) !important;
  border-right: 2px solid var(--gold) !important;
}}
section[data-testid="stSidebar"] * {{ color: var(--text) !important; }}
section[data-testid="stSidebar"] .stCaption {{ color: var(--muted) !important; }}
h1,h2,h3,h4 {{
  color: var(--gold) !important;
  font-family: 'Georgia', serif;
  border-bottom: 2px solid var(--gold) !important;
  padding-bottom: 8px !important;
  text-align: center !important;
}}
.stButton>button {{
  background: linear-gradient(135deg, var(--sidebar-bg) 0%, #1e3a8a 100%) !important;
  color: var(--gold) !important;
  font-weight: 900 !important;
  width: 100% !important;
  padding: 11px 12px !important;
  border: 1px solid var(--gold) !important;
  border-radius: 12px !important;
}}
.stTextInput input, .stSelectbox select {{
  background-color: rgba(255,255,255,0.06) !important;
  color: var(--text) !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}
.stTextArea textarea {{
  background-color: #fdfaf1 !important;
  color: #000000 !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}
.sticky-preview {{
  position: sticky;
  top: 4.6rem;
  border-radius: 14px;
  border: 2px solid var(--gold);
  overflow: hidden;
  background: rgba(0,0,0,0.15);
  max-height: 540px;
}}
.sticky-preview img {{
  width: 100%;
  height: 540px;
  object-fit: contain;
  display: block;
}}
</style>
""", unsafe_allow_html=True)

# =========================
# GEMINI INIT
# =========================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(model_name=MODEL_NAME)

# =========================
# RATE LIMITER
# =========================
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
                sleep_for = (self.window - (now - self.ts[0])) + 0.10
            time.sleep(max(0.25, sleep_for))

@st.cache_resource
def get_rate_limiter():
    return RateLimiter(rpm=SAFE_RPM, window_sec=RATE_WINDOW_SEC)

rate_limiter = get_rate_limiter()

# =========================
# IMAGE HELPERS
# =========================
def pil_to_jpeg_bytes(img: Image.Image, quality: int = 80, max_side: int = 1900) -> bytes:
    """Matn o‘qilishi uchun biroz kattaroq qoldiramiz."""
    img = img.convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > max_side:
        ratio = max_side / float(long_side)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

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
    return pil_to_jpeg_bytes(img, quality=80, max_side=1900)

@st.cache_data(show_spinner=False, max_entries=12)
def render_pdf_pages_to_bytes(file_bytes: bytes, max_pages: int, scale: float) -> list[bytes]:
    pdf = pdfium.PdfDocument(file_bytes)
    out = []
    try:
        n = min(len(pdf), max_pages)
        for i in range(n):
            pil_img = pdf[i].render(scale=scale).to_pil()
            out.append(pil_to_jpeg_bytes(pil_img, quality=80, max_side=1900))
    finally:
        try: pdf.close()
        except Exception: pass
    return out

def make_payloads_for_reading(img_bytes: bytes, hi_res: bool = False) -> list[dict]:
    """
    1 request ichida:
    - umumiy rasm
    - chap bet zoom
    - o‘ng bet zoom
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size

    left = img.crop((0, 0, w // 2, h))
    right = img.crop((w // 2, 0, w, h))

    if hi_res:
        full_b = pil_to_jpeg_bytes(img, quality=82, max_side=2200)
        left_b = pil_to_jpeg_bytes(left, quality=84, max_side=2400)
        right_b = pil_to_jpeg_bytes(right, quality=84, max_side=2400)
    else:
        full_b = pil_to_jpeg_bytes(img, quality=80, max_side=1900)
        left_b = pil_to_jpeg_bytes(left, quality=82, max_side=2100)
        right_b = pil_to_jpeg_bytes(right, quality=82, max_side=2100)

    def to_payload(b: bytes):
        return {"mime_type": "image/jpeg", "data": base64.b64encode(b).decode("utf-8")}

    return [to_payload(full_b), to_payload(left_b), to_payload(right_b)]

# =========================
# PROMPT + VALIDATION
# =========================
def build_prompt(hint_lang: str, hint_era: str) -> str:
    hl = hint_lang or "yo‘q"
    he = hint_era or "yo‘q"
    return (
        "Siz qo‘lyozma o‘qish va tarjima bo‘yicha mutaxassissiz.\n"
        "Sizga 3 ta rasm beriladi:\n"
        "1-rasm: umumiy ko‘rinish; 2-rasm: chap bet ZOOM; 3-rasm: o‘ng bet ZOOM.\n"
        "Asosan 2-rasm va 3-rasmdagi zoom matnga tayanib o‘qing.\n\n"
        "QOIDALAR:\n"
        "- Hech narsa uydirmang.\n"
        "- Agar joy o‘qilmasa: [o‘qilmadi] yoki [?] deb yozing.\n"
        "- BO‘LIMLARNI bo‘sh qoldirmang. Hech bo‘lmasa [o‘qilmadi] bilan to‘ldiring.\n\n"
        f"HINTLAR: til='{hl}', xat uslubi='{he}'.\n\n"
        "FORMAT (aniq shu tartibda):\n"
        "0) Tashxis:\n"
        "Til: <aniqlangan til yoki Noma'lum>\n"
        "Xat uslubi: <aniqlangan xat yoki Noma'lum>\n"
        "Ishonchlilik: <Yuqori/O‘rtacha/Past>\n\n"
        "2) To‘g‘ridan-to‘g‘ri tarjima:\n"
        "<oddiy o‘zbekcha, to‘liq; o‘qilmasa [o‘qilmadi]>\n\n"
        "6) Izoh:\n"
        "<kontekst va noaniqliklar; ehtiyotkor izoh>\n"
    )

def has_sections(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return ("2)" in t and "tarjima" in t and "6)" in t and "izoh" in t)

def call_gemini(prompt: str, payloads: list[dict], tries: int = 6) -> str:
    last_err = None
    for attempt in range(tries):
        try:
            rate_limiter.wait_for_slot()
            resp = model.generate_content(
                [prompt, *payloads],
                generation_config={"max_output_tokens": MAX_OUT_TOKENS, "temperature": 0.15}
            )
            return getattr(resp, "text", "") or ""
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if ("429" in msg) or ("rate" in msg) or ("quota" in msg) or ("exhaust" in msg):
                time.sleep(min(60, (2 ** attempt)) + random.uniform(0.8, 2.0))
                continue
            raise
    raise RuntimeError(f"Gemini 429: {last_err}") from last_err

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.markdown("### 🧠 Hintlar")
    auto_detect = st.checkbox("🧠 Avto aniqlash (tavsiya)", value=True)
    lang = st.selectbox("Taxminiy matn tili (hint):", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=0)
    era = st.selectbox("Taxminiy xat uslubi (hint):", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=0)

    st.markdown("### 🧪 Skan sozlamalari")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.05)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.45)
    sharpen = st.slider("Sharpen:", 0.0, 1.5, 1.0, 0.1)

    # Matn uchun biroz yuqoriroq scale (lekin juda katta emas)
    scale = st.slider("PDF render scale:", 1.2, 2.7, 1.9, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 60, 30)

# =========================
# MAIN
# =========================
st.title("📜 Manuscript AI Center")
uploaded_file = st.file_uploader("Faylni yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

if uploaded_file is None:
    st.stop()

# Load pages
file_bytes = uploaded_file.getvalue()
if uploaded_file.type == "application/pdf":
    pages = render_pdf_pages_to_bytes(file_bytes, max_pages=max_pages, scale=scale)
else:
    img = Image.open(io.BytesIO(file_bytes))
    pages = [pil_to_jpeg_bytes(img, quality=82, max_side=2200)]

processed_pages = [
    preprocess_bytes(b, brightness=brightness, contrast=contrast, rotate=rotate, sharpen=sharpen)
    for b in pages
]

total_pages = len(processed_pages)
st.caption(f"Yuklandi: **{total_pages}** sahifa.")

selected = st.multiselect(
    "Sahifalarni tanlang:",
    options=list(range(total_pages)),
    default=[0] if total_pages else [],
    format_func=lambda x: f"{x+1}-sahifa"
)

if "results" not in st.session_state:
    st.session_state.results = {}

if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
    if not selected:
        st.warning("Avval sahifani tanlang.")
        st.stop()

    hint_lang = "" if (auto_detect or lang == "Noma'lum") else lang
    hint_era = "" if (auto_detect or era == "Noma'lum") else era
    prompt = build_prompt(hint_lang, hint_era)

    bar = st.progress(0.0)
    for i, idx in enumerate(selected, start=1):
        with st.status(f"Sahifa {idx+1}..."):
            img_bytes = processed_pages[idx]

            # 1-urinish: normal crop payload
            payloads = make_payloads_for_reading(img_bytes, hi_res=False)
            text = call_gemini(prompt, payloads, tries=6).strip()

            # Agar bo‘limlar chiqmasa: 2-urinish HI-RES crop
            if not has_sections(text) or len(text) < 120:
                payloads2 = make_payloads_for_reading(img_bytes, hi_res=True)
                text2 = call_gemini(prompt + "\nMUHIM: 2) va 6) bo‘limlarini ALBATTA to‘ldiring.", payloads2, tries=5).strip()
                if text2:
                    text = text2

            if not text:
                text = "2) To‘g‘ridan-to‘g‘ri tarjima:\n[o‘qilmadi]\n\n6) Izoh:\nMatn o‘qilmadi. Iltimos, rasmni yaqinroq (zoom) yoki bitta bet qilib yuklang."

            st.session_state.results[idx] = text

        bar.progress(i / max(len(selected), 1))

    st.success("Tahlil yakunlandi.")

# Results
if st.session_state.results:
    st.divider()
    for idx in sorted(st.session_state.results.keys()):
        res = st.session_state.results[idx]
        with st.expander(f"📖 Varaq {idx+1}", expanded=True):
            img_b64 = base64.b64encode(processed_pages[idx]).decode("utf-8")
            st.markdown(
                f"<div class='sticky-preview'><img src='data:image/jpeg;base64,{img_b64}'/></div>",
                unsafe_allow_html=True
            )

            copy_js = f"""
            <button id="copybtn_{idx}" style="width:100%;padding:10px 12px;border-radius:12px;border:1px solid rgba(0,0,0,0.12);font-weight:900;cursor:pointer;">
              📋 Natijani nusxalash
            </button>
            <script>
              const t_{idx} = {html.escape(res)!r};
              document.getElementById("copybtn_{idx}").onclick = async () => {{
                try {{
                  await navigator.clipboard.writeText(t_{idx});
                  document.getElementById("copybtn_{idx}").innerText = "✅ Nusxalandi";
                  setTimeout(()=>document.getElementById("copybtn_{idx}").innerText="📋 Natijani nusxalash", 1500);
                }} catch(e) {{
                  document.getElementById("copybtn_{idx}").innerText = "❌ Clipboard ruxsat yo‘q";
                }}
              }}
            </script>
            """
            components.html(copy_js, height=55)
            st.text_area("Natija:", value=res, height=420, key=f"r_{idx}")

gc.collect()
