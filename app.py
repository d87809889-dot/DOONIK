import streamlit as st
import streamlit.components.v1 as components

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium

import io, gc, base64, time, random, html, re, threading
from collections import deque


# ==========================================
# CONFIG
# ==========================================
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

# ==========================================
# SAFETY TUNING
# ==========================================
# Vision (o'qish) uchun:
READ_MAX_TOKENS = 4096       # transliteratsiya uzun bo'ladi
# Text-only (tarjima+izoh) uchun:
AN_MAX_TOKENS = 2200

SAFE_RPM = 7                 # 429 ni keskin kamaytiradi
RATE_WINDOW_SEC = 60

# Model nomi o'zgarib qolsa 404 ni avtomatik aylanib o'tamiz:
MODEL_CANDIDATES = [
    "gemini-flash-latest",       # siz xohlagan
    "gemini-1.5-flash-latest",   # fallback 1
    "gemini-1.5-flash",          # fallback 2
]

# Rasm o'lchami (o‘qish uchun yetarli, lekin 429ni kuchaytirmaydi):
FULL_MAX_SIDE = 2000          # umumiy preview
TILE_MAX_SIDE = 2400          # zoom tile
JPEG_QUALITY = 82

# PDF scale (matn uchun balans):
PDF_SCALE_DEFAULT = 2.0
PDF_SCALE_MIN = 1.4
PDF_SCALE_MAX = 2.6


# ==========================================
# CSS
# ==========================================
st.markdown(f"""
<style>
:root {{
  --app-bg: {C["app_bg"]};
  --sidebar-bg: {C["sidebar_bg"]};
  --text: {C["text"]};
  --muted: {C["muted"]};
  --gold: {C["gold"]};
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


# ==========================================
# RATE LIMITER (process-wide)
# ==========================================
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
                sleep_for = (self.window - (now - self.ts[0])) + 0.15
            time.sleep(max(0.30, sleep_for))

@st.cache_resource
def get_limiter():
    return RateLimiter(SAFE_RPM, RATE_WINDOW_SEC)

limiter = get_limiter()


# ==========================================
# GEMINI INIT
# ==========================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

@st.cache_resource
def get_model(name: str):
    return genai.GenerativeModel(model_name=name)

def _looks_like_404(msg: str) -> bool:
    m = (msg or "").lower()
    return ("404" in m) or ("not found" in m) or ("model" in m and "not" in m and "found" in m)

def _looks_like_429(msg: str) -> bool:
    m = (msg or "").lower()
    return ("429" in m) or ("quota" in m) or ("rate" in m) or ("exhaust" in m)

def safe_generate(model_name: str, parts: list, max_tokens: int, tries: int = 7) -> str:
    """
    404 -> model fallback
    429/5xx -> backoff + retry
    """
    last_err = None
    candidates = [model_name] + [m for m in MODEL_CANDIDATES if m != model_name]

    for cand in candidates:
        model = get_model(cand)
        for attempt in range(tries):
            try:
                limiter.wait_for_slot()
                resp = model.generate_content(
                    parts,
                    generation_config={"max_output_tokens": max_tokens, "temperature": 0.15}
                )
                return getattr(resp, "text", "") or ""
            except Exception as e:
                last_err = e
                msg = str(e)

                # 404 -> keyingi model
                if _looks_like_404(msg):
                    break

                # 429 / vaqtinchalik xatolar -> retry
                if _looks_like_429(msg) or ("500" in msg) or ("503" in msg) or ("timeout" in msg.lower()):
                    sleep_s = min(60, (2 ** attempt)) + random.uniform(0.8, 2.0)
                    time.sleep(sleep_s)
                    continue

                # boshqa xato -> darhol chiqaramiz
                raise

    raise RuntimeError(f"AI xatosi: {last_err}")


# ==========================================
# IMAGE HELPERS
# ==========================================
def pil_to_jpeg_bytes(img: Image.Image, quality: int, max_side: int) -> bytes:
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
    return pil_to_jpeg_bytes(img, JPEG_QUALITY, FULL_MAX_SIDE)

@st.cache_data(show_spinner=False, max_entries=12)
def render_pdf_pages_to_bytes(file_bytes: bytes, max_pages: int, scale: float) -> list[bytes]:
    pdf = pdfium.PdfDocument(file_bytes)
    out = []
    try:
        n = min(len(pdf), max_pages)
        for i in range(n):
            pil_img = pdf[i].render(scale=scale).to_pil()
            out.append(pil_to_jpeg_bytes(pil_img, JPEG_QUALITY, FULL_MAX_SIDE))
    finally:
        try: pdf.close()
        except Exception: pass
    return out

def build_tiles(img_bytes: bytes) -> list[bytes]:
    """
    1 sahifa uchun 1 request ichida yuboriladigan rasmlar:
    - full (umumiy)
    - agar spread bo'lsa: left/right zoom
    - aks holda: 2x2 tile (bir oz overlap)
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    aspect = w / max(h, 1)

    tiles = []
    # full
    tiles.append(pil_to_jpeg_bytes(img, JPEG_QUALITY, FULL_MAX_SIDE))

    if aspect >= 1.25:
        # spread (ikki bet)
        left = img.crop((0, 0, w // 2, h))
        right = img.crop((w // 2, 0, w, h))
        tiles.append(pil_to_jpeg_bytes(left, JPEG_QUALITY, TILE_MAX_SIDE))
        tiles.append(pil_to_jpeg_bytes(right, JPEG_QUALITY, TILE_MAX_SIDE))
        return tiles

    # normal page -> 2x2 with overlap
    ox = int(w * 0.06)
    oy = int(h * 0.06)
    xs = [0, w // 2]
    ys = [0, h // 2]
    for yy in ys:
        for xx in xs:
            x1 = max(0, xx - ox)
            y1 = max(0, yy - oy)
            x2 = min(w, xx + w // 2 + ox)
            y2 = min(h, yy + h // 2 + oy)
            tile = img.crop((x1, y1, x2, y2))
            tiles.append(pil_to_jpeg_bytes(tile, JPEG_QUALITY, TILE_MAX_SIDE))

    return tiles

def to_payload(img_b: bytes) -> dict:
    return {"mime_type": "image/jpeg", "data": base64.b64encode(img_b).decode("utf-8")}


# ==========================================
# PROMPTS (2-step)
# ==========================================
def prompt_read(hint_lang: str, hint_era: str) -> str:
    hl = hint_lang or "yo‘q"
    he = hint_era or "yo‘q"
    return (
        "Siz qo‘lyozma o‘qish bo‘yicha mutaxassissiz.\n"
        "Sizga bir sahifa uchun bir nechta rasm beriladi (full + zoom/tiles).\n"
        "Vazifa: RASMDAGI MATNNI maksimal to‘liq TRANSLITERATSIYA qiling.\n\n"
        "QOIDALAR:\n"
        "- Hech narsa uydirmang.\n"
        "- O‘qilmagan joy: [o‘qilmadi] yoki [?].\n"
        "- Har satr alohida qatorda bo‘lsin.\n"
        "- Matnda bor narsani tashlab ketmang.\n\n"
        f"HINT: til='{hl}', xat='{he}'.\n\n"
        "FORMAT (aniq shunday):\n"
        "1) Transliteratsiya:\n"
        "<satrma-satr, to‘liq>\n"
    )

def prompt_analyze(translit: str) -> str:
    return (
        "Siz Manuscript AI tarjimonisiz.\n"
        "Vazifa: quyidagi transliteratsiya asosida faqat 2) va 6) bo‘limlarini yozing.\n"
        "QOIDALAR:\n"
        "- Hech narsa uydirmang.\n"
        "- Ism/son/sana/joylarni aynan transliteratsiyadagidek saqlang.\n\n"
        "FORMAT:\n"
        "2) To‘g‘ridan-to‘g‘ri tarjima:\n"
        "<oddiy o‘zbekcha, to‘liq>\n\n"
        "6) Izoh:\n"
        "<kontekst; noaniq joylarni ehtiyotkor izohlang>\n\n"
        "TRANSLITERATSIYA:\n"
        f"{translit}"
    )

def extract_translit(read_text: str) -> str:
    if not read_text:
        return ""
    m = re.search(r"1\)\s*Transliteratsiya\s*:?\s*\n?([\s\S]+)$", read_text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return read_text.strip()

def ok_translit(t: str) -> bool:
    # juda qisqa bo'lsa, demak o'qimagan
    return bool(t and len(t.strip()) >= 300)

def ok_an(text: str) -> bool:
    t = (text or "").lower()
    return ("2)" in t and "tarjima" in t and "6)" in t and "izoh" in t and len(text) >= 200)


# ==========================================
# UI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 Manuscript AI</h2>", unsafe_allow_html=True)
    st.markdown("### 🧠 Hintlar")
    auto_detect = st.checkbox("🧠 Avto aniqlash (tavsiya)", value=True)
    lang = st.selectbox("Taxminiy matn tili (hint):", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=0)
    era = st.selectbox("Taxminiy xat uslubi (hint):", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=0)

    st.markdown("### 🧪 Skan sozlamalari")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.05)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.45)
    sharpen = st.slider("Sharpen:", 0.0, 1.5, 1.0, 0.1)

    scale = st.slider("PDF render scale:", PDF_SCALE_MIN, PDF_SCALE_MAX, PDF_SCALE_DEFAULT, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 120, 40)

st.title("📜 Manuscript AI Center")
uploaded_file = st.file_uploader("Faylni yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")
if uploaded_file is None:
    st.stop()

# Load pages
file_bytes = uploaded_file.getvalue()
if uploaded_file.type == "application/pdf":
    raw_pages = render_pdf_pages_to_bytes(file_bytes, max_pages=max_pages, scale=scale)
else:
    img = Image.open(io.BytesIO(file_bytes))
    raw_pages = [pil_to_jpeg_bytes(img, JPEG_QUALITY, FULL_MAX_SIDE)]

pages = [preprocess_bytes(b, brightness, contrast, rotate, sharpen) for b in raw_pages]
total_pages = len(pages)
st.caption(f"Yuklandi: **{total_pages}** sahifa (preview: {max_pages}).")

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
    hint_era  = "" if (auto_detect or era == "Noma'lum") else era

    p_read = prompt_read(hint_lang, hint_era)

    bar = st.progress(0.0)
    for i, idx in enumerate(selected, start=1):
        with st.status(f"Sahifa {idx+1}...") as s:
            try:
                img_bytes = pages[idx]
                tiles = build_tiles(img_bytes)
                payloads = [to_payload(b) for b in tiles]

                # STEP A: READ (vision)
                read_text = safe_generate(
                    model_name=MODEL_CANDIDATES[0],
                    parts=[p_read, *payloads],
                    max_tokens=READ_MAX_TOKENS,
                    tries=7
                ).strip()

                translit = extract_translit(read_text)

                # Agar juda qisqa bo'lsa: yana bir marta kuchliroq instruktsiya bilan
                if not ok_translit(translit):
                    read_text2 = safe_generate(
                        model_name=MODEL_CANDIDATES[0],
                        parts=[p_read + "\nMUHIM: Hech bir so‘zni tashlab ketmang. Zoom/tilesga tayaning. Matn ko‘p bo‘lsa ham yozing.",
                               *payloads],
                        max_tokens=READ_MAX_TOKENS,
                        tries=6
                    ).strip()
                    translit2 = extract_translit(read_text2)
                    if len(translit2) > len(translit):
                        translit = translit2

                # STEP B: ANALYZE (text-only)
                an = safe_generate(
                    model_name=MODEL_CANDIDATES[0],
                    parts=[prompt_analyze(translit)],
                    max_tokens=AN_MAX_TOKENS,
                    tries=6
                ).strip()

                # Validate; agar bo'limlar yo'q bo'lsa, 1 retry
                if not ok_an(an):
                    an2 = safe_generate(
                        model_name=MODEL_CANDIDATES[0],
                        parts=[prompt_analyze(translit) + "\nMUHIM: Faqat 2) va 6) bo‘limlarini to‘liq chiqaring."],
                        max_tokens=AN_MAX_TOKENS,
                        tries=5
                    ).strip()
                    if an2:
                        an = an2

                final = (
                    "0) Tashxis:\n"
                    f"Til: {lang if lang != \"Noma'lum\" else 'Noma\\'lum'}\n"
                    f"Xat uslubi: {era if era != \"Noma'lum\" else 'Noma\\'lum'}\n"
                    "Ishonchlilik: (AI bahosi natijada)\n\n"
                    "1) Transliteratsiya:\n"
                    f"{translit}\n\n"
                    f"{an}"
                )

                st.session_state.results[idx] = final
                s.update(label="Tayyor!", state="complete")

            except Exception as e:
                st.session_state.results[idx] = f"Xato: {type(e).__name__}: {e}"
                s.update(label="Xato", state="error")
                st.error(st.session_state.results[idx])

        bar.progress(i / max(len(selected), 1))

    st.success("Tahlil yakunlandi.")
    gc.collect()

# Results
if st.session_state.results:
    st.divider()
    for idx in sorted(st.session_state.results.keys()):
        res = st.session_state.results[idx]
        with st.expander(f"📖 Varaq {idx+1}", expanded=True):
            img_b64 = base64.b64encode(pages[idx]).decode("utf-8")
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

            st.text_area("Natija:", value=res, height=520, key=f"r_{idx}")

gc.collect()
