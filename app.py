import base64
import io
import re
import time
import random
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
import threading

import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pypdfium2 as pdfium

# =========================================================
# 1) KONFIGURATSIYA
# =========================================================
st.set_page_config(
    page_title="Manuscript AI - Qo'lyozma Tahlili",
    page_icon="📜",
    layout="wide",
)

# =========================================================
# 2) ASOSIY SOZLAMALAR (MUKAMMAL VERSIYA)
# =========================================================
# Gemini modellar ro'yxati (barqarorlikga qarab)
AVAILABLE_MODELS = [
    "gemini-1.5-flash",          # Asosiy - barqaror va tez
    "gemini-1.5-flash-8b",       # Eng tez va arzon
    "gemini-1.5-flash-001",      # Versiyalangan
    "gemini-1.5-pro",            # Eng sifatli
    "gemini-pro-vision",         # Eski lekin ishonchli
]

MODEL_NAME = "gemini-1.5-flash"  # Default barqaror model

# Rate limiting sozlamalari (xatoliklarni kamaytirish)
SAFE_RPM_DEFAULT = 2  # 4 → 2 (yanada xavfsiz)
RATE_WINDOW_SEC = 60
MAX_RETRIES = 5  # 3 → 5 (ko'proq urinish)
MIN_REQUEST_INTERVAL = 15.0  # Yangi: minimum 15 soniya interval

# Token va rasm sozlamalari
MAX_OUT_TOKENS = 8192  # 4096 → 8192 (ko'proq output)
FULL_MAX_SIDE = 1600  # 1700 → 1600 (optimal)
CROP_MAX_SIDE = 1800  # 1900 → 1800
JPEG_QUALITY = 90  # 85 → 90 (yuqori sifat)

PDF_SCALE_DEFAULT = 2.5  # 2.0 → 2.5
DEMO_LIMIT_PAGES = 3

# =========================================================
# 3) DIZAYN (YAXSHILANGAN)
# =========================================================
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .result-card {
        background: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        margin: 15px 0;
        line-height: 1.8;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .preview-box {
        border: 3px solid #667eea;
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        background: white;
        padding: 10px;
    }
    h1, h2, h3 {
        color: #ffffff !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        border: none;
        padding: 15px 30px;
        border-radius: 10px;
        width: 100%;
        font-size: 16px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 8px 20px rgba(0,0,0,0.3);
    }
    .status-box {
        background: rgba(255,255,255,0.9);
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        box-shadow: 0 3px 10px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: rgba(255,255,255,0.2);
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 4) API SOZLAMALARI
# =========================================================
def get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except:
        return default

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
APP_PASSWORD = get_secret("APP_PASSWORD", "demo123")

if not GEMINI_API_KEY:
    st.error("⚠️ GEMINI_API_KEY topilmadi!")
    st.info("📝 .streamlit/secrets.toml faylida GEMINI_API_KEY qo'shing:")
    st.code('GEMINI_API_KEY = "AIzaSy..."', language="toml")
    st.markdown("🔗 API key olish: https://aistudio.google.com/app/apikey")
    st.stop()

# =========================================================
# 5) GEMINI MODEL (BARQAROR VERSIYA)
# =========================================================
genai.configure(api_key=GEMINI_API_KEY)

@st.cache_resource
def get_model(model_name: str = MODEL_NAME):
    """Modelni yuklash va tekshirish"""
    try:
        return genai.GenerativeModel(model_name=model_name)
    except Exception as e:
        st.error(f"❌ Model yuklashda xatolik: {model_name}")
        # Boshqa modelni sinab ko'rish
        for alt_model in AVAILABLE_MODELS:
            if alt_model != model_name:
                try:
                    st.warning(f"🔄 {alt_model} modelini sinab ko'rilmoqda...")
                    return genai.GenerativeModel(model_name=alt_model)
                except:
                    continue
        raise RuntimeError("Hech qanday model ishlamadi!")

model = get_model()

# =========================================================
# 6) RATE LIMITER (MUKAMMAL VERSIYA)
# =========================================================
class RateLimiter:
    """So'rovlarni cheklash (429 xatosini oldini olish)"""
    def __init__(self, rpm: int, window_sec: int = 60):
        self.rpm = max(1, int(rpm))
        self.window = int(window_sec)
        self.lock = threading.Lock()
        self.timestamps = deque()
        self.last_request_time = 0  # Yangi: So'nggi so'rov vaqti

    def wait_for_slot(self):
        """Navbat kutish (yaxshilangan)"""
        while True:
            with self.lock:
                now = time.monotonic()
                
                # Minimum interval tekshirish (429 oldini olish)
                time_since_last = now - self.last_request_time
                if time_since_last < MIN_REQUEST_INTERVAL:
                    sleep_needed = MIN_REQUEST_INTERVAL - time_since_last
                    time.sleep(sleep_needed)
                    now = time.monotonic()
                
                # Eski timestamplarni tozalash
                while self.timestamps and (now - self.timestamps[0]) > self.window:
                    self.timestamps.popleft()

                # Slot mavjudmi?
                if len(self.timestamps) < self.rpm:
                    self.timestamps.append(now)
                    self.last_request_time = now
                    return

                # Kutish vaqti
                sleep_time = (self.window - (now - self.timestamps[0])) + 3
            time.sleep(max(3, sleep_time))

@st.cache_resource
def get_limiter():
    return RateLimiter(SAFE_RPM_DEFAULT, RATE_WINDOW_SEC)

limiter = get_limiter()

# =========================================================
# 7) XATO TEKSHIRISH (MUKAMMAL)
# =========================================================
def parse_retry_seconds(err_msg: str) -> Optional[float]:
    """Xato xabaridan kutish vaqtini olish"""
    if not err_msg:
        return None
    patterns = [
        r"retry\s+(?:after|in)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:second|sec)",
        r"try again in\s+([0-9]+)",
        r"wait\s+([0-9]+)"
    ]
    for pattern in patterns:
        m = re.search(pattern, err_msg, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except:
                pass
    return None

def is_429_error(msg: str) -> bool:
    """429 (Rate Limit) xatosimi?"""
    m = msg.lower()
    keywords = ["429", "quota", "rate limit", "exceeded", "too many requests"]
    return any(kw in m for kw in keywords)

def is_404_error(msg: str) -> bool:
    """404 (Model topilmadi) xatosimi?"""
    m = msg.lower()
    return "404" in m or "not found" in m or "does not exist" in m

def is_network_error(msg: str) -> bool:
    """Tarmoq xatosimi?"""
    m = msg.lower()
    keywords = ["network", "connection", "timeout", "unreachable"]
    return any(kw in m for kw in keywords)

def generate_with_retry(parts, max_tokens: int = MAX_OUT_TOKENS) -> str:
    """AI'dan javob olish (mukammal retry logikasi + timeout)"""
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            # Rate limiter
            limiter.wait_for_slot()
            
            # Timeout bilan so'rov
            result = [None]
            error = [None]
            
            def _generate():
                try:
                    response = model.generate_content(
                        parts,
                        generation_config={
                            "max_output_tokens": max_tokens,
                            "temperature": 0.1,  # 0.2 → 0.1 (aniqroq)
                            "top_p": 0.8,        # Yangi
                            "top_k": 40,         # Yangi
                        },
                        safety_settings=[
                            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                        ]
                    )
                    
                    # Javobni tekshirish
                    if hasattr(response, 'prompt_feedback'):
                        if response.prompt_feedback.block_reason:
                            error[0] = Exception(f"Bloklandi: {response.prompt_feedback.block_reason}")
                            return
                    
                    text = getattr(response, "text", "")
                    if not text and hasattr(response, 'parts'):
                        text = " ".join([part.text for part in response.parts if hasattr(part, 'text')])
                    
                    if not text or len(text.strip()) < 50:
                        error[0] = ValueError("Javob juda qisqa yoki bo'sh")
                        return
                    
                    result[0] = text
                except Exception as e:
                    error[0] = e
            
            # Thread bilan timeout
            thread = threading.Thread(target=_generate)
            thread.daemon = True
            thread.start()
            thread.join(timeout=120)  # 2 daqiqa timeout
            
            if thread.is_alive():
                raise TimeoutError("So'rov juda uzoq davom etdi (120s)")
            
            if error[0]:
                raise error[0]
            
            if result[0]:
                return result[0]
            
            raise RuntimeError("Noma'lum xatolik")
            
        except TimeoutError as e:
            last_error = e
            st.warning(f"⏱️ Timeout (urinish {attempt + 1}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES - 1:
                time.sleep(5)
                continue
            raise
            
        except Exception as e:
            last_error = e
            error_msg = str(e)
            
            # 404 xatosi - model topilmadi
            if is_404_error(error_msg):
                st.error(f"❌ Model topilmadi: {MODEL_NAME}")
                st.info(f"💡 Boshqa modellarni sinab ko'ring: {', '.join(AVAILABLE_MODELS)}")
                raise
            
            # 429 xatosi - quota cheklovi
            if is_429_error(error_msg):
                retry_sec = parse_retry_seconds(error_msg)
                if retry_sec is None:
                    # Eksponensial backoff
                    retry_sec = min(120, (5 ** attempt) + random.uniform(5, 10))
                else:
                    retry_sec = retry_sec + random.uniform(5, 10)
                
                st.warning(f"⏳ Quota cheklovi. {retry_sec:.0f} soniya kutilmoqda... (Urinish {attempt + 1}/{MAX_RETRIES})")
                time.sleep(retry_sec)
                continue
            
            # Tarmoq xatosi
            if is_network_error(error_msg):
                wait_time = min(60, (3 ** attempt) + random.uniform(2, 5))
                st.warning(f"🌐 Tarmoq xatosi. {wait_time:.0f}s kutilmoqda...")
                time.sleep(wait_time)
                continue
            
            # Boshqa xatolar
            if attempt < MAX_RETRIES - 1:
                wait_time = (3 ** attempt) + random.uniform(2, 5)
                st.warning(f"⚠️ Xatolik: {error_msg[:100]}... {wait_time:.0f}s kutilmoqda...")
                time.sleep(wait_time)
                continue
            
            # Oxirgi urinish
            st.error(f"❌ Xatolik: {error_msg}")
            raise
    
    raise RuntimeError(f"So'rov {MAX_RETRIES} urinishdan keyin muvaffaqiyatsiz. Oxirgi xato: {last_error}")

# =========================================================
# 8) RASM QAYTA ISHLASH (OPTIMALLASHTIRILGAN)
# =========================================================
def pil_to_jpeg_bytes(img: Image.Image, quality: int = JPEG_QUALITY, max_side: int = FULL_MAX_SIDE) -> bytes:
    """PIL rasmni JPEG bytes'ga aylantirish"""
    img = img.convert("RGB")
    w, h = img.size
    
    # Katta rasmlarni kichraytirish
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

def create_payload(img_bytes: bytes) -> dict:
    """Gemini uchun payload yaratish"""
    return {
        "mime_type": "image/jpeg",
        "data": base64.b64encode(img_bytes).decode("utf-8")
    }

def auto_crop_text(img: Image.Image) -> Image.Image:
    """Matnli qismni avtomatik kesib olish (yaxshilangan)"""
    try:
        img_gray = img.convert("L")
        img_gray = ImageOps.autocontrast(img_gray, cutoff=2)
        
        # Adaptive threshold
        threshold = 185
        bw = img_gray.point(lambda p: 255 if p > threshold else 0)
        inv = ImageOps.invert(bw)
        
        bbox = inv.getbbox()
        if not bbox:
            return img
        
        # Margin qo'shish
        x1, y1, x2, y2 = bbox
        w, h = img.size
        margin_x = int(w * 0.06)
        margin_y = int(h * 0.06)
        
        x1 = max(0, x1 - margin_x)
        y1 = max(0, y1 - margin_y)
        x2 = min(w, x2 + margin_x)
        y2 = min(h, y2 + margin_y)
        
        cropped = img.crop((x1, y1, x2, y2))
        
        # Juda kichik crop'larni qaytarmaslik
        if cropped.size[0] < w * 0.3 or cropped.size[1] < h * 0.3:
            return img
        
        return cropped
    except Exception as e:
        return img

def preprocess_image(img: Image.Image, brightness: float = 1.1, contrast: float = 1.3, sharpen: float = 1.0) -> Image.Image:
    """Rasmni tahlil uchun tayyorlash (mukammal)"""
    img = img.convert("RGB")
    img = ImageOps.exif_transpose(img)
    
    # 1. Noise reduction (shovqinni kamaytirish)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    
    # 2. Yorqinlik va kontrast
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    
    # 3. Sharpen (aniqlik)
    if sharpen > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(150 * sharpen), threshold=3))
    
    # 4. Adaptive kontrast (matn aniqroq bo'lishi uchun)
    img = ImageOps.autocontrast(img, cutoff=2)
    
    return img

# =========================================================
# 9) PDF QAYTA ISHLASH
# =========================================================
@st.cache_data(show_spinner=False)
def render_pdf_page(file_bytes: bytes, page_index: int, scale: float = PDF_SCALE_DEFAULT) -> bytes:
    """PDF sahifasini yuqori sifatli rasmga aylantirish"""
    pdf = pdfium.PdfDocument(file_bytes)
    try:
        page = pdf[page_index]
        pil_img = page.render(scale=scale, rotation=0).to_pil().convert("RGB")
        return pil_to_jpeg_bytes(pil_img, quality=95, max_side=2400)
    finally:
        pdf.close()

# =========================================================
# 10) ASOSIY PROMPT (MUKAMMAL)
# =========================================================
def build_analysis_prompt(lang: str = "", era: str = "") -> str:
    """Professional tahlil uchun prompt (yaxshilangan)"""
    return f"""
Siz professional paleograf va qo'lyozma mutaxassisisiz. Qo'lyozma sahifasini JUDA DIQQAT bilan tahlil qiling.

📋 ASOSIY VAZIFA:
Qo'lyozma sahifasini o'qing va quyidagi formatda tahlil qiling.

⚠️ MUHIM QOIDALAR:
1. Faqat rasmda ko'rinayotgan matnni o'qing
2. Har bir so'zni diqqat bilan tekshiring
3. Agar so'z noaniq bo'lsa, [?] belgisini qo'ying
4. Shubhali joylar: [shubhali: variant1/variant2]
5. Hech narsa qo'shmang yoki o'zgartirmang
6. Har bir satrni alohida raqamlang (L1:, L2:, L3:...)
7. Barcha nuqta, vergul, diakritik belgilarni aniq ko'rsating

{f"🌐 TIL: {lang}" if lang else "🌐 TIL: Avval tilni aniqlang"}
{f"✍️ XAT USLUBI: {era}" if era else "✍️ XAT: Xat uslubini aniqlang"}

📤 JAVOB FORMATI (QATTIQ RIOYA QILING):

📋 TASHXIS:
- Til: <faqat aniq aniqlangan til>
- Xat uslubi: <faqat aniq xat turi va davri>
- Sifat: Yuqori / O'rtacha / Past / Juda past
- O'qish qiyinligi: <agar bo'lsa, nima uchun>
- Tavsiyalar: <rasm sifatini yaxshilash bo'yicha>

📝 TRANSLITERATSIYA (Asl xatda, har bir satr):
L1: <birinchi satr to'liq va aniq>
L2: <ikkinchi satr to'liq va aniq>
L3: <uchinchi satr to'liq va aniq>
...
[Barcha satrlar ketma-ket raqamlanadi]

🔤 LOTIN YOZUVIDA (Transliteratsiya):
L1: <lotin yozuvida>
L2: <lotin yozuvida>
...

🇺🇿 TARJIMA (So'zma-so'z O'zbekcha):
<To'liq, aniq, tushunarli tarjima. Kontekstni hisobga oling. Qo'shimcha tushuntirish yo'q.>

💡 IZOH VA TUSHUNTIRISH:
- Tarixiy kontekst (agar kerak bo'lsa)
- Noaniq joylar haqida batafsil tushuntirish
- Muhim so'zlar va atamalar ta'rifi
- Qo'shimcha ma'lumotlar

⚠️ ESLATMA: Agar matn o'qilmasa yoki juda sifatsiz bo'lsa, "⚠️ MATN O'QILMAYDI: [sabab]" deb yozing.
""".strip()

# =========================================================
# 11) SAHIFA TAHLILI (MUKAMMAL)
# =========================================================
def analyze_page(img: Image.Image, prompt: str, use_crop: bool = True) -> str:
    """Bitta sahifani tahlil qilish (yuqori sifat)"""
    
    payloads = []
    
    # 1. To'liq yuqori sifatli rasm
    full_bytes = pil_to_jpeg_bytes(img, quality=JPEG_QUALITY, max_side=FULL_MAX_SIDE)
    payloads.append(create_payload(full_bytes))
    
    # 2. Cropped versiya (matn fokusi)
    if use_crop:
        try:
            cropped = auto_crop_text(img)
            crop_bytes = pil_to_jpeg_bytes(cropped, quality=JPEG_QUALITY, max_side=CROP_MAX_SIDE)
            payloads.append(create_payload(crop_bytes))
        except Exception as e:
            st.warning(f"⚠️ Auto-crop xatosi: {e}")
    
    # 3. AI'ga so'rov
    parts = [prompt] + payloads
    result = generate_with_retry(parts, max_tokens=MAX_OUT_TOKENS)
    
    return result

# =========================================================
# 12) SESSION STATE
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "results" not in st.session_state:
    st.session_state.results = {}
if "pages" not in st.session_state:
    st.session_state.pages = []
if "current_model" not in st.session_state:
    st.session_state.current_model = MODEL_NAME
if "stats" not in st.session_state:
    st.session_state.stats = {"total_requests": 0, "total_tokens": 0, "errors": 0}

# =========================================================
# 13) SIDEBAR (YAXSHILANGAN)
# =========================================================
with st.sidebar:
    st.markdown("## 📜 Sozlamalar")
    
    # Model tanlash
    st.markdown("### 🤖 AI Model")
    selected_model = st.selectbox(
        "Model:",
        AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(MODEL_NAME) if MODEL_NAME in AVAILABLE_MODELS else 0,
        help="gemini-1.5-flash eng barqaror"
    )
    if selected_model != st.session_state.current_model:
        st.session_state.current_model = selected_model
        st.cache_resource.clear()
        model = get_model(selected_model)
        st.success(f"✅ Model o'zgartirildi: {selected_model}")
    
    st.divider()
    
    # Login
    if APP_PASSWORD:
        if not st.session_state.auth:
            st.markdown("### 🔑 Kirish")
            pwd = st.text_input("Parol:", type="password", key="pwd")
            if st.button("KIRISH", key="login"):
                if pwd == APP_PASSWORD:
                    st.session_state.auth = True
                    st.success("✅ Kirish muvaffaqiyatli!")
                    st.rerun()
                else:
                    st.error("❌ Parol xato!")
        else:
            st.success("✅ Tizimga kirilgan")
            if st.button("🚪 Chiqish", key="logout"):
                st.session_state.auth = False
                st.rerun()
    
    st.divider()
    
    # Til va davr
    st.markdown("### 🌐 Til va Davr")
    lang = st.selectbox(
        "Til:",
        ["", "Chig'atoy turkiy", "Forscha", "Arabcha", "Eski Turkiy", "O'zbekcha", "Qozoqcha"],
        help="Bo'sh qoldirish - avtomatik aniqlash"
    )
    era = st.selectbox(
        "Xat uslubi:",
        ["", "Nasta'liq", "Suls", "Riq'a", "Kufiy", "Divan", "Shikasta"],
        help="Bo'sh qoldirish - avtomatik aniqlash"
    )
    
    st.divider()
    
    # Rasm sozlamalari
    st.markdown("### 🎨 Rasm Sozlamalari")
    brightness = st.slider("Yorqinlik:", 0.7, 1.6, 1.15, 0.05, help="Ochroq - 1.2+")
    contrast = st.slider("Kontrast:", 0.7, 2.5, 1.4, 0.1, help="Aniqroq - 1.5+")
    sharpen = st.slider("Aniqliq:", 0.0, 2.5, 1.2, 0.1, help="Qirralari aniq - 1.5+")
    use_crop = st.checkbox("Auto-crop (matn fokusi)", value=True)
    
    st.divider()
    
    # PDF
    st.markdown("### 📄 PDF Sozlamalari")
    pdf_scale = st.slider("Sifat:", 1.5, 4.0, 2.5, 0.1, help="Yuqori - sekinroq")
    
    st.divider()
    
    # Statistika
    st.markdown("### 📊 Statistika")
    st.markdown(f"<div class='metric-card'>📌 Model: {selected_model}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='metric-card'>🎯 Max tokens: {MAX_OUT_TOKENS}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='metric-card'>⚡ RPM limit: {SAFE_RPM_DEFAULT}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='metric-card'>🔢 So'rovlar: {st.session_state.stats['total_requests']}</div>", unsafe_allow_html=True)

# =========================================================
# 14) ASOSIY INTERFEYS
# =========================================================
st.title("📜 Qo'lyozma Tahlil Markazi")
st.markdown("**Gemini 1.5 AI bilan professional qo'lyozma tahlili**")
st.markdown("---")

# Fayl yuklash
uploaded = st.file_uploader(
    "📤 Qo'lyozma faylini yuklang",
    type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp"],
    help="PDF yoki rasm formatida (max 200MB)"
)

if not uploaded:
    st.info("👆 Faylni yuklash uchun yuqoridagi tugmani bosing")
    st.markdown("""
    ### 💡 Qo'llanma:
    1. **Fayl yuklash**: PDF yoki rasm formatida qo'lyozma yuklang
    2. **Sozlash**: Til, xat uslubi va rasm sozlamalarini tanlang
    3. **Sahifalar**: Tahlil qilmoqchi bo'lgan sahifalarni belgilang
    4. **Tahlil**: "TAHLILNI BOSHLASH" tugmasini bosing
    5. **Natija**: Har bir sahifa uchun batafsil tahlil olasiz
    
    ### ✨ Imkoniyatlar:
    - 📝 **Yuqori aniqlikda OCR** - professional paleografik tahlil
    - 🔤 **Lotin yozuviga o'girish** - transliteratsiya
    - 🇺🇿 **O'zbekchaga tarjima** - kontekstli tarjima
    - 💡 **Tarixiy kontekst** - izoh va tushuntirishlar
    - 📊 **Batafsil tashxis** - til, xat, sifat
    - 💾 **Export** - TXT formatida saqlash
    - ✏️ **Tahrirlash** - natijalarni o'zgartirish
    
    ### 🔒 Xavfsizlik:
    - Barcha ma'lumotlar maxfiy saqlanadi
    - API key xavfsiz ishlatiladi
    - Rate limiting - xatoliklarni kamaytiradi
    """)
    st.stop()

# Faylni qayta ishlash
file_bytes = uploaded.getvalue()
file_key = f"{uploaded.name}_{len(file_bytes)}"

# Sahifalarni tayyorlash
if "last_file" not in st.session_state or st.session_state.last_file != file_key:
    st.session_state.last_file = file_key
    st.session_state.results = {}
    st.session_state.pages = []
    
    with st.spinner("📄 Fayl qayta ishlanmoqda..."):
        if uploaded.type == "application/pdf":
            pdf = pdfium.PdfDocument(file_bytes)
            total_pages = len(pdf)
            pdf.close()
            
            st.info(f"📚 PDF: {total_pages} sahifa topildi")
            
            # Progress bar
            progress_bar = st.progress(0)
            for i in range(min(total_pages, 50)):  # Max 50 sahifa
                page_bytes = render_pdf_page(file_bytes, i, pdf_scale)
                st.session_state.pages.append(page_bytes)
                progress_bar.progress((i + 1) / min(total_pages, 50))
        else:
            img = Image.open(io.BytesIO(file_bytes))
            img_bytes = pil_to_jpeg_bytes(img, quality=95, max_side=2400)
            st.session_state.pages = [img_bytes]
    
    st.success(f"✅ {len(st.session_state.pages)} sahifa tayyor!")

# Sahifa tanlash
total = len(st.session_state.pages)
st.markdown(f"### 📖 Jami sahifalar: **{total}** ta")

if total <= 20:
    selected = st.multiselect(
        "Tahlil qilish uchun sahifalarni tanlang:",
        options=list(range(total)),
        default=[0] if total else [],
        format_func=lambda x: f"Sahifa {x + 1}"
    )
else:
    st.info("💡 Masalan: 1-5, 8, 10-15 (vergul bilan ajratilgan)")
    range_input = st.text_input(
        "Sahifalar:",
        value="1",
        help="Oraliq: 1-5, Alohida: 8, Aralash: 1-3,5,7-9"
    )
    selected = []
    for part in range_input.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                selected.extend(range(start - 1, min(end, total)))
            except:
                pass
        else:
            try:
                idx = int(part) - 1
                if 0 <= idx < total:
                    selected.append(idx)
            except:
                pass
    selected = list(set(selected))  # Dublikatlarni olib tashlash
    selected.sort()

# Demo cheklov
if not st.session_state.auth and len(selected) > DEMO_LIMIT_PAGES:
    st.warning(f"⚠️ Demo rejim: faqat {DEMO_LIMIT_PAGES} sahifa. Parol kiriting.")
    selected = selected[:DEMO_LIMIT_PAGES]

# Preview
if selected:
    st.markdown("### 👁️ Preview")
    cols = st.columns(min(len(selected), 5))
    for i, idx in enumerate(selected[:10]):
        img = Image.open(io.BytesIO(st.session_state.pages[idx]))
        img = preprocess_image(img, brightness, contrast, sharpen)
        with cols[i % 5]:
            st.image(img, caption=f"Sahifa {idx + 1}", use_container_width=True)
    
    if len(selected) > 10:
        st.info(f"+ yana {len(selected) - 10} sahifa")

st.markdown("---")

# TAHLIL BOSHLASH
if st.button("🚀 TAHLILNI BOSHLASH", use_container_width=True, type="primary"):
    if not selected:
        st.warning("⚠️ Avval sahifalarni tanlang!")
        st.stop()
    
    prompt = build_analysis_prompt(lang, era)
    progress = st.progress(0)
    status_text = st.empty()
    
    start_time = time.time()
    success_count = 0
    error_count = 0
    
    for i, idx in enumerate(selected):
        status_text.markdown(f"<div class='status-box'>### 🔍 Sahifa {idx + 1}/{total} tahlil qilinmoqda...</div>", unsafe_allow_html=True)
        
        try:
            # Rasmni tayyorlash
            img = Image.open(io.BytesIO(st.session_state.pages[idx]))
            img = preprocess_image(img, brightness, contrast, sharpen)
            
            # Tahlil
            result = analyze_page(img, prompt, use_crop)
            st.session_state.results[idx] = result
            
            # Statistika
            st.session_state.stats['total_requests'] += 1
            success_count += 1
            
            status_text.success(f"✅ Sahifa {idx + 1} tayyor!")
            
        except Exception as e:
            error_msg = f"❌ Xatolik: {str(e)}"
            st.session_state.results[idx] = error_msg
            st.session_state.stats['errors'] += 1
            error_count += 1
            status_text.error(error_msg)
        
        progress.progress((i + 1) / len(selected))
        
        # Oraliq kutish (429 oldini olish)
        if i < len(selected) - 1:
            wait_time = random.uniform(3, 6)
            time.sleep(wait_time)
    
    elapsed = time.time() - start_time
    status_text.markdown(f"""
    <div class='status-box'>
    <h3>🎉 Tahlil yakunlandi!</h3>
    <p>⏱️ Vaqt: {elapsed:.1f}s</p>
    <p>✅ Muvaffaqiyatli: {success_count}</p>
    <p>❌ Xatolar: {error_count}</p>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# 15) NATIJALARNI KO'RSATISH (MUKAMMAL)
# =========================================================
if st.session_state.results:
    st.markdown("---")
    st.markdown("## 📊 Tahlil Natijalari")
    
    for idx in sorted(st.session_state.results.keys()):
        result = st.session_state.results[idx]
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Rasmni ko'rsatish
            img = Image.open(io.BytesIO(st.session_state.pages[idx]))
            img = preprocess_image(img, brightness, contrast, sharpen)
            
            st.markdown("<div class='preview-box'>", unsafe_allow_html=True)
            st.image(img, caption=f"Sahifa {idx + 1}", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"### 📄 Sahifa {idx + 1} - Natija")
            st.markdown(f"<div class='result-card'>{result.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
            
            # Tahrirlash
            with st.expander("✏️ Tahrirlash va export"):
                edited = st.text_area(
                    "Matnni tahrirlang:",
                    value=result,
                    height=400,
                    key=f"edit_{idx}"
                )
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f"📋 Nusxa olish", key=f"copy_{idx}"):
                        st.code(edited)
                        st.success("✅ Tayyor!")
                
                with col_b:
                    st.download_button(
                        "💾 TXT yuklab olish",
                        edited.encode("utf-8"),
                        f"sahifa_{idx + 1}.txt",
                        "text/plain",
                        key=f"download_{idx}"
                    )
        
        st.markdown("---")
    
    # Umumiy export
    st.markdown("### 📦 Umumiy Export")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # TXT export
        full_text = ""
        for idx in sorted(st.session_state.results.keys()):
            full_text += f"\n{'='*60}\n"
            full_text += f"SAHIFA {idx + 1}\n"
            full_text += f"{'='*60}\n\n"
            full_text += st.session_state.results[idx]
            full_text += "\n\n"
        
        st.download_button(
            "💾 BARCHASINI TXT",
            full_text.encode("utf-8"),
            f"tahlil_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "text/plain",
            key="download_all",
            use_container_width=True
        )
    
    with col2:
        # Statistika
        if st.button("📊 Statistika", use_container_width=True):
            total_chars = sum(len(r) for r in st.session_state.results.values())
            avg_chars = total_chars // len(st.session_state.results) if st.session_state.results else 0
            st.info(f"""
            📈 Umumiy:
            - Sahifalar: {len(st.session_state.results)}
            - Jami belgilar: {total_chars:,}
            - O'rtacha: {avg_chars:,} belgi/sahifa
            - So'rovlar: {st.session_state.stats['total_requests']}
            - Xatolar: {st.session_state.stats['errors']}
            """)
    
    with col3:
        # Tozalash
        if st.button("🗑️ Tozalash", use_container_width=True):
            st.session_state.results = {}
            st.rerun()

st.markdown("---")
st.markdown("""
<div style='text-align:center; color:white; padding: 20px;'>
    <p><strong>© 2026 Manuscript AI</strong></p>
    <p>Gemini 1.5 Flash bilan ishlab chiqilgan</p>
    <p style='font-size:12px;'>Professional qo'lyozma tahlil markazi | Barqaror va Aniq</p>
</div>
""", unsafe_allow_html=True)
