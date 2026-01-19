import streamlit as st
import streamlit.components.v1 as components

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium

import io
import gc
import base64
import time
import random
import re
import html
import json
import threading
from datetime import datetime
from collections import Counter, deque

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Supabase ixtiyoriy (secrets bo'lmasa ham app ishlaydi)
try:
    from supabase import create_client
except Exception:
    create_client = None


# =========================================================
# 1) CONFIG
# =========================================================
st.set_page_config(
    page_title="Manuscript AI Center",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# 2) LOCKED CONSTANTS
# =========================================================
MODEL_NAME = "gemini-flash-latest"  # ✅ FAQAT SHU (SIZ AYTGANSIZ)
DEMO_LIMIT_PAGES = 3
STARTER_CREDITS = 10
HISTORY_LIMIT = 20

# 429 ni kamaytirish uchun (sizda 15 RPM bo'lsa ham, xavfsizroq past ushlaymiz)
SAFE_RPM = 7            # 1 daqiqada maksimal so‘rov
RATE_WINDOW_SEC = 60
MAX_RETRIES = 7

# 1 sahifa = 1 request rejim uchun rasm paketlash:
JPEG_QUALITY_FULL = 80
JPEG_QUALITY_TILE = 82
FULL_MAX_SIDE = 2000
TILE_MAX_SIDE = 2400

PDF_SCALE_DEFAULT = 2.1
MAX_OUT_TOKENS = 4096   # flash-latest uchun odatda yetarli

BATCH_DELAY_RANGE = (0.5, 1.0)  # sahifa oralig'ida kichik pauza


# =========================================================
# 3) Minimal CSS (soddaroq, kam xato)
# =========================================================
st.markdown("""
<style>
html, body { background: #0b1220 !important; }
.stApp { background: #0b1220 !important; }
h1, h2, h3 { color: #d4af37 !important; }
.stMarkdown, .stCaption, label { color: #c7d0e6 !important; }
textarea { background: #fdfaf1 !important; color: #000 !important; }
</style>
""", unsafe_allow_html=True)


# =========================================================
# 4) SERVICES (Gemini + optional Supabase)
# =========================================================
def _get_secret(key: str, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

GEMINI_API_KEY = _get_secret("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY topilmadi. Streamlit secrets'ga qo‘ying.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

@st.cache_resource
def get_model():
    # google-generativeai SDK (sizda shuni requirements bor)
    return genai.GenerativeModel(model_name=MODEL_NAME)

model = get_model()


@st.cache_resource
def get_db():
    if create_client is None:
        return None
    url = _get_secret("SUPABASE_URL", "")
    key = _get_secret("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None

db = get_db()


# =========================================================
# 5) RATE LIMITER (429 ni oldini olish)
# =========================================================
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
                sleep_for = (self.window - (now - self.ts[0])) + 0.25
            time.sleep(max(0.35, sleep_for))

@st.cache_resource
def get_limiter():
    return RateLimiter(SAFE_RPM, RATE_WINDOW_SEC)

limiter = get_limiter()


def _is_429(msg: str) -> bool:
    m = (msg or "").lower()
    return ("429" in m) or ("quota" in m) or ("rate" in m) or ("resource has been exhausted" in m)

def _is_404(msg: str) -> bool:
    m = (msg or "").lower()
    return ("404" in m) and ("not found" in m or "models/" in m)

def _is_5xx_or_net(msg: str) -> bool:
    m = (msg or "").lower()
    return any(x in m for x in ["500", "502", "503", "504", "timeout", "timed out", "connection", "network", "ssl"])


def generate_with_retry(parts, max_tokens: int = MAX_OUT_TOKENS, tries: int = MAX_RETRIES) -> str:
    last_err = None
    for attempt in range(tries):
        try:
            limiter.wait_for_slot()
            resp = model.generate_content(
                parts,
                generation_config={"max_output_tokens": int(max_tokens), "temperature": 0.15}
            )
            return getattr(resp, "text", "") or ""
        except Exception as e:
            last_err = e
            msg = str(e)

            if _is_404(msg):
                raise RuntimeError(
                    f"AI xatosi: 404. Model topilmadi. Sizning model nomingiz FAQAT '{MODEL_NAME}' bo‘lishi kerak."
                ) from e

            if _is_429(msg) or _is_5xx_or_net(msg):
                # exponential backoff + jitter
                time.sleep(min(60, (2 ** attempt)) + random.uniform(0.6, 1.8))
                continue

            raise
    raise RuntimeError(f"So‘rov bajarilmadi (429/Network). Oxirgi xato: {last_err}") from last_err


# =========================================================
# 6) STATE
# =========================================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""
if "last_fn" not in st.session_state: st.session_state.last_fn = None
if "page_bytes" not in st.session_state: st.session_state.page_bytes = []
if "results" not in st.session_state: st.session_state.results = {}
if "warn_db" not in st.session_state: st.session_state.warn_db = False
if "running" not in st.session_state: st.session_state.running = False


# =========================================================
# 7) IMAGE/PDF HELPERS
# =========================================================
def pil_to_jpeg_bytes(img: Image.Image, quality: int, max_side: int) -> bytes:
    img = img.convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > max_side:
        ratio = max_side / float(long_side)
        img = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(quality), optimize=True)
    return buf.getvalue()

@st.cache_data(show_spinner=False, max_entries=16)
def render_pdf_pages_to_bytes(file_bytes: bytes, max_pages: int, scale: float):
    pdf = pdfium.PdfDocument(file_bytes)
    out = []
    try:
        n = min(len(pdf), int(max_pages))
        for i in range(n):
            pil_img = pdf[i].render(scale=float(scale)).to_pil()
            out.append(pil_to_jpeg_bytes(pil_img, quality=JPEG_QUALITY_FULL, max_side=FULL_MAX_SIDE))
    finally:
        try:
            pdf.close()
        except Exception:
            pass
    return out

@st.cache_data(show_spinner=False, max_entries=256)
def preprocess_bytes(img_bytes: bytes, brightness: float, contrast: float, rotate: int, sharpen: float) -> bytes:
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageOps.exif_transpose(img)
    if rotate:
        img = img.rotate(int(rotate), expand=True)

    img = ImageEnhance.Brightness(img).enhance(float(brightness))
    img = ImageEnhance.Contrast(img).enhance(float(contrast))

    if sharpen > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(120 * float(sharpen)), threshold=2))

    return pil_to_jpeg_bytes(img, quality=JPEG_QUALITY_FULL, max_side=FULL_MAX_SIDE)

def parse_pages(spec: str, max_n: int):
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

def _payload(img_bytes: bytes) -> dict:
    return {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}

def build_payloads_for_one_request(img_bytes: bytes):
    """
    ✅ 1 request uchun: 1 ta full + 2 ta zoom (left/right) yoki 2x2 tiles.
    Maqsad: matndan so‘z qolib ketmasin.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    aspect = w / max(h, 1)

    payloads = []
    payloads.append(_payload(pil_to_jpeg_bytes(img, quality=JPEG_QUALITY_FULL, max_side=FULL_MAX_SIDE)))

    # Juda keng sahifa bo‘lsa (kitob yoyilmasi) => left+right
    if aspect >= 1.25:
        left = img.crop((0, 0, w // 2, h))
        right = img.crop((w // 2, 0, w, h))
        payloads.append(_payload(pil_to_jpeg_bytes(left, quality=JPEG_QUALITY_TILE, max_side=TILE_MAX_SIDE)))
        payloads.append(_payload(pil_to_jpeg_bytes(right, quality=JPEG_QUALITY_TILE, max_side=TILE_MAX_SIDE)))
        return payloads

    # 2x2 tiles (ozgina overlap bilan)
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
            payloads.append(_payload(pil_to_jpeg_bytes(tile, quality=JPEG_QUALITY_TILE, max_side=TILE_MAX_SIDE)))

    return payloads


# =========================================================
# 8) OPTIONAL SUPABASE (credits/logs/reports) – xato qilsa ham app to‘xtamaydi
# =========================================================
def ensure_profile(email: str) -> None:
    if db is None:
        return
    try:
        existing = db.table("profiles").select("email,credits").eq("email", email).limit(1).execute()
        if existing.data:
            return
        db.table("profiles").insert({"email": email, "credits": STARTER_CREDITS}).execute()
    except Exception:
        st.session_state.warn_db = True

def get_credits(email: str) -> int:
    if db is None:
        return 0
    try:
        r = db.table("profiles").select("credits").eq("email", email).single().execute()
        return int(r.data["credits"]) if r.data and "credits" in r.data else 0
    except Exception:
        st.session_state.warn_db = True
        return 0

def consume_credit_safe(email: str, n: int = 1) -> bool:
    if db is None:
        return True
    try:
        r = db.rpc("consume_credits", {"p_email": email, "p_n": n}).execute()
        return bool(r.data)
    except Exception:
        pass
    try:
        cur = get_credits(email)
        if cur < n:
            return False
        newv = cur - n
        upd = db.table("profiles").update({"credits": newv}).eq("email", email).eq("credits", cur).execute()
        return bool(upd.data)
    except Exception:
        st.session_state.warn_db = True
        return False

def refund_credit_safe(email: str, n: int = 1) -> None:
    if db is None:
        return
    try:
        db.rpc("refund_credits", {"p_email": email, "p_n": n}).execute()
        return
    except Exception:
        pass
    try:
        cur = get_credits(email)
        db.table("profiles").update({"credits": cur + n}).eq("email", email).eq("credits", cur).execute()
    except Exception:
        st.session_state.warn_db = True

def save_report(email: str, doc_name: str, page_index: int, result_text: str) -> None:
    if db is None:
        return
    try:
        db.table("reports").upsert(
            {
                "email": email,
                "doc_name": doc_name,
                "page_index": int(page_index),
                "result_text": result_text,
                "updated_at": datetime.utcnow().isoformat()
            },
            on_conflict="email,doc_name,page_index"
        ).execute()
    except Exception:
        st.session_state.warn_db = True

def load_reports(email: str, doc_name: str) -> dict:
    if db is None:
        return {}
    try:
        r = db.table("reports").select("page_index,result_text") \
            .eq("email", email).eq("doc_name", doc_name).limit(500).execute()
        out = {}
        for row in (r.data or []):
            out[int(row["page_index"])] = row.get("result_text") or ""
        return out
    except Exception:
        st.session_state.warn_db = True
        return {}


# =========================================================
# 9) PROMPTS (1 REQUEST = translit + tarjima + izoh)
# =========================================================
def build_one_call_prompt(hint_lang: str, hint_era: str) -> str:
    hl = hint_lang or "yo‘q"
    he = hint_era or "yo‘q"
    return (
        "Siz qo‘lyozma (manuscript) o‘qish va tarjima bo‘yicha mutaxassissiz.\n"
        "Sizga BIR SAHIFAGA tegishli bir nechta rasm beriladi: 1-rasm full, qolganlari zoom/tiles.\n"
        "Vazifa: zoom/tilesdan foydalanib MATNNI maksimal to‘liq o‘qing.\n\n"
        "QOIDALAR (juda muhim):\n"
        "- Hech narsa uydirmang.\n"
        "- O‘qilmagan joy: [o‘qilmadi] yoki [?].\n"
        "- Hech bir so‘zni tashlab ketmang.\n"
        "- Har satr alohida qator.\n"
        "- Ism/son/sana/joylarni aynan ko‘ringanidek saqlang.\n\n"
        f"HINT: til='{hl}', xat uslubi='{he}'.\n\n"
        "CHIQISH FORMAT (aniq shunday, bo‘limlarni tashlab ketmang):\n"
        "0) Tashxis:\n"
        "Til: <aniqlangan yoki Noma'lum>\n"
        "Xat uslubi: <aniqlangan yoki Noma'lum>\n"
        "Ishonchlilik: <Yuqori/O‘rtacha/Past>\n\n"
        "1) Transliteratsiya:\n"
        "<satrma-satr, maksimal to‘liq>\n\n"
        "2) To‘g‘ridan-to‘g‘ri tarjima:\n"
        "<oddiy o‘zbekcha, to‘liq>\n\n"
        "6) Izoh:\n"
        "<kontekst; noaniq joylarni ehtiyotkor izohlang>\n"
    )

def _has_sections(text: str) -> bool:
    t = (text or "").lower()
    return ("1) transliteratsiya" in t) and ("2) to" in t) and ("6) izoh" in t)

def _extract_translit(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"1\)\s*Transliteratsiya\s*:?\s*\n([\s\S]*?)(?:\n\s*2\)\s*To|$)", text, flags=re.IGNORECASE)
    return (m.group(1).strip() if m else "")

def build_text_only_analyze_prompt(translit: str) -> str:
    return (
        "Siz Manuscript AI tarjimonisiz.\n"
        "Vazifa: faqat 2) va 6) bo‘limini yozing.\n"
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


# =========================================================
# 10) WORD EXPORT
# =========================================================
def _doc_set_normal_style(doc: Document):
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

def _add_cover(doc: Document, title: str, subtitle: str):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title); run.bold = True; run.font.size = Pt(20)
    p2 = doc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(subtitle); run2.font.size = Pt(12)
    doc.add_paragraph("")

def _add_meta_table(doc: Document, meta: dict):
    t = doc.add_table(rows=0, cols=2); t.style = "Table Grid"
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
    _add_cover(doc, app_name, "Hisobot (Transliteratsiya + Tarjima + Izoh)")
    _add_meta_table(doc, meta)
    doc.add_page_break()

    for j, idx in enumerate(sorted(pages.keys())):
        doc.add_heading(f"Varaq {idx+1}", level=1)
        add_plain_text(doc, pages[idx] or "")
        if j != len(pages) - 1:
            doc.add_page_break()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def _extract_diag(text: str) -> dict:
    def pick(rx):
        m = re.search(rx, text or "", flags=re.IGNORECASE)
        return (m.group(1).strip() if m else "")
    return {
        "til": pick(r"Til\s*:\s*(.+)"),
        "xat": pick(r"Xat\s*uslubi\s*:\s*(.+)"),
        "conf": pick(r"Ishonchlilik\s*:\s*(.+)")
    }

def aggregate_detected_meta(results: dict) -> dict:
    til_list, xat_list, conf_list = [], [], []
    for _, txt in results.items():
        d = _extract_diag(txt or "")
        if d["til"] and "noma" not in d["til"].lower(): til_list.append(d["til"])
        if d["xat"] and "noma" not in d["xat"].lower(): xat_list.append(d["xat"])
        if d["conf"]: conf_list.append(d["conf"])
    til = Counter(til_list).most_common(1)[0][0] if til_list else "Noma'lum"
    xat = Counter(xat_list).most_common(1)[0][0] if xat_list else "Noma'lum"
    conf = Counter(conf_list).most_common(1)[0][0] if conf_list else ""
    return {"til": til, "xat": xat, "conf": conf}


# =========================================================
# 11) SIDEBAR (soddaroq)
# =========================================================
with st.sidebar:
    st.markdown("## 📜 MS AI PRO")
    st.caption(f"Model: **{MODEL_NAME}** (locked)")

    st.markdown("### ✉️ Email bilan kirish (ixtiyoriy)")
    email_in = st.text_input("Email", value=(st.session_state.u_email or ""), placeholder="example@mail.com")

    if st.button("KIRISH"):
        email = (email_in or "").strip().lower()
        if not email or "@" not in email:
            st.error("Emailni to‘g‘ri kiriting.")
        else:
            st.session_state.auth = True
            st.session_state.u_email = email
            ensure_profile(email)
            st.rerun()

    if st.session_state.auth:
        credits = get_credits(st.session_state.u_email)
        st.info(f"👤 {st.session_state.u_email}\n\nKredit: {credits} sahifa")
        if st.button("CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = ""
            st.rerun()

    if st.session_state.warn_db:
        st.warning("Supabase/DB muammo bo‘lishi mumkin. App baribir ishlaydi.")

    st.divider()
    st.markdown("### 🧠 Hintlar")
    auto_detect = st.checkbox("Avto aniqlash (tavsiya)", value=True)
    lang = st.selectbox("Taxminiy til (hint):", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=0)
    era = st.selectbox("Taxminiy xat (hint):", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=0)

    st.divider()
    st.markdown("### 🧪 Skan sozlamalari")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.05)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.45)
    sharpen = st.slider("Sharpen:", 0.0, 1.5, 1.0, 0.1)

    st.divider()
    scale = st.slider("PDF render scale:", 1.4, 2.8, PDF_SCALE_DEFAULT, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 200, 40)

    st.caption("429 bo‘lsa: bu limit. Kod faqat sekinlashtiradi va qayta urinadi.")


# =========================================================
# 12) MAIN UI
# =========================================================
st.title("📜 Manuscript AI Center")
st.caption("PDF/rasm yuklang → sahifani tanlang → 1 request bilan transliteratsiya + tarjima + izoh.")

uploaded_file = st.file_uploader("Faylni yuklang", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file is None:
    st.stop()

# Load file bytes and render pages
if st.session_state.last_fn != uploaded_file.name:
    with st.spinner("Fayl tayyorlanmoqda..."):
        file_bytes = uploaded_file.getvalue()
        if uploaded_file.type == "application/pdf":
            pages = render_pdf_pages_to_bytes(file_bytes, max_pages=max_pages, scale=scale)
        else:
            img = Image.open(io.BytesIO(file_bytes))
            pages = [pil_to_jpeg_bytes(img, quality=JPEG_QUALITY_FULL, max_side=FULL_MAX_SIDE)]

        st.session_state.page_bytes = pages
        st.session_state.last_fn = uploaded_file.name
        st.session_state.results = {}
        st.session_state.warn_db = False
        gc.collect()

        if st.session_state.auth and st.session_state.u_email:
            restored = load_reports(st.session_state.u_email, st.session_state.last_fn)
            if restored:
                st.session_state.results.update(restored)

processed_pages = [
    preprocess_bytes(b, brightness=brightness, contrast=contrast, rotate=rotate, sharpen=sharpen)
    for b in st.session_state.page_bytes
]
total_pages = len(processed_pages)
st.success(f"Yuklandi: {total_pages} sahifa (preview limit: {max_pages}).")

if total_pages <= 30:
    selected_indices = st.multiselect(
        "Sahifalarni tanlang:",
        options=list(range(total_pages)),
        default=[0] if total_pages else [],
        format_func=lambda x: f"{x+1}-sahifa"
    )
else:
    page_spec = st.text_input("Sahifalar (masalan: 1-5, 9, 12-20):", value="1")
    selected_indices = parse_pages(page_spec, total_pages)

if not st.session_state.auth and len(selected_indices) > DEMO_LIMIT_PAGES:
    st.warning(f"Demo: maksimal {DEMO_LIMIT_PAGES} sahifa. Premium uchun email bilan kiring.")
    selected_indices = selected_indices[:DEMO_LIMIT_PAGES]

# preview
if selected_indices:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.image(processed_pages[selected_indices[0]], caption=f"Preview: {selected_indices[0]+1}-sahifa", use_container_width=True)
    with c2:
        st.caption("Tugmani bossangiz tanlangan sahifalar ketma-ket tahlil qilinadi (1 sahifa = 1 so‘rov).")


# =========================================================
# 13) RUN ANALYSIS
# =========================================================
run_btn = st.button("✨ AKADEMIK TAHLILNI BOSHLASH", disabled=st.session_state.running)

if run_btn:
    if not selected_indices:
        st.warning("Avval sahifani tanlang.")
        st.stop()

    st.session_state.running = True
    try:
        hint_lang = "" if (auto_detect or lang == "Noma'lum") else lang
        hint_era = "" if (auto_detect or era == "Noma'lum") else era

        prompt = build_one_call_prompt(hint_lang, hint_era)

        total = len(selected_indices)
        done = 0
        prog = st.progress(0.0)
        status_ph = st.empty()

        for idx in selected_indices:
            time.sleep(random.uniform(*BATCH_DELAY_RANGE))

            # credits (optional)
            reserved = False
            if st.session_state.auth and st.session_state.u_email:
                ok = consume_credit_safe(st.session_state.u_email, 1)
                if not ok:
                    st.warning("Kredit tugagan.")
                    continue
                reserved = True

            status_ph.info(f"Sahifa {idx+1}/{total} tahlil qilinmoqda...")
            try:
                payloads = build_payloads_for_one_request(processed_pages[idx])
                one_call_text = generate_with_retry([prompt, *payloads], max_tokens=MAX_OUT_TOKENS).strip()

                # Agar 2) va 6) chiqmay qolsa => translitdan text-only to‘ldiramiz (kamdan-kam)
                if not _has_sections(one_call_text):
                    translit = _extract_translit(one_call_text) or ""
                    if translit.strip():
                        an_prompt = build_text_only_analyze_prompt(translit)
                        an_text = generate_with_retry([an_prompt], max_tokens=MAX_OUT_TOKENS).strip()
                        if an_text:
                            one_call_text = (one_call_text.strip() + "\n\n" + an_text.strip()).strip()

                st.session_state.results[idx] = one_call_text or "Xato: bo‘sh natija."

                if st.session_state.auth and st.session_state.u_email:
                    save_report(st.session_state.u_email, st.session_state.last_fn, idx, st.session_state.results[idx])

            except Exception as e:
                if reserved and st.session_state.auth and st.session_state.u_email:
                    refund_credit_safe(st.session_state.u_email, 1)

                # 429 bo‘lsa: aniq aytamiz — bu limit
                msg = str(e)
                if _is_429(msg):
                    st.session_state.results[idx] = (
                        "Xato: 429 (quota/rate limit). Bu API limit. "
                        "Kodni sekinlashtirdik, lekin limit tugagan bo‘lsa server baribir qaytaradi.\n\n"
                        f"Texnik: {msg}"
                    )
                else:
                    st.session_state.results[idx] = f"Xato: {type(e).__name__}: {msg}"

            done += 1
            prog.progress(done / max(total, 1))

        status_ph.success("Tahlil yakunlandi.")
        prog.progress(1.0)
        gc.collect()

    finally:
        st.session_state.running = False


# =========================================================
# 14) RESULTS
# =========================================================
if st.session_state.results:
    st.divider()
    st.subheader("📄 Natijalar")

    keys = sorted(st.session_state.results.keys())
    jump = st.selectbox("Tez o‘tish:", options=keys, format_func=lambda x: f"{x+1}-sahifa")
    keys = [jump] + [k for k in keys if k != jump]

    for idx in keys:
        with st.expander(f"Varaq {idx+1}", expanded=(idx == jump)):
            left, right = st.columns([1, 1.2], gap="large")
            with left:
                st.image(processed_pages[idx], use_container_width=True)
            with right:
                res = st.session_state.results.get(idx, "") or ""

                # Copy button (xavfsiz)
                txt_json = json.dumps(res)
                components.html(f"""
                <button id="copybtn" style="width:100%;padding:10px 12px;border-radius:10px;border:1px solid #ddd;font-weight:800;cursor:pointer;">
                  📋 Natijani nusxalash
                </button>
                <script>
                  const txt = {txt_json};
                  const btn = document.getElementById("copybtn");
                  btn.onclick = async () => {{
                    try {{
                      await navigator.clipboard.writeText(txt);
                      btn.innerText = "✅ Nusxalandi";
                      setTimeout(()=>btn.innerText="📋 Natijani nusxalash", 1400);
                    }} catch(e) {{
                      btn.innerText = "❌ Clipboard ruxsat yo‘q";
                    }}
                  }};
                </script>
                """, height=55)

                st.text_area("Natija:", value=res, height=420, key=f"res_{idx}")

    # Word export (auth bo'lsa)
    if st.session_state.auth and st.session_state.u_email:
        detected = aggregate_detected_meta(st.session_state.results)
        meta = {
            "Hujjat nomi": st.session_state.last_fn,
            "Model": MODEL_NAME,
            "Til (aniqlangan)": detected["til"],
            "Xat uslubi (aniqlangan)": detected["xat"],
            "Avto aniqlash": "Ha" if auto_detect else "Yo‘q",
            "Til (hint)": lang,
            "Xat (hint)": era,
            "Eksport sahifalar": ", ".join(str(i+1) for i in sorted(st.session_state.results.keys())),
            "Yaratilgan vaqt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        report_bytes = build_word_report("Manuscript AI", meta, st.session_state.results)
        st.download_button(
            "📥 WORD HISOBOTNI YUKLAB OLISH (.docx)",
            report_bytes,
            file_name="Manuscript_AI_Report.docx"
        )

gc.collect()
