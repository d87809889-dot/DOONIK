import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, base64, time, re
from collections import deque
from docx import Document

try:
    from supabase import create_client
except Exception:
    create_client = None


# =========================
# 1) PAGE
# =========================
st.set_page_config(
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
html, body, .stApp { background:#0b1220 !important; color:#eaf0ff !important; }
h1,h2,h3 { color:#d4af37 !important; font-family: Georgia, serif; }
section[data-testid="stSidebar"] { background:#0c1421 !important; border-right: 2px solid #c5a059 !important; }
.stButton>button { width:100% !important; font-weight:800 !important; border-radius:12px !important; }
.result-box {
  background:#ffffff; color:#111827; padding:18px; border-radius:16px;
  border-left:10px solid #c5a059; box-shadow: 0 10px 30px rgba(0,0,0,.18);
  white-space: pre-wrap; line-height: 1.7; font-size: 15.5px;
}
.smallmuted { color:#b9c2d4; }
</style>
""", unsafe_allow_html=True)


# =========================
# 2) SECRETS (safe)
# =========================
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

if not GEMINI_KEY:
    st.error("GEMINI_API_KEY secrets’da yo‘q. Streamlit → Settings → Secrets ga qo‘shing.")
    st.stop()

# Optional DB
db = None
if create_client and SUPABASE_URL and SUPABASE_KEY:
    try:
        db = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        db = None


# =========================
# 3) AUTH (optional)
# =========================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "u_email" not in st.session_state:
    st.session_state.u_email = "demo@local"

with st.sidebar:
    st.markdown("## 📜 MS AI PRO")

    if APP_PASSWORD:  # password enabled
        if not st.session_state.auth:
            st.caption("Kredit/chat/Word uchun tizimga kiring.")
            email_in = st.text_input("Email", placeholder="example@mail.com")
            pwd_in = st.text_input("Parol", type="password", placeholder="****")
            if st.button("KIRISH"):
                if pwd_in == APP_PASSWORD and email_in.strip():
                    st.session_state.auth = True
                    st.session_state.u_email = email_in.strip().lower()
                    st.success("Kirdingiz ✅")
                else:
                    st.error("Email/parol xato.")
        else:
            st.success(f"Kirdi: {st.session_state.u_email}")
            if st.button("CHIQISH"):
                st.session_state.auth = False
                st.session_state.u_email = "demo@local"
    else:
        st.info("Demo rejim: APP_PASSWORD yo‘q (majburiy emas).")
        st.session_state.auth = True
        st.session_state.u_email = "demo@local"

    st.divider()
    lang = st.selectbox("Asl matn tili (hint):", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=1)
    era = st.selectbox("Xat uslubi (hint):", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=1)
    brightness = st.slider("Yorqinlik:", 0.6, 1.6, 1.05, 0.01)
    contrast = st.slider("Kontrast:", 0.7, 2.5, 1.45, 0.01)
    pdf_scale = st.slider("PDF render scale:", 1.4, 2.8, 2.1, 0.1)

    st.divider()
    st.caption("429 bo‘lsa: kod retry_delay bo‘yicha kutadi.")


# =========================
# 4) GEMINI SETUP (auto pick best flash model)
# =========================
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def pick_flash_model():
    """
    'flash-latest' har doim ham listda bir xil nomda chiqmaydi.
    Shu funksiya sizdagi APIga mos, ishlaydigan 'flash' modelni topadi.
    """
    candidates = [
        "gemini-flash-latest",
        "models/gemini-flash-latest",
        "gemini-1.5-flash",
        "models/gemini-1.5-flash",
        "gemini-2.0-flash",
        "models/gemini-2.0-flash",
        "gemini-2.5-flash",
        "models/gemini-2.5-flash",
    ]

    try:
        available = [m.name for m in genai.list_models()]
    except Exception:
        available = []

    chosen = None
    for c in candidates:
        if c in available:
            chosen = c
            break

    # Agar list_models ishlamasa ham, eng ko‘p ishlaydiganini sinab ko‘ramiz:
    if not chosen:
        chosen = "models/gemini-1.5-flash"

    return chosen, genai.GenerativeModel(model_name=chosen)

MODEL_NAME, model = pick_flash_model()


# =========================
# 5) 429 SAFE CALL (reads retry_delay)
# =========================
class RateLimiter:
    def __init__(self, rpm: int, window: int = 60):
        self.rpm = max(1, int(rpm))
        self.window = int(window)
        self.ts = deque()

    def wait(self):
        while True:
            now = time.monotonic()
            while self.ts and (now - self.ts[0]) > self.window:
                self.ts.popleft()
            if len(self.ts) < self.rpm:
                self.ts.append(now)
                return
            sleep_for = (self.window - (now - self.ts[0])) + 0.2
            time.sleep(max(0.5, sleep_for))

# RPM ni juda past qilamiz (barqarorlik uchun)
limiter = RateLimiter(rpm=6, window=60)

def _extract_retry_seconds(err_text: str) -> int:
    # "retry in 59.58s" yoki "retry_delay { seconds: 59 }"
    m = re.search(r"retry in\s+(\d+)", err_text.lower())
    if m:
        return int(m.group(1))
    m2 = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)", err_text.lower())
    if m2:
        return int(m2.group(1))
    return 15

def gemini_call(parts, max_tokens=4096, tries=6):
    last = None
    for attempt in range(tries):
        try:
            limiter.wait()
            resp = model.generate_content(
                parts,
                generation_config={"max_output_tokens": max_tokens, "temperature": 0.15}
            )
            txt = getattr(resp, "text", "") or ""
            return txt, None
        except Exception as e:
            last = str(e)

            # 404
            if "404" in last.lower() and "not found" in last.lower():
                return "", f"404: Model topilmadi. Tanlangan model: {MODEL_NAME}"

            # 429 / quota
            if ("429" in last) or ("quota" in last.lower()) or ("rate" in last.lower()):
                wait_s = _extract_retry_seconds(last) + 2
                time.sleep(min(wait_s, 90))
                continue

            # boshqa xatolar
            time.sleep(2 + attempt)
            continue
    return "", f"Xato (retry tugadi): {last}"


# =========================
# 6) PDF/IMAGE HELPERS
# =========================
def render_pdf_page_to_pil(pdf_bytes: bytes, idx: int, scale: float) -> Image.Image:
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page = pdf[idx]
        pil_img = page.render(scale=scale).to_pil()
        return pil_img
    finally:
        try:
            pdf.close()
        except Exception:
            pass

def preprocess(img: Image.Image, b: float, c: float) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(b)
    img = ImageEnhance.Contrast(img).enhance(c)
    return img

def pil_to_payload(img: Image.Image, quality=85, max_side=2100) -> dict:
    img = img.convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > max_side:
        r = max_side / float(long_side)
        img = img.resize((int(w*r), int(h*r)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode("utf-8")}


# =========================
# 7) PROMPT (tarjima xatolarini kamaytirish)
# =========================
def build_prompt(lang_hint: str, era_hint: str) -> str:
    lh = lang_hint if lang_hint != "Noma'lum" else "aniqlang"
    eh = era_hint if era_hint != "Noma'lum" else "aniqlang"

    return f"""
Siz paleograf-olim va qo‘lyozma o‘quvchisiz.
Til: {lh}. Xat uslubi: {eh}.

QOIDALAR:
- Hech narsa uydirmang.
- O‘qilmagan joy: [o‘qilmadi] yoki [?]
- Matndan birorta ham so‘z tushib qolmasin (maksimal to‘liq o‘qing).
- Natijani quyidagi FORMATDA aniq chiqaring:

0) Tashxis:
Til: ...
Xat uslubi: ...
Ishonchlilik: Yuqori/O‘rtacha/Past

1) Transliteratsiya:
(satrma-satr, maksimal to‘liq)

2) To‘g‘ridan-to‘g‘ri tarjima:
(maksimal to‘liq zamonaviy o‘zbekcha)

6) Izoh:
(kontekst, terminlar, noaniq joylarga ehtiyotkor izoh)
""".strip()


# =========================
# 8) APP
# =========================
st.title("📜 Manuscript AI Center")
st.caption(f"Model: **{MODEL_NAME}**")

uploaded = st.file_uploader("Fayl yuklang (PDF/JPG/PNG)", type=["pdf", "jpg", "jpeg", "png"])

if "results" not in st.session_state:
    st.session_state.results = {}

if uploaded:
    raw = uploaded.getvalue()

    # page count
    if uploaded.type == "application/pdf":
        pdf = pdfium.PdfDocument(raw)
        n_pages = len(pdf)
        pdf.close()
    else:
        n_pages = 1

    st.write(f"Yuklandi: **{n_pages} sahifa**")

    page_idx = st.number_input("Sahifa:", min_value=1, max_value=n_pages, value=1) - 1

    # render + preview
    with st.spinner("Sahifa tayyorlanmoqda..."):
        if uploaded.type == "application/pdf":
            img = render_pdf_page_to_pil(raw, page_idx, pdf_scale)
        else:
            img = Image.open(io.BytesIO(raw))

        img = preprocess(img, brightness, contrast)
        st.image(img, caption=f"{page_idx+1}-sahifa", use_container_width=True)

    st.divider()

    if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
        prompt = build_prompt(lang, era)
        payload = pil_to_payload(img, quality=86, max_side=2200)

        with st.status("AI tahlil qilmoqda... (429 bo‘lsa kutadi)") as s:
            text, err = gemini_call([prompt, payload], max_tokens=4096, tries=7)

            # Natija bo‘sh bo‘lsa ham sababini ko‘rsatamiz
            if err:
                s.update(label="Xatolik", state="error")
                st.error(err)
            else:
                if not text.strip():
                    s.update(label="Natija bo‘sh qaytdi", state="error")
                    st.error("AI javobi bo‘sh. Ehtimol safety/format muammo. Boshqa rasm yoki kontrastni oshirib ko‘ring.")
                else:
                    st.session_state.results[page_idx] = text
                    s.update(label="Tayyor!", state="complete")

    # show result ALWAYS if exists
    if page_idx in st.session_state.results:
        st.subheader("Natija")
        res = st.session_state.results[page_idx]
        st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)

        # Word export (oddiy)
        if st.session_state.auth:
            doc = Document()
            doc.add_heading(f"Varaq {page_idx+1}", level=1)
            for line in res.splitlines():
                doc.add_paragraph(line)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 Word yuklab olish", bio.getvalue(), file_name="report.docx")

gc.collect()
