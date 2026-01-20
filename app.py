import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium
import io, gc, base64, time, random, html, re, threading
from datetime import datetime
from collections import deque

# =========================================================
# 1) CONFIG
# =========================================================
st.set_page_config(
    page_title="Manuscript AI - Professional Edition",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# 2) CONSTANTS (BARQAROR MODELGA BOG'LANDI)
# =========================================================
# MUHIM: 'latest' so'zidan qochamiz. 1.5-flash eng yuqori bepul limitga ega.
MODEL_NAME = "models/gemini-1.5-flash"  

SAFE_RPM = 14               # 1.5-flash uchun limit 15 RPM. 14 xavfsizroq.
RATE_WINDOW_SEC = 60
MAX_RETRIES = 5

# Output tokens
MAX_OUT_TOKENS = 4096

# Rasm sifat balansi
JPEG_QUALITY_FULL = 85
FULL_MAX_SIDE = 2100
TILE_MAX_SIDE = 2600

# =========================================================
# 3) UI STYLING
# =========================================================
st.markdown("""
<style>
html, body, .stApp { background: #0b1220 !important; color: #eaf0ff !important; }
h1, h2, h3 { color: #d4af37 !important; font-family: 'Georgia', serif; }
hr { border-color: rgba(212,175,55,0.25) !important; }
.stButton>button { font-weight: 800 !important; border-radius: 12px !important; background: #d4af37 !important; color: #0b1220 !important; }
.stTextArea textarea { background: #fdfaf1 !important; color:#000 !important; font-size: 16px !important; }
.result-card { background: rgba(255,255,255,0.04); border:1px solid rgba(212,175,55,0.3); border-radius:16px; padding:20px; }
.stProgress > div > div > div > div { background-color: #d4af37 !important; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 4) SERVICES (Gemini)
# =========================================================
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("GEMINI_API_KEY topilmadi.")
    st.stop()

genai.configure(api_key=api_key)

@st.cache_resource
def get_model():
    # Faqat barqaror modelni yuklaymiz
    return genai.GenerativeModel(model_name=MODEL_NAME)

ai_engine = get_model()

# =========================================================
# 5) SMART RATE LIMITER (429 xatolardan himoya)
# =========================================================
class GlobalRateLimiter:
    def __init__(self, rpm: int, window_sec: int):
        self.rpm = rpm
        self.window = window_sec
        self.ts = deque()
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            while self.ts and (now - self.ts[0]) > self.window:
                self.ts.popleft()
            
            if len(self.ts) >= self.rpm:
                sleep_time = self.window - (now - self.ts[0]) + 0.1
                time.sleep(sleep_time)
                # Tozalashdan keyin yangi vaqtni olish
                return self.wait()
            
            self.ts.append(time.monotonic())

@st.cache_resource
def get_limiter():
    return GlobalRateLimiter(SAFE_RPM, RATE_WINDOW_SEC)

limiter = get_limiter()

def generate_call(parts):
    """Xatolarni ushlash va qayta urinish tizimi bilan AI chaqiruvi"""
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            limiter.wait()
            resp = ai_engine.generate_content(
                parts,
                generation_config={"max_output_tokens": MAX_OUT_TOKENS, "temperature": 0.2}
            )
            return resp.text
        except Exception as e:
            last_err = str(e)
            if "429" in last_err or "quota" in last_err.lower():
                # Agar limit to'lsa, kutish vaqti eksponentsial ortadi
                wait_time = (attempt + 1) * 10
                time.sleep(wait_time)
                continue
            else:
                st.error(f"Kutilmagan xato: {e}")
                return None
    return f"Xato: Limitlar oshib ketdi. Iltimos 1 daqiqa kuting. ({last_err})"

# =========================================================
# 6) CORE LOGIC (IMAGE & PDF)
# =========================================================
def pil_to_bytes(img: Image.Image):
    img = img.convert("RGB")
    # Tiling/Zoom qilish uchun piksellar boyitiladi
    w, h = img.size
    if max(w, h) > 2200:
        ratio = 2200 / float(max(w, h))
        img = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY_FULL)
    return buf.getvalue()

@st.cache_data(show_spinner=False)
def get_page_image(file_bytes, p_idx, scale):
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[p_idx]
    pil_img = page.render(scale=scale).to_pil()
    pdf.close()
    return pil_img

def build_parts(img_bytes, prompt_txt):
    """Google Gemini uchun multimodal payload"""
    return [
        prompt_txt,
        {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}
    ]

# =========================================================
# 7) APP UI
# =========================================================
st.title("📜 Manuscript AI Center")
st.markdown("##### Akademik Qo'lyozmalar uchun Professional Tahlil")

with st.sidebar:
    st.markdown("### ⚙️ Sozlamalar")
    st.info(f"Hozirgi model: **Gemini 1.5 Flash (1500 RPD)**")
    
    # Preprocessing
    st.divider()
    contrast = st.slider("Kontrast (Siyoh o'tkirligi):", 0.5, 3.0, 1.5)
    sharpen = st.checkbox("Sharpen (Keskinlashtirish)", value=True)
    
    st.divider()
    lang_hint = st.selectbox("Taxminiy matn tili:", ["Aniqlanmagan", "Chig'atoy", "Forscha", "Arabcha", "Usmonli Turk"])
    
    # PDF scale
    pdf_scale = st.slider("PDF Sifati (DPI):", 1.5, 3.5, 2.1)

# Fayl yuklash
file = st.file_uploader("Faylni yuklang (PDF yoki Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'])

if file:
    # Faylni xotiraga olish
    if "last_file_name" not in st.session_state or st.session_state.last_file_name != file.name:
        st.session_state.last_file_name = file.name
        st.session_state.results = {}
        st.session_state.raw_data = file.getvalue()
        gc.collect()

    # Sahifalarni aniqlash
    if file.type == "application/pdf":
        doc = pdfium.PdfDocument(st.session_state.raw_data)
        n_pages = len(doc)
        doc.close()
    else:
        n_pages = 1

    st.write(f"Hujjat yuklandi: **{n_pages} sahifa**")
    
    # Sahifa tanlash
    sel_page = st.number_input("Tahlil uchun sahifa raqamini yozing:", 1, n_pages, 1) - 1
    
    # Tasvirni render qilish va preprocess
    with st.spinner("Varaq tayyorlanmoqda..."):
        img = get_page_image(st.session_state.raw_data, sel_page, pdf_scale)
        if sharpen:
            img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(contrast)
        
        # Vizual ko'rish
        st.image(img, caption=f"{sel_page+1}-sahifa", use_container_width=True)

    # TAHLIL
    if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
        prompt = (
            f"Siz Manuscript AI matnshunosisiz. Hujjat tili taxminan: {lang_hint}.\n"
            "Vazifa:\n1. Matnni xatosiz lotin alifbosiga ko'chiring (transliteratsiya).\n"
            "2. Matnni zamonaviy o'zbek tiliga akademik tarjima qiling.\n"
            "3. Tarixiy sharh va izoh bering.\n"
            "Hech narsa uydirmang. O'qib bo'lmagan joyda [?] belgisini ishlating."
        )
        
        with st.status("AI qo'lyozmani o'rganmoqda...") as status:
            img_bytes = pil_to_bytes(img)
            parts = build_parts(img_bytes, prompt)
            
            res_text = generate_call(parts)
            if res_text:
                st.session_state.results[sel_page] = res_text
                status.update(label="Tahlil yakunlandi!", state="complete")
            else:
                status.update(label="Xatolik yuz berdi", state="error")

    # NATIJANI KO'RSATISH
    if sel_page in st.session_state.results:
        res = st.session_state.results[sel_page]
        st.divider()
        st.subheader("🖋 Tahlil Natijasi:")
        
        # Copy to Clipboard Component
        safe_res = html.escape(res)
        copy_code = f"""
        <button id="copy-btn" style="padding:10px 20px; border-radius:10px; cursor:pointer; font-weight:bold;">📋 Natijani nusxalash</button>
        <script>
        const txt = {repr(res)};
        document.getElementById('copy-btn').onclick = () => {{
            navigator.clipboard.writeText(txt).then(() => {{
                document.getElementById('copy-btn').innerText = "✅ Nusxalandi!";
                setTimeout(() => {{ document.getElementById('copy-btn').innerText = "📋 Natijani nusxalash"; }}, 2000);
            }});
        }}
        </script>
        """
        components.html(copy_code, height=50)
        
        st.markdown(f"<div class='result-card'>{res}</div>", unsafe_allow_html=True)
        st.text_area("Tahrirlash uchun matn:", value=res, height=400)

gc.collect()
