import base64
import gc
import html
import io
import random
import re
import threading
import time
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import streamlit as st

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pypdfium2 as pdfium

# Optional (Word export / Supabase)
try:
    from docx import Document
    from docx.shared import Pt

    WORD_OK = True
except Exception:
    WORD_OK = False

try:
    from supabase import create_client

    SUPABASE_LIB_OK = True
except Exception:
    SUPABASE_LIB_OK = False


# =========================================================
# 1) APP CONFIG
# =========================================================
st.set_page_config(
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# 2) CONSTANTS (MODEL LOCKED - DO NOT CHANGE)
# =========================================================
MODEL_NAME = "gemini-flash-latest"  # ✅ To'g'ri model nomi

# Rate-limit safety
SAFE_RPM_DEFAULT = 8
RATE_WINDOW_SEC = 60
MAX_RETRIES = 6

# Output length - OSHIRILDI (tahlil batafsil bo'lishi uchun)
MAX_OUT_TOKENS = 8192  # ✅ 4096 → 8192 (2x ko'proq)

# Image sizing (keep moderate for speed)
FULL_MAX_SIDE = 1700
CROP_MAX_SIDE = 1900
TILE_MAX_SIDE = 1800

JPEG_QUALITY_FULL = 85  # ✅ 80 → 85 (aniqroq rasm)
JPEG_QUALITY_CROP = 87  # ✅ 82 → 87
JPEG_QUALITY_TILE = 87  # ✅ 82 → 87

# PDF
PDF_SCALE_DEFAULT = 2.5  # ✅ 2.2 → 2.5 (yuqori sifat)

# Demo limitations (if no auth)
DEMO_LIMIT_PAGES = 3

# Adaptive payload thresholds - YUMSHATILDI (ko'proq heavy mode ishlatish uchun)
MAX_QMARKS_LIGHT = 12  # ✅ 18 → 12 (tezroq heavy'ga o'tadi)
MIN_TEXT_LEN_LIGHT = 400  # ✅ 320 → 400 (juda qisqa bo'lsa heavy)
MAX_RETRY_PER_PAGE = 2  # ✅ 1 → 2 (ko'proq urinish)


# =========================================================
# 3) THEME (DARK_GOLD)
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
  margin: 0 !important;
  padding: 0 !important;
}}
.stApp, div[data-testid="stAppViewContainer"] {{
  background: var(--app-bg) !important;
  min-height: 100vh !important;
}}
div[data-testid="stAppViewContainer"] .main .block-container {{
  padding-top: 3.0rem !important;
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

h1, h2, h3 {{
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
  font-weight: 900 !important;
  width: 100% !important;
  padding: 11px 12px !important;
  border: 1px solid var(--gold) !important;
  border-radius: 12px !important;
  box-shadow: 0 10px 22px rgba(0,0,0,0.25) !important;
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

.result-box {{
  background: var(--card) !important;
  color: var(--card-text) !important;
  padding: 18px !important;
  border-radius: 16px !important;
  border-left: 10px solid var(--gold) !important;
  box-shadow: 0 10px 28px rgba(0,0,0,0.20) !important;
  line-height: 1.75;
}}

.sticky-preview {{
  position: sticky;
  top: 4.6rem;
  border-radius: 14px;
  border: 2px solid var(--gold);
  overflow: hidden;
  box-shadow: 0 14px 35px rgba(0,0,0,0.22);
  background: rgba(0,0,0,0.15);
  max-height: 560px;
}}
.sticky-preview img {{
  width: 100%;
  height: 560px;
  object-fit: contain;
  display: block;
}}

.small-muted {{
  color: var(--muted);
  font-size: 13px;
}}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# 4) SECRETS LOADING (SAFE)
# =========================================================
def _get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


GEMINI_API_KEY = _get_secret("GEMINI_API_KEY", "")
APP_PASSWORD = _get_secret("APP_PASSWORD", "")

SUPABASE_URL = _get_secret("SUPABASE_URL", "")
SUPABASE_KEY = _get_secret("SUPABASE_KEY", "")

SUPABASE_ENABLED = bool(SUPABASE_LIB_OK and SUPABASE_URL and SUPABASE_KEY)


@st.cache_resource
def get_db():
    if not SUPABASE_ENABLED:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None


db = get_db()

if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY topilmadi. Streamlit secrets'ga GEMINI_API_KEY qo'ying.")
    st.stop()


# =========================================================
# 5) GEMINI INIT (MODEL LOCKED)
# =========================================================
genai.configure(api_key=GEMINI_API_KEY)


@st.cache_resource
def get_model():
    # ⚠️ Model nomi qat'iy (o'zgartirmang)
    return genai.GenerativeModel(model_name=MODEL_NAME)


model = get_model()


# =========================================================
# 6) GLOBAL RATE LIMITER (PERSISTENT across reruns)
# =========================================================
class RateLimiter:
    def __init__(self, rpm: int, window_sec: int = 60):
        self.rpm = max(1, int(rpm))
        self.window = int(window_sec)
        self.lock = threading.Lock()
        self.ts = deque()  # timestamps

    def set_rpm(self, rpm: int):
        with self.lock:
            self.rpm = max(1, int(rpm))

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
            time.sleep(max(0.35, sleep_for))


@st.cache_resource
def get_limiter():
    # default rpm set later from slider via set_rpm()
    return RateLimiter(SAFE_RPM_DEFAULT, RATE_WINDOW_SEC)


limiter = get_limiter()


def _parse_retry_seconds(err_msg: str) -> Optional[float]:
    """
    Gemini error matnidan:
    - 'Please retry in 10.3s'
    - yoki 'retry_delay { seconds: 40 }'
    qiymatlarini ushlaydi.
    """
    if not err_msg:
        return None
    m = re.search(r"Please\s+retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s", err_msg, flags=re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    m2 = re.search(r"retry_delay\s*{\s*seconds:\s*([0-9]+)", err_msg, flags=re.IGNORECASE)
    if m2:
        try:
            return float(m2.group(1))
        except Exception:
            return None
    return None


def _looks_like_429(msg: str) -> bool:
    m = (msg or "").lower()
    return ("429" in m) or ("quota" in m) or ("rate" in m) or ("exceeded" in m)


def _looks_like_404(msg: str) -> bool:
    m = (msg or "").lower()
    return ("404" in m) and ("not found" in m or "not supported" in m or "model" in m)


def _looks_like_network(msg: str) -> bool:
    m = (msg or "").lower()
    return (
        ("timeout" in m)
        or ("temporarily" in m)
        or ("unavailable" in m)
        or ("connection" in m)
        or ("503" in m)
        or ("500" in m)
    )


def generate_with_retry(parts, max_tokens: int, tries: int = MAX_RETRIES) -> str:
    last_err = None
    for attempt in range(tries):
        try:
            limiter.wait_for_slot()
            resp = model.generate_content(
                parts,
                generation_config={
                    "max_output_tokens": int(max_tokens),
                    "temperature": 0.1,  # ✅ 0.15 → 0.1 (aniqroq)
                    "top_p": 0.95,  # ✅ Qo'shildi (diversifikatsiya)
                    "top_k": 40,  # ✅ Qo'shildi (variant cheklash)
                },
            )
            return getattr(resp, "text", "") or ""
        except Exception as e:
            last_err = e
            msg = str(e)

            if _looks_like_404(msg):
                raise RuntimeError(
                    f"AI xatosi: 404 (model not found/unsupported). Model: '{MODEL_NAME}'. "
                    f"Google AI Studio/Console'da shu model loyihangiz uchun mavjudligini tekshiring."
                ) from e

            if _looks_like_429(msg):
                retry_s = _parse_retry_seconds(msg)
                # API aytgan vaqtni hurmat qilamiz (eng ishonchli)
                if retry_s is None:
                    retry_s = min(70.0, (2 ** attempt) + random.uniform(1.0, 2.0))
                else:
                    retry_s = float(retry_s) + random.uniform(0.8, 1.8)
                time.sleep(max(1.0, retry_s))
                continue

            if _looks_like_network(msg):
                time.sleep(min(55.0, (2 ** attempt) + random.uniform(0.8, 2.0)))
                continue

            raise

    raise RuntimeError(f"So'rov bajarilmadi (429/Network). Oxirgi xato: {last_err}") from last_err


# =========================================================
# 7) IMAGE HELPERS
# =========================================================
def pil_to_jpeg_bytes(img: Image.Image, *, quality: int, max_side: int) -> bytes:
    img = img.convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > max_side:
        r = max_side / float(long_side)
        img = img.resize((max(1, int(w * r)), max(1, int(h * r))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(quality), optimize=True)
    return buf.getvalue()


def payload_from_bytes(img_bytes: bytes) -> dict:
    return {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}


def _bbox_is_too_small(bbox: Tuple[int, int, int, int], w: int, h: int) -> bool:
    x1, y1, x2, y2 = bbox
    bw = max(0, x2 - x1)
    bh = max(0, y2 - y1)
    return (bw < w * 0.40) or (bh < h * 0.40)


def _bbox_is_too_big(bbox: Tuple[int, int, int, int], w: int, h: int) -> bool:
    x1, y1, x2, y2 = bbox
    bw = max(0, x2 - x1)
    bh = max(0, y2 - y1)
    # deyarli butun sahifa bo'lsa crop foydasiz (va xatoli bo'lishi mumkin)
    return (bw > w * 0.96) and (bh > h * 0.96)


def auto_crop_text_region_safe(img: Image.Image) -> Image.Image:
    """
    Xavfsiz auto-crop:
    - grayscale -> autocontrast -> threshold -> invert -> bbox
    - bbox topilmasa: original
    - bbox juda kichik / juda katta bo'lsa: original
    - margin 6-8% (matn chetini yeb yubormaslik uchun)
    """
    img = img.convert("RGB")
    w, h = img.size

    im = img.convert("L")
    im = ImageOps.autocontrast(im)

    # threshold: matnni ajratish (barqarorroq)
    thr = 192
    bw = im.point(lambda p: 255 if p > thr else 0, mode="L")
    inv = ImageOps.invert(bw)

    bbox = inv.getbbox()
    if not bbox:
        return img

    if _bbox_is_too_small(bbox, w, h) or _bbox_is_too_big(bbox, w, h):
        return img

    x1, y1, x2, y2 = bbox

    # margin 7%
    mx = int(w * 0.07)
    my = int(h * 0.07)

    x1 = max(0, x1 - mx)
    y1 = max(0, y1 - my)
    x2 = min(w, x2 + mx)
    y2 = min(h, y2 + my)

    # safety re-check
    new_bbox = (x1, y1, x2, y2)
    if _bbox_is_too_small(new_bbox, w, h) or _bbox_is_too_big(new_bbox, w, h):
        return img

    return img.crop((x1, y1, x2, y2))


def build_payloads_light(img: Image.Image, enable_crop: bool) -> List[dict]:
    """
    Light mode: full + safe-crop (2 ta image).
    """
    img = img.convert("RGB")
    payloads: List[dict] = []

    full_bytes = pil_to_jpeg_bytes(img, quality=JPEG_QUALITY_FULL, max_side=FULL_MAX_SIDE)
    payloads.append(payload_from_bytes(full_bytes))

    if enable_crop:
        cropped = auto_crop_text_region_safe(img)
        crop_bytes = pil_to_jpeg_bytes(cropped, quality=JPEG_QUALITY_CROP, max_side=CROP_MAX_SIDE)
        payloads.append(payload_from_bytes(crop_bytes))

    return payloads


def build_payloads_heavy(img: Image.Image, enable_crop: bool) -> List[dict]:
    """
    Heavy mode: full + safe-crop + 2x2 tiles (6 ta image: full + crop + 4 tiles).
    """
    img = img.convert("RGB")
    payloads: List[dict] = []

    full_bytes = pil_to_jpeg_bytes(img, quality=JPEG_QUALITY_FULL, max_side=FULL_MAX_SIDE)
    payloads.append(payload_from_bytes(full_bytes))

    base = img
    if enable_crop:
        base = auto_crop_text_region_safe(img)
        crop_bytes = pil_to_jpeg_bytes(base, quality=JPEG_QUALITY_CROP, max_side=CROP_MAX_SIDE)
        payloads.append(payload_from_bytes(crop_bytes))

    # 2x2 tiles on base with small overlap
    bw, bh = base.size
    ox = int(bw * 0.06)
    oy = int(bh * 0.06)

    xs = [0, bw // 2]
    ys = [0, bh // 2]

    for yy in ys:
        for xx in xs:
            x1 = max(0, xx - ox)
            y1 = max(0, yy - oy)
            x2 = min(bw, xx + bw // 2 + ox)
            y2 = min(bh, yy + bh // 2 + oy)
            tile = base.crop((x1, y1, x2, y2))
            tb = pil_to_jpeg_bytes(tile, quality=JPEG_QUALITY_TILE, max_side=TILE_MAX_SIDE)
            payloads.append(payload_from_bytes(tb))

    return payloads


# =========================================================
# 8) PDF RENDER (cache_data)
# =========================================================
@st.cache_data(show_spinner=False, max_entries=48)
def render_pdf_page_bytes(file_bytes: bytes, page_index: int, scale: float) -> bytes:
    pdf = pdfium.PdfDocument(file_bytes)
    try:
        pil_img = pdf[page_index].render(scale=scale).to_pil().convert("RGB")
        return pil_to_jpeg_bytes(pil_img, quality=90, max_side=2600)
    finally:
        try:
            pdf.close()
        except Exception:
            pass


# =========================================================
# 9) PROMPT (YAXSHILANGAN - BATAFSIL TAHLIL)
# =========================================================
def build_prompt(lang_hint: str, era_hint: str) -> str:
    return f"""
Siz professional paleograf va qo'lyozma mutaxassisisiz. Sizga bitta sahifa bo'yicha bir nechta rasm beriladi:
- 1-rasm: to'liq sahifa
- qolganlari: zoom/crop/tiles (matnni ANIQ va BATAFSIL o'qish uchun)

⚠️ QATTIQ QOIDALAR:
1. Faqat qo'lyozma/kitob sahifasidagi matnni o'qing
2. Agar rasm UI skrinshot, Word hujjat, menyu, tugma, interfeys bo'lsa:
   "BU QO'LYOZMA SAHIFASI EMAS" deb yozing va to'xtang
3. UI/menyu so'zlarini (ManuscriptAI, Word, PDF, button, sidebar, demo rejim, export, report, streamlit va h.k.) transliteratsiya QILMANG
4. Hech narsa uydirmang - faqat ko'rinayotgan matn
5. O'qilmagan joy: [o'qilmadi] yoki [?]
6. Matnni satrma-satr yozing: har satr L1:, L2:, L3: ... bilan boshlang
7. HAR BIR SO'ZNI to'liq yozing - QISQARTIRMANG!
8. Har bir satrdagi BARCHA so'zlarni (oxirigacha) yozing
9. Zoom/crop rasmlardan MAKSIMAL foydalaning
10. Noaniq harflar bo'lsa: [shubhali: variant1/variant2]

📋 HINT:
- Til taxmini: {lang_hint or "Noma'lum"}
- Xat uslubi taxmini: {era_hint or "Noma'lum"}

📤 JAVOB FORMATI (QATTIQ RIOYA QILING):

0) Tashxis:
Til: <aniq til nomi>
Xat uslubi: <aniq xat turi va davri>
Ishonchlilik: Yuqori/O'rtacha/Past/Juda past
Sahifa turi: Qo'lyozma / Bosma / UI-skrinshot / Noma'lum
Sifat baholash: <rasm sifati, yorug'lik, kontrast haqida>
O'qilmaslik sababi (agar bo'lsa): <blur/rezolyutsiya past/soyalar/crop noto'g'ri/yirtiq/dog'lar>

1) Transliteratsiya (ASLIY XAT - HAR BIR SATR TO'LIQ):
L1: <birinchi satr to'liq, har bir so'z>
L2: <ikkinchi satr to'liq, har bir so'z>
L3: <uchinchi satr to'liq, har bir so'z>
L4: <to'rtinchi satr to'liq, har bir so'z>
... (BARCHA SATRLAR oxirigacha davom eting)

2) Lotin yozuvida (HAR BIR SATR TO'LIQ):
L1: <lotin yozuvida, har bir so'z transliteratsiya qilingan>
L2: <lotin yozuvida, har bir so'z transliteratsiya qilingan>
L3: <lotin yozuvida, har bir so'z transliteratsiya qilingan>
... (BARCHA SATRLAR)

3) To'liq va batafsil tarjima (ODDIY O'ZBEKCHA):
<Har bir satrning ma'nosi to'liq, tushunarli, batafsil tarjimasi>
<Hech narsa qoldirilmasin - to'liq tarjima>
<Agar tarixiy/arxaik so'zlar bo'lsa, izohlab tarjima qiling>

4) Keng izoh va kontekst:
<Tarixiy kontekst, davr, mavzu haqida ma'lumot>
<Noaniq o'qilgan so'zlar ro'yxati (L raqami bilan)>
<Grammatik tushuntirishlar (agar muhim bo'lsa)>
<Matn tuzilishi, uslubi haqida fikrlar>
<Qo'shimcha kuzatishlar va tavsiyalar>

⚠️ ESLATMA:
- Agar matn UMUMAN o'qilmasa: "⚠️ MATN O'QILMAYDI: [aniq sabab]"
- Agar juda kam o'qilsa: nima o'qilganini yozing va sabab tushuntiring
- QISQARTIRMANG - to'liq, batafsil, professional tahlil bering!
""".strip()


def looks_like_ui_output(text: str) -> bool:
    t = (text or "").lower()
    bad = [
        "microsoft word",
        "manuscriptai",
        "demo rejim",
        "pdf render",
        "button",
        "sidebar",
        "streamlit",
        "export",
        "report",
        "tizimga kirish",
        "kredit",
        "profil",
        "upload",
        "download",
    ]
    return any(x in t for x in bad)


def count_uncertain_marks(text: str) -> int:
    if not text:
        return 0
    t = text
    return t.count("[?]") + t.count("[o'qilmadi]") + t.count("[o'qilmadi]") + t.count("[oqilmadi]")


def is_low_quality_light(text: str) -> bool:
    """
    Yumshoq "light->heavy" trigger (ko'proq heavy ishlatish uchun).
    """
    if not text:
        return True
    if len(text.strip()) < MIN_TEXT_LEN_LIGHT:
        return True
    if count_uncertain_marks(text) >= MAX_QMARKS_LIGHT:
        return True
    return False


# =========================================================
# 10) WORD EXPORT
# =========================================================
def build_docx(pages_text: Dict[int, str]) -> bytes:
    doc = Document()
    try:
        style = doc.styles["Normal"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(12)
    except Exception:
        pass

    doc.add_paragraph("Manuscript AI Report")
    doc.add_paragraph(datetime.utcnow().isoformat())
    doc.add_paragraph("")

    for idx in sorted(pages_text.keys()):
        doc.add_paragraph(f"--- VARAQ {idx + 1} ---")
        doc.add_paragraph(pages_text[idx] or "")
        doc.add_paragraph("")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# =========================================================
# 11) SESSION STATE
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "u_email" not in st.session_state:
    st.session_state.u_email = ""
if "last_fn" not in st.session_state:
    st.session_state.last_fn = None
if "last_render_sig" not in st.session_state:
    st.session_state.last_render_sig = None
if "pages_jpeg" not in st.session_state:
    st.session_state.pages_jpeg = []
if "results" not in st.session_state:
    st.session_state.results = {}


# =========================================================
# 12) SIDEBAR (controls)
# =========================================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)

    # Login only if APP_PASSWORD exists
    if APP_PASSWORD:
        if not st.session_state.auth:
            st.markdown("### 🔑 Tizimga kirish")
            st.caption("Word eksport va qo'shimcha funksiyalar uchun.")
            email_in = st.text_input("Email", placeholder="example@mail.com")
            pwd_in = st.text_input("Parol", type="password", placeholder="****")
            if st.button("KIRISH"):
                if pwd_in == APP_PASSWORD and email_in and "@" in email_in:
                    st.session_state.auth = True
                    st.session_state.u_email = email_in.strip().lower()
                    st.rerun()
                else:
                    st.error("Email yoki parol xato.")
        else:
            st.markdown(f"**👤 {html.escape(st.session_state.u_email)}**")
            if st.button("🚪 Chiqish"):
                st.session_state.auth = False
                st.session_state.u_email = ""
                st.rerun()
    else:
        st.info("Demo rejim: APP_PASSWORD yo'q (majburiy emas).")

    st.divider()
    st.markdown("### 🧠 Hintlar")
    lang_hint = st.selectbox(
        "Asl matn tili (hint):",
        ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy", "O'zbekcha (eski)", "Turk"],
        index=0,
    )
    era_hint = st.selectbox(
        "Xat uslubi (hint):",
        ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy", "Naskh", "Divani"],
        index=0,
    )

    st.divider()
    st.markdown("### 🧪 Skan sozlamalari")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.6, 1.8, 1.1, 0.01)  # ✅ 1.05 → 1.1
    contrast = st.slider("Kontrast:", 0.8, 2.5, 1.5, 0.01)  # ✅ 1.45 → 1.5
    sharpen = st.slider("Sharpen (Unsharp):", 0.0, 1.5, 1.2, 0.1)  # ✅ 1.0 → 1.2

    st.divider()
    st.markdown("### 📄 PDF")
    pdf_scale = st.slider("PDF render scale:", 1.6, 3.2, PDF_SCALE_DEFAULT, 0.1)  # ✅ max 2.8→3.2
    preview_max_pages = st.slider("Preview max sahifa:", 1, 120, 40)

    st.divider()
    st.markdown("### 🛡 429 himoya")
    safe_rpm = st.slider("So'rov/min (xavfsiz):", 2, 14, SAFE_RPM_DEFAULT)

    st.caption("Tavsiya: 6–10 RPM. 14 faqat limit aniq bo'lsa.")
    enable_crop = st.checkbox("Matn qutisini auto-crop (tavsiya)", value=True)

    # Quality gate: UI va qisqa matn uchun
    enable_quality_gate = st.checkbox("Sifat nazorati (UI va qisqa matn uchun qayta urish)", value=True)

    # Apply rpm without recreating limiter
    limiter.set_rpm(safe_rpm)


# =========================================================
# 13) MAIN UI
# =========================================================
st.title("📜 Manuscript AI Center")
st.markdown(
    "<p class='small-muted' style='text-align:center;'>✨ Batafsil tahlil: 8192 token, yuqori sifat, adaptiv heavy mode ✨</p>",
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader("Faylni yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")
if uploaded_file is None:
    st.stop()

file_bytes = uploaded_file.getvalue()
file_id = f"{uploaded_file.name}|{len(file_bytes)}"
render_sig = f"{file_id}|scale={pdf_scale}|max={preview_max_pages}"

# Rebuild pages_jpeg if:
# - new file OR
# - pdf_scale / preview_max_pages changed (render_sig change)
if st.session_state.last_render_sig != render_sig:
    st.session_state.last_render_sig = render_sig
    st.session_state.last_fn = uploaded_file.name
    st.session_state.results = {}
    st.session_state.pages_jpeg = []

    if uploaded_file.type == "application/pdf":
        pdf = pdfium.PdfDocument(file_bytes)
        n_pages = min(len(pdf), int(preview_max_pages))
        pdf.close()

        pages: List[bytes] = []
        for i in range(n_pages):
            pages.append(render_pdf_page_bytes(file_bytes, i, float(pdf_scale)))
        st.session_state.pages_jpeg = pages
    else:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        jb = pil_to_jpeg_bytes(img, quality=90, max_side=2600)
        st.session_state.pages_jpeg = [jb]

    gc.collect()

total_pages = len(st.session_state.pages_jpeg)
st.caption(f"Yuklandi: **{total_pages}** sahifa (preview limit: {preview_max_pages}).")

# Page select
if total_pages <= 30:
    selected_indices = st.multiselect(
        "Sahifalarni tanlang:",
        options=list(range(total_pages)),
        default=[0] if total_pages else [],
        format_func=lambda x: f"{x + 1}-sahifa",
    )
else:
    spec = st.text_input("Sahifalar (masalan: 1-5, 9, 12-20):", value="1")
    chosen = set()
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                a = int(a)
                b = int(b)
                if a > b:
                    a, b = b, a
                for p in range(a, b + 1):
                    if 1 <= p <= total_pages:
                        chosen.add(p - 1)
            except Exception:
                pass
        else:
            try:
                p = int(part)
                if 1 <= p <= total_pages:
                    chosen.add(p - 1)
            except Exception:
                pass
    selected_indices = sorted(chosen) if chosen else ([0] if total_pages else [])

# Demo limit if not auth
if not st.session_state.auth and len(selected_indices) > DEMO_LIMIT_PAGES:
    st.warning(f"Demo rejim: maksimal {DEMO_LIMIT_PAGES} sahifa tahlil qilinadi.")
    selected_indices = selected_indices[:DEMO_LIMIT_PAGES]


def preprocess_pil_from_jpeg(jpeg_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(jpeg_bytes))
    img = ImageOps.exif_transpose(img)
    if rotate:
        img = img.rotate(rotate, expand=True)

    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)

    if sharpen > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(150 * sharpen), threshold=2))
    return img.convert("RGB")


# Prepare images for chosen pages (used for preview + analysis)
processed_imgs: Dict[int, Image.Image] = {
    idx: preprocess_pil_from_jpeg(st.session_state.pages_jpeg[idx]) for idx in selected_indices
}

# Preview thumbnails (before analysis)
if selected_indices and not st.session_state.results:
    cols = st.columns(min(len(selected_indices), 4))
    for i, idx in enumerate(selected_indices[:16]):
        with cols[i % min(len(cols), 4)]:
            st.image(processed_imgs[idx], caption=f"Varaq {idx + 1}", use_container_width=True)


# =========================================================
# 14) RUN ANALYSIS (YAXSHILANGAN - ADAPTIVE + HEAVY)
# =========================================================
def analyze_one_page(img: Image.Image, prompt: str, enable_crop_flag: bool, quality_gate_flag: bool) -> str:
    """
    YAXSHILANGAN STRATEGIYA:
    1) Light request (full + crop) - tez tahlil
    2) Agar UI chiqsa va quality_gate yoniq -> qayta urish (light mode)
    3) Agar matn juda qisqa yoki ko'p [?] bo'lsa -> HEAVY mode (full+crop+tiles)
    4) HEAVY mode bajarilgandan keyin yana past sifat bo'lsa -> ikkinchi HEAVY urinish
    """
    # --- LIGHT MODE (TEZKOR) ---
    payloads_light = build_payloads_light(img, enable_crop=enable_crop_flag)
    parts = [prompt] + payloads_light
    text = generate_with_retry(parts, max_tokens=MAX_OUT_TOKENS, tries=MAX_RETRIES).strip()

    # --- UI QUALITY GATE (UI uchun) ---
    if quality_gate_flag and looks_like_ui_output(text):
        strict = (
            prompt
            + "\n\n⚠️ QATTIQ OGOHLANTIRUV: UI/menyu so'zlarini transliteratsiya qilmang! "
            + "Faqat qo'lyozma ichidagi matnni o'qing! "
            + "Agar bu UI skrinshot bo'lsa: 'BU QO'LYOZMA SAHIFASI EMAS' deb yozing."
        )
        text2 = generate_with_retry([strict] + payloads_light, max_tokens=MAX_OUT_TOKENS, tries=MAX_RETRIES).strip()
        if text2:
            text = text2

    # --- ADAPTIVE HEAVY MODE (PAST SIFAT UCHUN) ---
    if (not looks_like_ui_output(text)) and is_low_quality_light(text):
        # HEAVY mode: 6 ta rasm (full + crop + 4 tiles)
        payloads_heavy = build_payloads_heavy(img, enable_crop=enable_crop_flag)
        heavy_prompt = (
            prompt
            + "\n\n✅ MUHIM: Sizga 6 ta rasm berildi - ularning BARCHASIDAN foydalaning! "
            + "Har bir tile'da yashirin matnlar bor - ularni ham o'qing! "
            + "BATAFSIL tahlil qiling - QISQARTIRMANG!"
        )
        text3 = generate_with_retry([heavy_prompt] + payloads_heavy, max_tokens=MAX_OUT_TOKENS, tries=MAX_RETRIES).strip()
        if text3:
            text = text3

        # --- IKKINCHI HEAVY URINISH (agar hali ham past sifat bo'lsa) ---
        if quality_gate_flag and is_low_quality_light(text3):
            ultra_prompt = (
                heavy_prompt
                + "\n\n🔥 OXIRGI URINISH: Maksimal diqqat! Har bir pixel'ni tekshiring! "
                + "Zoom rasmlardan MAKSIMAL foydalaning! "
                + "Shubhali harflar bo'lsa: [shubhali: variant1/variant2] formatda yozing!"
            )
            text4 = generate_with_retry([ultra_prompt] + payloads_heavy, max_tokens=MAX_OUT_TOKENS, tries=MAX_RETRIES).strip()
            if text4 and len(text4) > len(text3):
                text = text4

    return text


if st.button("✨ BATAFSIL AKADEMIK TAHLILNI BOSHLASH"):
    if not selected_indices:
        st.warning("Avval sahifani tanlang.")
        st.stop()

    p = build_prompt("" if lang_hint == "Noma'lum" else lang_hint, "" if era_hint == "Noma'lum" else era_hint)

    total = len(selected_indices)
    done = 0
    bar = st.progress(0.0)

    for idx in selected_indices:
        with st.status(f"Sahifa {idx + 1} tahlil qilinmoqda... (Light → Heavy adaptiv)", expanded=True) as s:
            try:
                img = processed_imgs[idx]

                s.update(label=f"📸 Sahifa {idx + 1}: Light mode...", state="running")
                text = analyze_one_page(img, p, enable_crop, enable_quality_gate)

                st.session_state.results[idx] = text

                word_count = len(text.split())
                s.update(label=f"✅ Tayyor! ({word_count} so'z)", state="complete")

            except Exception as e:
                st.session_state.results[idx] = f"❌ Xato: {e}"
                s.update(label="❌ Xatolik", state="error")

        done += 1
        bar.progress(done / max(1, total))

        time.sleep(random.uniform(0.8, 1.5))

    st.success("✅ Tahlil yakunlandi! Natijalarni ko'ring ⬇️")
    gc.collect()


# =========================================================
# 15) SHOW RESULTS (always render)
# =========================================================
if st.session_state.results:
    st.markdown("---")
    st.subheader("📋 Natijalar")

    for idx in sorted(st.session_state.results.keys()):
        res = st.session_state.results[idx]

        c1, c2 = st.columns([1, 1.35], gap="large")
        with c1:
            img = preprocess_pil_from_jpeg(st.session_state.pages_jpeg[idx])
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            st.markdown(
                f"<div class='sticky-preview'><img src='data:image/jpeg;base64,{b64}' alt='page {idx + 1}' /></div>",
                unsafe_allow_html=True,
            )

        with c2:
            st.markdown(f"#### 📖 Varaq {idx + 1}")

            safe = html.escape(res).replace("\n", "<br/>")
            st.markdown(f"<div class='result-box'>{safe}</div>", unsafe_allow_html=True)

            st.text_area("Tahrirlash:", value=res, height=320, key=f"edit_{idx}")

        st.markdown("---")

    # Word export
    if WORD_OK:
        colA, colB = st.columns([1, 1])
        with colA:
            st.caption("📥 Word eksport (docx) tayyor.")
        with colB:
            if st.button("📥 Word hisobot yaratish"):
                pages_text = {
                    i: st.session_state.get(f"edit_{i}", st.session_state.results[i])
                    for i in st.session_state.results.keys()
                }
                doc_bytes = build_docx(pages_text)
                st.download_button("⬇️ Yuklab olish (report.docx)", doc_bytes, "report.docx")
    else:
        st.info("Word eksport uchun python-docx kerak (serverda o'rnatilmagan bo'lishi mumkin).")

gc.collect()


