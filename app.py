import streamlit as st
import streamlit.components.v1 as components

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium

import io, gc, base64, time, random, html, re, threading
from datetime import datetime
from collections import deque

# Optional (app ishlashi uchun shart emas)
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
# 2) CONSTANTS (LOCKED MODEL)
# =========================================================
MODEL_NAME = "gemini-flash-latest"  # ✅ FAQAT SHU MODEL (fallback YO‘Q)

SAFE_RPM = 8               # 429 kamaytirish uchun konservativ
RATE_WINDOW_SEC = 60
MAX_RETRIES = 7

# Output tokens
MAX_OUT_TOKENS = 4096

# Rasm sifat balansi (tezlik + aniqlik)
JPEG_QUALITY_FULL = 84
JPEG_QUALITY_TILE = 86
FULL_MAX_SIDE = 2100
TILE_MAX_SIDE = 2600

# PDF render
PDF_SCALE_DEFAULT = 2.1

# Pages delay (ketma-ket bosilganda ham tarmoqni bosmaydi)
BATCH_DELAY_RANGE = (0.7, 1.3)

# =========================================================
# 3) SIMPLE THEME + CSS (soddaroq, lekin chiroyli)
# =========================================================
st.markdown("""
<style>
html, body, .stApp { background: #0b1220 !important; color: #eaf0ff !important; }
h1, h2, h3 { color: #d4af37 !important; }
hr { border-color: rgba(212,175,55,0.25) !important; }
.stButton>button { font-weight: 800 !important; border-radius: 12px !important; }
.stTextArea textarea { background: #fdfaf1 !important; color:#000 !important; }
.card { background: rgba(255,255,255,0.04); border:1px solid rgba(212,175,55,0.25); border-radius:16px; padding:14px; }
.small { color: rgba(234,240,255,0.72); font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 4) SERVICES (Gemini + optional Supabase)
# =========================================================
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("GEMINI_API_KEY topilmadi. Streamlit secrets.toml ga qo‘ying.")
    st.stop()

genai.configure(api_key=api_key)

@st.cache_resource
def get_model():
    return genai.GenerativeModel(model_name=MODEL_NAME)

model = get_model()

@st.cache_resource
def get_db():
    # DB bo‘lmasa ham app ishlaydi
    if create_client is None:
        return None
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None

db = get_db()

# =========================================================
# 5) RATE LIMITER (global)
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

def _looks_like_429(msg: str) -> bool:
    m = (msg or "").lower()
    return ("429" in m) or ("quota" in m) or ("rate" in m) or ("exceeded" in m)

def _looks_like_5xx(msg: str) -> bool:
    m = (msg or "").lower()
    return ("500" in m) or ("503" in m) or ("timeout" in m) or ("unavailable" in m)

def _parse_retry_seconds(err_text: str) -> float:
    """
    Gemini ba'zida: 'Please retry in 10.3s' yoki retry_delay seconds: 40
    """
    t = err_text or ""
    m1 = re.search(r"retry in\s*([0-9.]+)\s*s", t, flags=re.IGNORECASE)
    if m1:
        try:
            return float(m1.group(1))
        except Exception:
            pass
    m2 = re.search(r"retry_delay\s*\{\s*seconds:\s*([0-9]+)", t, flags=re.IGNORECASE)
    if m2:
        try:
            return float(int(m2.group(1)))
        except Exception:
            pass
    return 0.0

def generate_with_retry(parts, max_tokens: int = MAX_OUT_TOKENS, tries: int = MAX_RETRIES) -> str:
    last_err = None
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
            low = msg.lower()

            # 404 model not found: aniq xabar
            if ("404" in low) and ("not found" in low or "models/" in low):
                raise RuntimeError(
                    f"AI xatosi: 404. Model '{MODEL_NAME}' topilmadi yoki bu API versiyada yo‘q. "
                    f"Model nomini aynan '{MODEL_NAME}' qiling."
                ) from e

            # 429 / 5xx: backoff + server aytgan delay bo‘lsa shuni kutamiz
            if _looks_like_429(msg) or _looks_like_5xx(msg):
                server_wait = _parse_retry_seconds(msg)
                base = min(60.0, (2 ** attempt) + random.uniform(0.6, 1.8))
                wait_s = max(server_wait, base)
                time.sleep(wait_s)
                continue

            raise
    raise RuntimeError(f"So‘rov bajarilmadi (429/Network). Oxirgi xato: {last_err}") from last_err

# =========================================================
# 6) IMAGE/PDF HELPERS
# =========================================================
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

@st.cache_data(show_spinner=False, max_entries=16)
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

def build_payloads_from_page(img_bytes: bytes):
    """
    1 so‘rov ichida: 1 full + 2 bo‘lak (yoki 4 tile).
    Overlap bo‘ladi — prompt + dedupe buni bartaraf qiladi.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    aspect = w / max(h, 1)

    payloads = [_payload(pil_to_jpeg_bytes(img, quality=JPEG_QUALITY_FULL, max_side=FULL_MAX_SIDE))]

    # Spread bo‘lsa: left/right
    if aspect >= 1.25:
        left = img.crop((0, 0, w // 2, h))
        right = img.crop((w // 2, 0, w, h))
        payloads.append(_payload(pil_to_jpeg_bytes(left, quality=JPEG_QUALITY_TILE, max_side=TILE_MAX_SIDE)))
        payloads.append(_payload(pil_to_jpeg_bytes(right, quality=JPEG_QUALITY_TILE, max_side=TILE_MAX_SIDE)))
        return payloads

    # Aks holda: 2x2 tile (overlap bilan)
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

    # Juda ko‘p tile ham limitga uradi; 1 full + 4 tile yetarli
    return payloads[:5]

# =========================================================
# 7) PROMPT (FIXED) + OUTPUT NORMALIZATION
# =========================================================
def build_prompt(hint_lang: str, hint_era: str) -> str:
    hl = hint_lang or "yo‘q"
    he = hint_era or "yo‘q"
    return (
        "Siz qo‘lyozma (manuscript) o‘qish va tarjima qilish bo‘yicha juda sinchkov mutaxassissiz.\n"
        "Sizga BIR sahifa uchun bir nechta rasm beriladi: 1-rasm full, qolganlari zoom/bo‘laklar.\n"
        "Bo‘laklar ustma-ust (overlap) bo‘lishi mumkin.\n\n"
        "Vazifa:\n"
        "A) Sahifadagi matnni maksimal to‘liq ko‘chiring (asliyatni satrma-satr).\n"
        "B) So‘ng o‘zbekchaga to‘g‘ridan-to‘g‘ri tarjima qiling.\n"
        "C) Qisqa izoh bering.\n\n"
        "MUHIM QOIDALAR:\n"
        "- Hech narsa UYDIRMANG.\n"
        "- O‘qilmagan joy: [o‘qilmadi] yoki [?].\n"
        "- Zoom/bo‘laklar sabab bir xil satr bir necha marta ko‘rinishi mumkin: "
        "bunday holatda SATRNI FAQAT 1 MARTA yozing (faqat manbada haqiqatan takror bo‘lsa takrorlang).\n"
        "- Natijani faqat quyidagi bo‘limlarda chiqaring (boshqa matn YO‘Q).\n\n"
        f"HINT: til='{hl}', xat uslubi='{he}'.\n\n"
        "FORMAT (aniq shunday):\n"
        "0) Tashxis:\n"
        "Til: <aniqlangan yoki Noma'lum>\n"
        "Xat uslubi: <aniqlangan yoki Noma'lum>\n"
        "Ishonchlilik: <Yuqori/O‘rtacha/Past>\n\n"
        "1) Matn (asliyat, satrma-satr):\n"
        "<matnni satrma-satr yozing; takror satrlarni overlapdan kelib chiqib ko‘paytirmang>\n\n"
        "2) To‘g‘ridan-to‘g‘ri tarjima:\n"
        "<o‘zbekcha, to‘liq>\n\n"
        "6) Izoh:\n"
        "<kontekst; noaniq joylarni ehtiyotkor izohlang>\n"
    )

def _has_sections(text: str) -> bool:
    t = (text or "").lower()
    return ("0) tashxis" in t) and ("1) matn" in t) and ("2) to" in t) and ("6) izoh" in t)

def _dedupe_lines_block(block: str) -> str:
    # Juda ehtiyotkor dedupe: faqat aynan bir xil satrlar olib tashlanadi
    lines = block.splitlines()
    out = []
    seen = set()
    for ln in lines:
        key = re.sub(r"\s+", " ", (ln or "").strip())
        if not key:
            out.append(ln)
            continue
        # sarlavha bo‘lsa (0) 1) 2) 6)) hech qachon olib tashlamaymiz
        if re.match(r"^\s*\d+\)\s+", ln.strip()):
            out.append(ln)
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(ln)
    return "\n".join(out)

def normalize_output(text: str) -> str:
    raw = (text or "").strip()

    # 1) Matn bo‘limini topib, faqat o‘sha qismda dedupe qilamiz
    lower = raw.lower()
    p2 = lower.find("\n2)")
    if p2 == -1:
        # bo‘limlar yo‘q bo‘lsa, umumiy dedupe
        return _dedupe_lines_block(raw)

    head = raw[:p2]
    tail = raw[p2:]

    head = _dedupe_lines_block(head)
    out = (head + tail).strip()
    return out

def repair_if_needed(text: str) -> str:
    """
    Agar model formatni buzsa yoki tarjima/izoh yo‘q bo‘lsa, text-only repair.
    (Bu 2-so‘rov, faqat kerak bo‘lsa ishlaydi)
    """
    if _has_sections(text):
        return text

    repair_prompt = (
        "Quyidagi natija formatni buzgan yoki bo‘limlar yetishmaydi.\n"
        "Siz faqat 0), 1), 2), 6) bo‘limlarini to‘liq va aniq chiqarib bering.\n"
        "Hech narsa uydirmang. O‘qilmagan joy: [o‘qilmadi] yoki [?].\n\n"
        "FORMAT (aniq shunday):\n"
        "0) Tashxis:\n"
        "Til: <...>\n"
        "Xat uslubi: <...>\n"
        "Ishonchlilik: <Yuqori/O‘rtacha/Past>\n\n"
        "1) Matn (asliyat, satrma-satr):\n"
        "<...>\n\n"
        "2) To‘g‘ridan-to‘g‘ri tarjima:\n"
        "<...>\n\n"
        "6) Izoh:\n"
        "<...>\n\n"
        "MANBA MATN:\n"
    ) + (text or "")

    fixed = generate_with_retry([repair_prompt], max_tokens=MAX_OUT_TOKENS).strip()
    fixed = normalize_output(fixed)
    return fixed if fixed else text

# =========================================================
# 8) APP STATE
# =========================================================
if "last_fn" not in st.session_state:
    st.session_state.last_fn = None
if "page_bytes" not in st.session_state:
    st.session_state.page_bytes = []
if "results" not in st.session_state:
    st.session_state.results = {}

# =========================================================
# 9) UI (simple, demo-friendly)
# =========================================================
st.title("📜 Manuscript AI Center")
st.caption(f"Model: {MODEL_NAME}  •  1 sahifa = 1 so‘rov (format buzilsa repair ishlaydi)")

with st.sidebar:
    st.markdown("### 🧪 Skan sozlamalari")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.05)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.45)
    sharpen = st.slider("Sharpen:", 0.0, 1.5, 1.0, 0.1)

    st.markdown("### PDF")
    scale = st.slider("PDF render scale:", 1.4, 2.8, PDF_SCALE_DEFAULT, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 120, 40)

    st.markdown("### 🧠 Hintlar")
    auto_detect = st.checkbox("Avto aniqlash (tavsiya)", value=True)
    lang = st.selectbox("Taxminiy matn tili:", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=0)
    era = st.selectbox("Taxminiy xat uslubi:", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=0)

uploaded_file = st.file_uploader("Fayl yuklang (pdf/png/jpg)", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file is None:
    st.stop()

# =========================================================
# 10) LOAD FILE -> PAGES
# =========================================================
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
st.markdown(f"<div class='card'>Yuklandi: <b>{total_pages}</b> sahifa</div>", unsafe_allow_html=True)

# Pages selection
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

# Preview
if selected_indices:
    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        st.image(processed_pages[selected_indices[0]], caption=f"Preview: {selected_indices[0]+1}-sahifa", use_container_width=True)
    with c2:
        st.markdown("<div class='small'>Tip: agar matn xira bo‘lsa Contrast/Sharpen ni oshiring.</div>", unsafe_allow_html=True)

# =========================================================
# 11) RUN ANALYSIS
# =========================================================
if st.button("✨ TAHLILNI BOSHLASH"):
    if not selected_indices:
        st.warning("Avval sahifa tanlang.")
        st.stop()

    hint_lang = "" if (auto_detect or lang == "Noma'lum") else lang
    hint_era = "" if (auto_detect or era == "Noma'lum") else era
    prompt = build_prompt(hint_lang, hint_era)

    total = len(selected_indices)
    done = 0
    bar = st.progress(0.0)

    for idx in selected_indices:
        time.sleep(random.uniform(*BATCH_DELAY_RANGE))

        with st.status(f"Sahifa {idx+1} tahlil qilinmoqda...") as s:
            try:
                img_bytes = processed_pages[idx]
                payloads = build_payloads_from_page(img_bytes)

                # 1 ta vision so‘rov
                raw = generate_with_retry([prompt, *payloads], max_tokens=MAX_OUT_TOKENS).strip()
                raw = normalize_output(raw)

                # Format buzilsa yoki tarjima yo‘q bo‘lsa: repair
                final = repair_if_needed(raw)

                st.session_state.results[idx] = final
                s.update(label="Tayyor!", state="complete")

            except Exception as e:
                st.session_state.results[idx] = f"Xato: {type(e).__name__}: {e}"
                s.update(label="Xato", state="error")

        done += 1
        bar.progress(done / max(total, 1))

    bar.progress(1.0)
    st.success("Tahlil yakunlandi.")

# =========================================================
# 12) RESULTS
# =========================================================
if st.session_state.results:
    st.divider()
    keys = sorted(st.session_state.results.keys())
    jump = st.selectbox("⚡ Tez o‘tish:", options=keys, format_func=lambda x: f"{x+1}-sahifa")
    keys = [jump] + [k for k in keys if k != jump]

    for idx in keys:
        with st.expander(f"📖 {idx+1}-sahifa natijasi", expanded=True):
            left, right = st.columns([1, 1.2], gap="large")
            with left:
                st.image(processed_pages[idx], use_container_width=True)

            with right:
                res = st.session_state.results.get(idx, "") or ""
                # Copy button
                safe_txt = html.escape(res)
                copy_js = f"""
                <button id="copybtn" style="width:100%;padding:10px 12px;border-radius:12px;border:1px solid rgba(0,0,0,0.12);font-weight:900;cursor:pointer;">
                  📋 Natijani nusxalash
                </button>
                <script>
                  const txt = {safe_txt!r};
                  document.getElementById("copybtn").onclick = async () => {{
                    try {{
                      await navigator.clipboard.writeText(txt);
                      document.getElementById("copybtn").innerText = "✅ Nusxalandi";
                      setTimeout(()=>document.getElementById("copybtn").innerText="📋 Natijani nusxalash", 1500);
                    }} catch(e) {{
                      document.getElementById("copybtn").innerText = "❌ Clipboard ruxsat yo‘q";
                    }}
                  }}
                </script>
                """
                components.html(copy_js, height=55)
                st.text_area("Natija", value=res, height=420)

gc.collect()
