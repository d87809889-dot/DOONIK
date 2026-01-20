import streamlit as st
import streamlit.components.v1 as components

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium

import io, gc, base64, time, random, html, re, threading
from datetime import datetime
from collections import Counter, deque

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

try:
    from supabase import create_client
except Exception:
    create_client = None


# =========================================================
# 1) CONFIG
# =========================================================
st.set_page_config(
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# 2) THEME (SODDA, BARQAROR)
# =========================================================
C = {
    "app_bg": "#0b1220",
    "surface": "#10182b",
    "sidebar_bg": "#0c1421",
    "text": "#eaf0ff",
    "muted": "#c7d0e6",
    "gold": "#c5a059",
    "gold2": "#d4af37",
    "card": "#ffffff",
    "card_text": "#111827",
}

st.markdown(
    f"""
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
  margin:0 !important; padding:0 !important;
}}
.stApp, div[data-testid="stAppViewContainer"] {{
  background: var(--app-bg) !important;
  min-height: 100vh !important;
}}
div[data-testid="stAppViewContainer"] .main .block-container {{
  padding-top: 3.2rem !important;
  padding-bottom: 1.25rem !important;
}}

footer {{visibility:hidden !important;}}
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

h1,h2,h3,h4 {{
  color: var(--gold2) !important;
  font-family: Georgia, serif !important;
  border-bottom: 2px solid rgba(212,175,55,0.55) !important;
  padding-bottom: 6px !important;
  text-align:center !important;
}}

.stMarkdown p {{ color: var(--muted) !important; }}

.stButton>button {{
  background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
  color: var(--gold2) !important;
  font-weight: 900 !important;
  width: 100% !important;
  padding: 11px 12px !important;
  border: 1px solid rgba(212,175,55,0.7) !important;
  border-radius: 12px !important;
  box-shadow: 0 12px 24px rgba(0,0,0,0.25) !important;
  transition: transform .15s ease, filter .2s ease !important;
}}
.stButton>button:hover {{
  transform: translateY(-1px);
  filter: brightness(1.08);
}}

.stTextInput input, .stSelectbox select {{
  background-color: rgba(255,255,255,0.06) !important;
  color: var(--text) !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}

.stTextArea textarea {{
  background-color: #fdfaf1 !important;
  color: #000 !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}

.result-box {{
  background: var(--card) !important;
  color: var(--card-text) !important;
  padding: 18px !important;
  border-radius: 16px !important;
  border-left: 10px solid var(--gold2) !important;
  box-shadow: 0 10px 30px rgba(0,0,0,0.18) !important;
  line-height: 1.75 !important;
  white-space: pre-wrap !important;
}}

.sticky-preview {{
  position: sticky;
  top: 4.6rem;
  border-radius: 14px;
  border: 2px solid rgba(212,175,55,0.8);
  overflow: hidden;
  box-shadow: 0 14px 35px rgba(0,0,0,0.22);
  background: rgba(0,0,0,0.15);
}}
.sticky-preview img {{
  width: 100%;
  height: 540px;
  object-fit: contain;
  display: block;
}}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# 3) SECRETS (BARQAROR)
# =========================================================
def get_secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
APP_PASSWORD = get_secret("APP_PASSWORD", "")  # optional
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "")

if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY topilmadi. Streamlit Secrets ichiga qo‘ying.")
    st.stop()

# =========================================================
# 4) GEMINI (MODELGA TEGMAYMIZ!)
# =========================================================
genai.configure(api_key=GEMINI_API_KEY)

# MUHIM: foydalanuvchi talabiga ko‘ra modelni o‘zgartirmaymiz
MODEL_NAME = "gemini-flash-latest"

@st.cache_resource
def get_model():
    return genai.GenerativeModel(model_name=MODEL_NAME)

model = get_model()

# =========================================================
# 5) SUPABASE (OPTIONAL, YIQILMASIN)
# =========================================================
@st.cache_resource
def get_db():
    if not (SUPABASE_URL and SUPABASE_KEY and create_client):
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None

db = get_db()

def safe_get_credits(email: str) -> int:
    if db is None or not email:
        return 0
    try:
        r = db.table("profiles").select("credits").eq("email", email).single().execute()
        if r.data and "credits" in r.data:
            return int(r.data["credits"])
    except Exception:
        pass
    return 0

def safe_decrement_credit(email: str, n: int = 1) -> None:
    if db is None or not email:
        return
    try:
        cur = safe_get_credits(email)
        db.table("profiles").update({"credits": max(cur - n, 0)}).eq("email", email).execute()
    except Exception:
        pass

# =========================================================
# 6) RATE LIMITER + RETRY (MODELGA TEGMAYDI)
# =========================================================
SAFE_RPM = 8
RATE_WINDOW_SEC = 60
MAX_RETRIES = 6

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
                sleep_for = (self.window - (now - self.ts[0])) + 0.2
            time.sleep(max(0.35, sleep_for))

@st.cache_resource
def get_limiter():
    return RateLimiter(SAFE_RPM, RATE_WINDOW_SEC)

limiter = get_limiter()

def _extract_retry_seconds(err_text: str) -> int:
    """
    Gemini ba'zan 'Please retry in 59.5s' yoki 'retry_delay { seconds: 59 }' ko‘rinishida beradi.
    """
    t = (err_text or "")
    m1 = re.search(r"retry in\s+(\d+(\.\d+)?)s", t, flags=re.IGNORECASE)
    if m1:
        return int(float(m1.group(1)))
    m2 = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", t, flags=re.IGNORECASE)
    if m2:
        return int(m2.group(1))
    return 0

def _looks_like_429(msg: str) -> bool:
    m = (msg or "").lower()
    return ("429" in m) or ("quota" in m) or ("rate limit" in m) or ("exceeded your current quota" in m)

def _looks_like_5xx(msg: str) -> bool:
    m = (msg or "").lower()
    return any(x in m for x in ["500", "503", "timeout", "temporarily unavailable", "internal error"])

def generate_with_retry(parts, max_tokens: int = 4096, temperature: float = 0.15) -> str:
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            limiter.wait_for_slot()
            resp = model.generate_content(
                parts,
                generation_config={"max_output_tokens": int(max_tokens), "temperature": float(temperature)},
            )
            return getattr(resp, "text", "") or ""
        except Exception as e:
            last_err = e
            msg = str(e)

            low = msg.lower()
            if "404" in low and "not found" in low:
                raise RuntimeError(
                    f"AI xatosi: 404. Model topilmadi/qo‘llab-quvvatlanmadi. "
                    f"Model nomi o‘zgartirilmagan: {MODEL_NAME}"
                ) from e

            if _looks_like_429(msg):
                s = _extract_retry_seconds(msg)
                # server aytgan kutish bo‘lsa shunga yaqin kutamiz, bo‘lmasa backoff
                wait_s = max(s, min(60, (2 ** attempt) + random.uniform(0.6, 1.8)))
                time.sleep(wait_s)
                continue

            if _looks_like_5xx(msg):
                time.sleep(min(45, (2 ** attempt) + random.uniform(0.6, 1.8)))
                continue

            raise
    raise RuntimeError(f"So‘rov bajarilmadi (429/Network). Oxirgi xato: {last_err}") from last_err


# =========================================================
# 7) IMAGE HELPERS (FULL + TILES + OPTIONAL CROP)
# =========================================================
def pil_to_jpeg_bytes(img: Image.Image, max_side: int = 1800, quality: int = 84) -> bytes:
    img = img.convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > max_side:
        ratio = max_side / float(long_side)
        img = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(quality), optimize=True)
    return buf.getvalue()

def payload_from_bytes(img_bytes: bytes) -> dict:
    return {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}

def build_payloads_full_and_tiles(img: Image.Image):
    """
    1 request ichida: full + 4 tile (2x2 overlap).
    Request soni oshmaydi, aniqlik oshadi.
    """
    img = img.convert("RGB")
    w, h = img.size

    payloads = []
    full_bytes = pil_to_jpeg_bytes(img, max_side=1600, quality=82)
    payloads.append(payload_from_bytes(full_bytes))

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
            tile_bytes = pil_to_jpeg_bytes(tile, max_side=1800, quality=84)
            payloads.append(payload_from_bytes(tile_bytes))

    return payloads

def auto_crop_text_region(img: Image.Image) -> Image.Image:
    """
    Yengil auto-crop: oq/bo‘sh marginlarni qisqartirishga urinish.
    Juda agressiv emas — xato crop bo‘lmasin.
    """
    img = img.convert("RGB")
    gray = ImageOps.grayscale(img)
    # kontrastni biroz oshirib, matnni ajratamiz
    g = ImageEnhance.Contrast(gray).enhance(1.6)
    # threshold (matn=quyuq)
    bw = g.point(lambda p: 255 if p > 210 else 0)
    bbox = bw.getbbox()
    if not bbox:
        return img

    x1, y1, x2, y2 = bbox
    w, h = img.size

    # juda kichik crop bo‘lsa — qo‘ymaslik
    if (x2 - x1) < w * 0.35 or (y2 - y1) < h * 0.35:
        return img

    pad_x = int(w * 0.03)
    pad_y = int(h * 0.03)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w, x2 + pad_x)
    y2 = min(h, y2 + pad_y)
    return img.crop((x1, y1, x2, y2))


# =========================================================
# 8) PROMPT (ANTI-UI + LINE-BY-LINE)
# =========================================================
def build_prompt(lang_hint: str, era_hint: str) -> str:
    lh = lang_hint or "Noma'lum"
    eh = era_hint or "Noma'lum"
    return f"""
Siz paleograf-ekspertsiz. Sizga bitta sahifa bo‘yicha bir nechta rasm beriladi:
- 1-rasm: to‘liq sahifa
- qolganlari: zoom/crop (matnni aniq o‘qish uchun)

MUHIM QOIDALAR:
- Faqat qo‘lyozma/kitob sahifasidagi matnni o‘qing.
- Agar rasm UI skrinshot, Word hujjat, menyu, tugma, interfeys bo‘lsa:
  "BU QO‘LYOZMA SAHIFASI EMAS" deb yozing va to‘xtang.
- UI/menyu so‘zlarini (ManuscriptAI, Word, PDF, button, sidebar, Demo rejim, report va h.k.)
  transliteratsiya QILMANG.
- Hech narsa uydirmang. O‘qilmagan joy: [o‘qilmadi] yoki [?].
- Matnni satrma-satr yozing (har satr alohida qatorda).
- Hech bir so‘zni tashlab ketmang (zoom/croplardan foydalaning).
- QAYTA TEKSHIRUV: javobda 0), 1), 2), 3) bo‘limlari majburiy.

HINT:
- Til taxmini: {lh}
- Xat uslubi taxmini: {eh}

FORMATNI QATTIQ SAQLANG:

0) Tashxis:
Til: <...>
Xat uslubi: <...>
Ishonchlilik: Yuqori/O‘rtacha/Past
Sahifa turi: Qo‘lyozma / Bosma / UI-skrinshot / Noma'lum

1) Transliteratsiya:
<faqat qo‘lyozma matni, satrma-satr>

2) To‘g‘ridan-to‘g‘ri tarjima:
<to‘liq, oddiy o‘zbekcha>

3) Izoh:
<kontekst + noaniq joylar ro‘yxati (qator raqami bilan)>
""".strip()

def looks_like_ui_output(text: str) -> bool:
    t = (text or "").lower()
    bad = ["microsoft word", "manuscriptai", "demo rejim", "pdf render", "button", "sidebar", "report", "streamlit"]
    return any(x in t for x in bad)

def too_short(text: str) -> bool:
    return len((text or "").strip()) < 500


# =========================================================
# 9) PDF RENDER
# =========================================================
@st.cache_data(show_spinner=False, max_entries=12)
def render_pdf_pages(file_bytes: bytes, max_pages: int, scale: float):
    pdf = pdfium.PdfDocument(file_bytes)
    out = []
    try:
        n = min(len(pdf), max_pages)
        for i in range(n):
            out.append(pdf[i].render(scale=scale).to_pil())
    finally:
        try:
            pdf.close()
        except Exception:
            pass
    return out


# =========================================================
# 10) WORD EXPORT (MODEL ROW YO‘Q)
# =========================================================
def _doc_set_normal_style(doc: Document):
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

def _add_cover(doc: Document, title: str, subtitle: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(20)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(subtitle)
    run2.font.size = Pt(12)

    doc.add_paragraph("")

def _add_meta_table(doc: Document, meta: dict):
    t = doc.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    for k, v in meta.items():
        row = t.add_row().cells
        row[0].text = str(k)
        row[1].text = str(v)

def add_plain_text(doc: Document, txt: str):
    for line in (txt or "").splitlines():
        doc.add_paragraph(line)

def build_word_report(app_name: str, meta: dict, pages: dict) -> bytes:
    doc = Document()
    _doc_set_normal_style(doc)
    _add_cover(doc, app_name, "Hisobot (Tashxis + Transliteratsiya + Tarjima + Izoh)")
    _add_meta_table(doc, meta)  # model qatori kiritilmaydi
    doc.add_page_break()

    for i, idx in enumerate(sorted(pages.keys())):
        doc.add_heading(f"Varaq {idx+1}", level=1)
        add_plain_text(doc, pages[idx] or "")
        if i != len(pages) - 1:
            doc.add_page_break()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# =========================================================
# 11) STATE
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "u_email" not in st.session_state:
    st.session_state.u_email = ""
if "last_fn" not in st.session_state:
    st.session_state.last_fn = None
if "imgs" not in st.session_state:
    st.session_state.imgs = []
if "results" not in st.session_state:
    st.session_state.results = {}


# =========================================================
# 12) SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)

    # Login (optional)
    if APP_PASSWORD:
        st.markdown("### 🔑 Tizimga kirish")
        st.caption("Kredit/Word eksport uchun kiring (agar yoqilgan bo‘lsa).")
        email_in = st.text_input("Email", value=st.session_state.u_email or "", placeholder="example@mail.com")
        pwd_in = st.text_input("Parol", type="password", placeholder="****")

        if st.button("KIRISH"):
            if (pwd_in or "") == APP_PASSWORD and email_in and "@" in email_in:
                st.session_state.auth = True
                st.session_state.u_email = email_in.strip().lower()
                st.success("Kirdingiz.")
                st.rerun()
            else:
                st.error("Email yoki parol xato.")

        if st.session_state.auth:
            st.divider()
            st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
            if db is not None:
                st.metric("💳 Kreditlar", safe_get_credits(st.session_state.u_email))
            else:
                st.caption("Supabase ulanmagan (kreditlar o‘chirilgan).")
            if st.button("🚪 CHIQISH"):
                st.session_state.auth = False
                st.session_state.u_email = ""
                st.rerun()
    else:
        st.info("Demo rejim: APP_PASSWORD yo‘q (majburiy emas).")

    st.divider()
    st.markdown("### 🧠 Hintlar")
    lang = st.selectbox("Asl matn tili (hint):", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=0)
    era = st.selectbox("Xat uslubi (hint):", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=0)

    st.divider()
    st.markdown("### 🧪 Skan sozlamalari")
    auto_crop = st.checkbox("Matn qutisini auto-crop (tavsiya)", value=True)
    brightness = st.slider("Yorqinlik:", 0.6, 2.0, 1.05)
    contrast = st.slider("Kontrast:", 0.6, 3.0, 1.45)
    sharpen = st.slider("Sharpen:", 0.0, 1.5, 1.0, 0.1)

    st.divider()
    st.markdown("### 📄 PDF")
    pdf_scale = st.slider("PDF render scale:", 1.4, 2.8, 2.1, 0.1)
    preview_max_pages = st.slider("Preview max sahifa:", 1, 120, 40)

    st.divider()
    st.caption(f"Model: **{MODEL_NAME}** (o‘zgartirilmagan)")


# =========================================================
# 13) MAIN
# =========================================================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qo‘lyozmani yuklang → AI yordamida o‘qish / tarjima / izoh.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Faylni yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")
if uploaded_file is None:
    st.stop()

# Load file -> images
if st.session_state.last_fn != uploaded_file.name:
    with st.spinner("Preparing..."):
        file_bytes = uploaded_file.getvalue()
        imgs = []

        if uploaded_file.type == "application/pdf":
            imgs = render_pdf_pages(file_bytes, max_pages=preview_max_pages, scale=pdf_scale)
        else:
            imgs = [Image.open(io.BytesIO(file_bytes))]

        st.session_state.imgs = imgs
        st.session_state.results = {}
        st.session_state.last_fn = uploaded_file.name
        gc.collect()

# Preprocess
processed_imgs = []
for img in st.session_state.imgs:
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    if sharpen > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(120 * sharpen), threshold=2))
    if auto_crop:
        img = auto_crop_text_region(img)
    processed_imgs.append(img)

total_pages = len(processed_imgs)
st.caption(f"Yuklandi: **{total_pages}** sahifa (preview limit: {preview_max_pages}).")

# Select pages
if total_pages <= 30:
    selected = st.multiselect(
        "Sahifalarni tanlang:",
        options=list(range(total_pages)),
        default=[0] if total_pages else [],
        format_func=lambda x: f"{x+1}-sahifa",
    )
else:
    spec = st.text_input("Sahifalar (masalan: 1-5, 9, 12-20):", value="1")
    def parse_pages(spec_text: str, max_n: int):
        spec_text = (spec_text or "").strip()
        if not spec_text:
            return [0] if max_n > 0 else []
        out = set()
        for part in [p.strip() for p in spec_text.split(",") if p.strip()]:
            try:
                if "-" in part:
                    a, b = part.split("-", 1)
                    a, b = int(a.strip()), int(b.strip())
                    if a > b:
                        a, b = b, a
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
    selected = parse_pages(spec, total_pages)

# Preview thumbnails
if selected and not st.session_state.results:
    cols = st.columns(min(4, len(selected)))
    for i, idx in enumerate(selected[:16]):
        with cols[i % len(cols)]:
            st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", use_container_width=True)

# Run analysis
if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
    if not selected:
        st.warning("Avval sahifa tanlang.")
        st.stop()

    prompt = build_prompt("" if lang == "Noma'lum" else lang, "" if era == "Noma'lum" else era)

    total = len(selected)
    done = 0
    bar = st.progress(0.0)

    for idx in selected:
        # RPM/429'ni kamaytirish uchun mayda jitter
        time.sleep(random.uniform(0.4, 0.9))

        with st.status(f"Sahifa {idx+1} tahlil qilinmoqda...") as s:
            try:
                # Credits (faqat auth + db bo‘lsa)
                if st.session_state.auth and db is not None:
                    # kredit yetmasa ham app yiqilmasin — faqat ogohlantiramiz
                    if safe_get_credits(st.session_state.u_email) <= 0:
                        s.update(label="Kredit tugagan", state="error")
                        st.warning("Kredit tugagan. Demo rejimda davom eting yoki kredit qo‘shing.")
                        done += 1
                        bar.progress(done / max(total, 1))
                        continue

                img = processed_imgs[idx]
                payloads = build_payloads_full_and_tiles(img)
                parts = [prompt, *payloads]

                text = generate_with_retry(parts, max_tokens=4096, temperature=0.15).strip()

                # Quality gate: UI chiqsa yoki juda qisqa bo‘lsa 1 marta qat’iy retry
                if looks_like_ui_output(text) or too_short(text):
                    strict = prompt + "\n\nQATTIQ: UI/Word/PDF/report so‘zlarini yozmang. Faqat qo‘lyozma ichidagi matn!"
                    text2 = generate_with_retry([strict, *payloads], max_tokens=4096, temperature=0.10).strip()
                    if text2:
                        text = text2

                st.session_state.results[idx] = text

                # decrement credit
                if st.session_state.auth and db is not None:
                    safe_decrement_credit(st.session_state.u_email, 1)

                s.update(label="Tayyor!", state="complete")

            except Exception as e:
                s.update(label="Xatolik", state="error")
                st.error(f"Xato: {e}")

        done += 1
        bar.progress(done / max(total, 1))

    st.rerun()

# Results
if st.session_state.results:
    st.divider()
    st.subheader("Natija")

    # Copy button (global)
    all_text = "\n\n".join(
        [f"--- VARAQ {i+1} ---\n{st.session_state.results[i]}" for i in sorted(st.session_state.results.keys())]
    )
    copy_html = f"""
    <button id="copy-btn" style="padding:10px 16px;border-radius:10px;cursor:pointer;font-weight:800;">
      📋 Natijani nusxalash
    </button>
    <script>
      const txt = {repr(all_text)};
      const btn = document.getElementById('copy-btn');
      btn.onclick = () => {{
        navigator.clipboard.writeText(txt).then(() => {{
          btn.innerText = "✅ Nusxalandi!";
          setTimeout(() => btn.innerText = "📋 Natijani nusxalash", 1800);
        }});
      }};
    </script>
    """
    components.html(copy_html, height=55)

    for idx in sorted(st.session_state.results.keys()):
        st.markdown(f"### 📖 Varaq {idx+1}")
        c1, c2 = st.columns([1, 1.35], gap="large")

        with c1:
            # sticky image
            b = io.BytesIO()
            processed_imgs[idx].save(b, format="JPEG", quality=90)
            b64 = base64.b64encode(b.getvalue()).decode("utf-8")
            st.markdown(
                f"""
                <div class="sticky-preview">
                  <img src="data:image/jpeg;base64,{b64}" alt="page {idx+1}" />
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c2:
            res = st.session_state.results[idx] or ""
            st.markdown(f"<div class='result-box'>{html.escape(res)}</div>", unsafe_allow_html=True)
            st.session_state.results[idx] = st.text_area(
                f"Tahrirlash ({idx+1}):",
                value=res,
                height=260,
                key=f"edit_{idx}",
            )

        st.markdown("---")

    # Word export (auth bo‘lsa ham, bo‘lmasa ham ruxsat berishingiz mumkin;
    # xohlasangiz faqat auth bo‘lsin deb shu yerga shart qo‘ying)
    meta = {
        "Hujjat": st.session_state.last_fn or "",
        "Sana": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "Sahifalar": ", ".join(str(i + 1) for i in sorted(st.session_state.results.keys())),
        "Email": st.session_state.u_email if st.session_state.auth else "Mehmon",
    }
    doc_bytes = build_word_report("Manuscript AI Center", meta, st.session_state.results)
    st.download_button("📥 Word hisobotni yuklab olish", doc_bytes, file_name="report.docx")

gc.collect()
