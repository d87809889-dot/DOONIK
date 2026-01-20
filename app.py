import streamlit as st
import google.generativeai as genai

from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium

import io, gc, base64, time, random, re, html
from datetime import datetime

try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except Exception:
    Document = None

try:
    from supabase import create_client
except Exception:
    create_client = None


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Manuscript AI Center", page_icon="📜", layout="wide")

DEMO_LIMIT_PAGES = 3
MAX_PAGES_PREVIEW_DEFAULT = 40
PDF_SCALE_DEFAULT = 2.1

# Rate-limit safety (RPM)
SAFE_RPM = 6
RATE_WINDOW_SEC = 60
MAX_RETRIES = 6

# Image settings
JPEG_QUALITY_FULL = 84
JPEG_QUALITY_TILE = 86
FULL_MAX_SIDE = 2100
TILE_MAX_SIDE = 2600

# Output tokens (biroz kattaroq)
MAX_OUT_TOKENS = 8192

# Model chain:
# 1) user xohlagan alias
# 2) ko‘pincha free-tier ko‘proq beradigan variantlar (agar mavjud bo‘lsa)
MODEL_CHAIN = [
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]

# =========================
# Secrets
# =========================
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("GEMINI_API_KEY topilmadi. Streamlit secrets'ga qo‘ying.")
    st.stop()

genai.configure(api_key=api_key)


# =========================
# Optional Supabase
# =========================
@st.cache_resource
def get_db():
    if create_client is None:
        return None
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None

db = get_db()


# =========================
# Tiny in-memory RPM limiter
# =========================
class RateLimiter:
    def __init__(self, rpm: int, window_sec: int = 60):
        self.rpm = max(1, int(rpm))
        self.window = int(window_sec)
        self.ts = []

    def wait(self):
        while True:
            now = time.monotonic()
            self.ts = [t for t in self.ts if (now - t) < self.window]
            if len(self.ts) < self.rpm:
                self.ts.append(now)
                return
            sleep_for = (self.window - (now - self.ts[0])) + 0.2
            time.sleep(max(0.35, sleep_for))

limiter = RateLimiter(SAFE_RPM, RATE_WINDOW_SEC)


def _is_429(msg: str) -> bool:
    m = (msg or "").lower()
    return ("429" in m) or ("resource_exhausted" in m) or ("quota" in m) or ("rate limit" in m)

def _is_daily_quota(msg: str) -> bool:
    m = (msg or "").lower()
    return ("perday" in m) or ("requestsperday" in m) or ("generaterequestsperday" in m)

def _extract_retry_seconds(msg: str) -> float:
    # "Please retry in 10.396s"
    m = re.search(r"retry in\s+([0-9]+(\.[0-9]+)?)\s*s", msg.lower())
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return 10.0
    # "retry_delay { seconds: 40 }"
    m2 = re.search(r"retry_delay\s*{\s*seconds:\s*([0-9]+)", msg.lower())
    if m2:
        try:
            return float(m2.group(1))
        except Exception:
            return 10.0
    return 10.0


@st.cache_resource
def get_model(model_name: str):
    return genai.GenerativeModel(model_name=model_name)


def generate_with_retry(model_name: str, parts, max_tokens: int):
    model = get_model(model_name)
    last_err = None

    for attempt in range(MAX_RETRIES):
        try:
            limiter.wait()
            resp = model.generate_content(
                parts,
                generation_config={"max_output_tokens": max_tokens, "temperature": 0.15},
                request_options={"timeout": 600},  # osilib qolmasin
            )
            return (getattr(resp, "text", "") or "").strip(), None
        except Exception as e:
            last_err = e
            msg = str(e)

            # 404 -> bu model yo‘q / ruxsat yo‘q
            if "404" in msg.lower() and "not found" in msg.lower():
                return "", f"404: model topilmadi: {model_name}"

            if _is_429(msg):
                # daily quota tugasa: qayta urinib foyda yo‘q, yuqoriroq modelga o‘tishga signal beramiz
                if _is_daily_quota(msg):
                    return "", f"DAILY_QUOTA:{msg}"

                # RPM / vaqtinchalik quota: retryDelayga ko‘ra kutamiz
                wait_s = min(60.0, _extract_retry_seconds(msg) + random.uniform(0.3, 1.2))
                time.sleep(wait_s)
                continue

            # boshqa xato -> qaytar
            return "", msg

    return "", str(last_err)


# =========================
# Image helpers
# =========================
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

@st.cache_data(show_spinner=False, max_entries=12)
def render_pdf_pages_to_bytes(file_bytes: bytes, max_pages: int, scale: float):
    pdf = pdfium.PdfDocument(file_bytes)
    out = []
    try:
        n = min(len(pdf), max_pages)
        for i in range(n):
            pil_img = pdf[i].render(scale=scale).to_pil()
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
        img = img.rotate(rotate, expand=True)

    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)

    if sharpen > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(120 * sharpen), threshold=2))

    return pil_to_jpeg_bytes(img, quality=JPEG_QUALITY_FULL, max_side=FULL_MAX_SIDE)

def _payload(img_bytes: bytes) -> dict:
    return {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}

def build_payloads_from_page(img_bytes: bytes):
    """
    1 request ichida: full + zoom/tiles (matn qolib ketmasligi uchun).
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    aspect = w / max(h, 1)

    payloads = [_payload(pil_to_jpeg_bytes(img, quality=JPEG_QUALITY_FULL, max_side=FULL_MAX_SIDE))]

    # keng sahifa bo‘lsa: left/right
    if aspect >= 1.25:
        left = img.crop((0, 0, w // 2, h))
        right = img.crop((w // 2, 0, w, h))
        payloads.append(_payload(pil_to_jpeg_bytes(left, quality=JPEG_QUALITY_TILE, max_side=TILE_MAX_SIDE)))
        payloads.append(_payload(pil_to_jpeg_bytes(right, quality=JPEG_QUALITY_TILE, max_side=TILE_MAX_SIDE)))
        return payloads

    # 2x2 tiles overlap bilan
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


# =========================
# Word export (optional)
# =========================
def build_word_report(title: str, meta: dict, pages: dict) -> bytes:
    if Document is None:
        return b""
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title); run.bold = True; run.font.size = Pt(20)
    p2 = doc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.add_run("Hisobot (Transliteratsiya + Tarjima + Izoh)")

    doc.add_paragraph("")

    t = doc.add_table(rows=0, cols=2); t.style = "Table Grid"
    for k, v in meta.items():
        row = t.add_row().cells
        row[0].text = str(k); row[1].text = str(v)

    doc.add_page_break()

    for i, idx in enumerate(sorted(pages.keys())):
        doc.add_heading(f"Varaq {idx+1}", level=1)
        for line in (pages[idx] or "").splitlines():
            doc.add_paragraph(line)
        if i != len(pages) - 1:
            doc.add_page_break()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# =========================
# UI
# =========================
st.title("📜 Manuscript AI Center (Stable)")
st.caption("Soddalashtirilgan, barqaror versiya: 1 sahifa = 1 request. 429 bo‘lsa avtomatik kutadi yoki boshqa modelga o‘tadi.")

with st.sidebar:
    st.subheader("Skan sozlamalari")
    rotate = st.select_slider("Aylantirish", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik", 0.5, 2.0, 1.05)
    contrast = st.slider("Kontrast", 0.5, 3.0, 1.45)
    sharpen = st.slider("Sharpen", 0.0, 1.5, 1.0, 0.1)

    st.subheader("PDF")
    scale = st.slider("PDF render scale", 1.4, 2.8, PDF_SCALE_DEFAULT, 0.1)
    max_pages = st.slider("Preview max sahifa", 1, 160, MAX_PAGES_PREVIEW_DEFAULT)

    st.subheader("Model")
    strict_flash_latest = st.checkbox("Qat’iy: faqat gemini-flash-latest", value=False)
    st.caption("Agar qat’iy bo‘lmasa, 429/day bo‘lsa Flash-Lite’ga o‘tadi.")

uploaded_file = st.file_uploader("Faylni yuklang (PDF yoki rasm)", type=["pdf", "png", "jpg", "jpeg"])

if "last_fn" not in st.session_state:
    st.session_state.last_fn = None
if "page_bytes" not in st.session_state:
    st.session_state.page_bytes = []
if "results" not in st.session_state:
    st.session_state.results = {}

if uploaded_file is None:
    st.stop()

# Load file
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
        gc.collect()

processed_pages = [
    preprocess_bytes(b, brightness=brightness, contrast=contrast, rotate=rotate, sharpen=sharpen)
    for b in st.session_state.page_bytes
]
total_pages = len(processed_pages)
st.success(f"Yuklandi: {total_pages} sahifa (preview limit: {max_pages}).")

if total_pages <= 30:
    selected = st.multiselect(
        "Sahifalarni tanlang",
        options=list(range(total_pages)),
        default=[0] if total_pages else [],
        format_func=lambda x: f"{x+1}-sahifa"
    )
else:
    spec = st.text_input("Sahifalar (1-5, 9, 12-20)", value="1")
    selected = parse_pages(spec, total_pages)

if len(selected) == 0:
    st.stop()

# Preview
with st.expander("Preview (rasmlar)", expanded=False):
    cols = st.columns(min(len(selected), 4))
    for i, idx in enumerate(selected[:12]):
        with cols[i % min(len(cols), 4)]:
            st.image(processed_pages[idx], caption=f"{idx+1}-sahifa", use_container_width=True)


def build_prompt(hint_lang: str, hint_era: str) -> str:
    hl = hint_lang or "yo‘q"
    he = hint_era or "yo‘q"
    return (
        "Siz qo‘lyozma o‘qish va tarjima bo‘yicha mutaxassissiz.\n"
        "Sizga 1 sahifa uchun bir nechta rasm beriladi: 1-rasm full, qolganlari zoom/tiles.\n"
        "Vazifa: matndagi BIRORTA so‘zni ham tashlab ketmasdan o‘qing.\n\n"
        "QOIDALAR:\n"
        "- Hech narsa uydirmang.\n"
        "- O‘qilmagan joy: [o‘qilmadi] yoki [?].\n"
        "- Transliteratsiya satrma-satr bo‘lsin.\n"
        "- Tarjima to‘liq bo‘lsin, qisqartirmang.\n\n"
        f"HINT: til='{hl}', xat uslubi='{he}'.\n\n"
        "FORMAT (aniq shunday):\n"
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


hint_lang = ""  # soddaroq: hozircha auto
hint_era = ""

if st.button("✨ TAHLILNI BOSHLASH"):
    total = len(selected)
    done = 0
    bar = st.progress(0.0)

    # model selection strategy
    active_chain = MODEL_CHAIN if not strict_flash_latest else ["gemini-flash-latest"]

    for idx in selected:
        with st.status(f"{idx+1}-sahifa tahlil qilinmoqda...") as s:
            prompt = build_prompt(hint_lang, hint_era)
            payloads = build_payloads_from_page(processed_pages[idx])

            final_text = ""
            used_model = None

            for mi, model_name in enumerate(active_chain):
                text, err = generate_with_retry(model_name, [prompt, *payloads], MAX_OUT_TOKENS)
                if text:
                    final_text = text
                    used_model = model_name
                    break

                if err and err.startswith("DAILY_QUOTA:"):
                    # agar qat’iy bo‘lmasa, keyingi modelga o‘tamiz
                    if strict_flash_latest:
                        final_text = "Xato: Bugungi free-tier kunlik limit tugadi (flash-latest). Ertaga yoki billing bilan davom eting.\n\n" + err[11:]
                        used_model = model_name
                        break
                    # keyingi modelga o‘tish
                    continue

                # 404 bo‘lsa ham keyingisini sinaymiz (qat’iy bo‘lmasa)
                if err and ("404" in err):
                    continue

                # boshqa xato: keyingi modelga o‘tish (yoki stop)
                if err:
                    if strict_flash_latest:
                        final_text = f"Xato: {err}"
                        used_model = model_name
                        break
                    else:
                        # sinab ko‘ramiz chain bo‘yicha
                        continue

            if not final_text:
                final_text = "Xato: natija olinmadi. (tarmoq/kvota muammosi bo‘lishi mumkin)"

            st.session_state.results[idx] = f"MODEL: {used_model or 'noma’lum'}\n\n{final_text}"
            s.update(label="Tayyor", state="complete")

        done += 1
        bar.progress(done / max(total, 1))
        time.sleep(random.uniform(0.4, 0.9))

    st.success("Tahlil yakunlandi.")


if st.session_state.results:
    st.divider()
    st.subheader("Natijalar")

    for idx in sorted(st.session_state.results.keys()):
        with st.expander(f"{idx+1}-sahifa", expanded=True):
            st.image(processed_pages[idx], use_container_width=True)
            st.text_area("Natija", value=st.session_state.results[idx], height=380)

    if Document is not None:
        meta = {
            "Hujjat nomi": st.session_state.last_fn,
            "Eksport qilingan sahifalar": ", ".join(str(i+1) for i in sorted(st.session_state.results.keys())),
            "Yaratilgan vaqt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        report_bytes = build_word_report("Manuscript AI", meta, st.session_state.results)
        if report_bytes:
            st.download_button(
                "📥 WORD HISOBOT (.docx)",
                report_bytes,
                file_name="Manuscript_AI_Report.docx"
            )

gc.collect()
