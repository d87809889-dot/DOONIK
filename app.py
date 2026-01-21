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
# 4) API SOZLAMALARI (AVVAL)
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

# API'ni sozlash
genai.configure(api_key=GEMINI_API_KEY)

# =========================================================
# 5) ISHLAYDIGAN MODELNI TOPISH (YANGI)
# =========================================================
@st.cache_data(show_spinner=False)
def get_available_models() -> List[str]:
    """API'dan mavjud modellarni olish"""
    try:
        models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                # Model nomini to'g'ri formatga keltirish
                model_name = m.name
                if model_name.startswith('models/'):
                    model_name = model_name.replace('models/', '')
                models.append(model_name)
        return models
    except Exception as e:
        st.warning(f"⚠️ Modellarni olishda xatolik: {e}")
        # Fallback - qo'lda yozilgan modellar
        return [
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash-002",
            "gemini-1.5-pro-002",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro-vision",
            "gemini-pro",
        ]

# Mavjud modellarni olish
AVAILABLE_MODELS = get_available_models()

if not AVAILABLE_MODELS:
    st.error("❌ Hech qanday model topilmadi!")
    st.stop()

st.sidebar.success(f"✅ {len(AVAILABLE_MODELS)} ta model mavjud")

# Default model - birinchi mavjud model
MODEL_NAME = AVAILABLE_MODELS[0] if AVAILABLE_MODELS else "gemini-1.5-flash-latest"

# =========================================================
# 2) ASOSIY SOZLAMALAR
# =========================================================
# Rate limiting sozlamalari
SAFE_RPM_DEFAULT = 2
RATE_WINDOW_SEC = 60
MAX_RETRIES = 5
MIN_REQUEST_INTERVAL = 15.0

# Token va rasm sozlamalari
MAX_OUT_TOKENS = 8192
FULL_MAX_SIDE = 1600
CROP_MAX_SIDE = 1800
JPEG_QUALITY = 90

PDF_SCALE_DEFAULT = 2.5
DEMO_LIMIT_PAGES = 3

# =========================================================
# 3) DIZAYN
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
# 6) GEMINI MODEL (ISHONCHLI VERSIYA)
# =========================================================
@st.cache_resource
def get_model(model_name: str = MODEL_NAME):
    """Modelni yuklash va test qilish"""
    # Avval tanlangan modelni sinash
    try:
        st.info(f"🔄 {model_name} yuklanmoqda...")
        test_model = genai.GenerativeModel(model_name=model_name)
        
        # Test so'rov
        test_response = test_model.generate_content("Test", generation_config={"max_output_tokens": 10})
        
        st.success(f"✅ Model tayyor: {model_name}")
        return test_model
        
    except Exception as e:
        error_msg = str(e)
        st.warning(f"⚠️ {model_name} ishlamadi: {error_msg[:100]}")
        
        # Boshqa modellarni sinash
        for alt_model in AVAILABLE_MODELS:
            if alt_model == model_name:
                continue
                
            try:
                st.info(f"🔄 {alt_model} sinab ko'rilmoqda...")
                test_model = genai.GenerativeModel(model_name=alt_model)
                test_response = test_model.generate_content("Test", generation_config={"max_output_tokens": 10})
                
                st.success(f"✅ Model topildi: {alt_model}")
                return test_model
                
            except Exception as e2:
                st.warning(f"⚠️ {alt_model} ham ishlamadi")
                continue
        
        # Hech qanday model ishlamadi
        st.error("❌ Hech qanday model ishlamadi!")
        st.info("""
        🔧 Yechimlar:
        1. API key yangilang: https://aistudio.google.com/app/apikey
        2. Kutubxonani yangilang:
           ```bash
           pip install google-generativeai --upgrade
           ```
        3. Quota tekshiring: https://console.cloud.google.com
        """)
        raise RuntimeError("Ishlaydigan model topilmadi")

model = get_model()

# =========================================================
# 7) RATE LIMITER
# =========================================================
class RateLimiter:
    """So'rovlarni cheklash"""
    def __init__(self, rpm: int, window_sec: int = 60):
        self.rpm = max(1, int(rpm))
        self.window = int(window_sec)
        self.lock = threading.Lock()
        self.timestamps = deque()
        self.last_request_time = 0

    def wait_for_slot(self):
        while True:
            with self.lock:
                now = time.monotonic()
                
                time_since_last = now - self.last_request_time
                if time_since_last < MIN_REQUEST_INTERVAL:
                    sleep_needed = MIN_REQUEST_INTERVAL - time_since_last
                    time.sleep(sleep_needed)
                    now = time.monotonic()
                
                while self.timestamps and (now - self.timestamps[0]) > self.window:
                    self.timestamps.popleft()

                if len(self.timestamps) < self.rpm:
                    self.timestamps.append(now)
                    self.last_request_time = now
                    return

                sleep_time = (self.window - (now - self.timestamps[0])) + 3
            time.sleep(max(3, sleep_time))

@st.cache_resource
def get_limiter():
    return RateLimiter(SAFE_RPM_DEFAULT, RATE_WINDOW_SEC)

limiter = get_limiter()

# =========================================================
# 8) XATO TEKSHIRISH
# =========================================================
def parse_retry_seconds(err_msg: str) -> Optional[float]:
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
    m = msg.lower()
    keywords = ["429", "quota", "rate limit", "exceeded", "too many requests"]
    return any(kw in m for kw in keywords)

def is_404_error(msg: str) -> bool:
    m = msg.lower()
    return "404" in m or "not found" in m or "does not exist" in m

def is_network_error(msg: str) -> bool:
    m = msg.lower()
    keywords = ["network", "connection", "timeout", "unreachable"]
    return any(kw in m for kw in keywords)

def generate_with_retry(parts, max_tokens: int = MAX_OUT_TOKENS) -> str:
    """AI'dan javob olish"""
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            limiter.wait_for_slot()
            
            result = [None]
            error = [None]
            
            def _generate():
                try:
                    response = model.generate_content(
                        parts,
                        generation_config={
                            "max_output_tokens": max_tokens,
                            "temperature": 0.1,
                            "top_p": 0.8,
                            "top_k": 40,
                        },
                        safety_settings=[
                            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                        ]
                    )
                    
                    if hasattr(response, 'prompt_feedback'):
                        if response.prompt_feedback.block_reason:
                            error[0] = Exception(f"Bloklandi: {response.prompt_feedback.block_reason}")
                            return
                    
                    text = getattr(response, "text", "")
                    if not text and hasattr(response, 'parts'):
                        text = " ".join([part.text for part in response.parts if hasattr(part, 'text')])
                    
                    if not text or len(text.strip()) < 50:
                        error[0] = ValueError("Javob juda qisqa")
                        return
                    
                    result[0] = text
                except Exception as e:
                    error[0] = e
            
            thread = threading.Thread(target=_generate)
            thread.daemon = True
            thread.start()
            thread.join(timeout=120)
            
            if thread.is_alive():
                raise TimeoutError("Timeout (120s)")
            
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
            
            if is_404_error(error_msg):
                st.error(f"❌ Model topilmadi")
                raise
            
            if is_429_error(error_msg):
                retry_sec = parse_retry_seconds(error_msg)
                if retry_sec is None:
                    retry_sec = min(120, (5 ** attempt) + random.uniform(5, 10))
                else:
                    retry_sec = retry_sec + random.uniform(5, 10)
                
                st.warning(f"⏳ Quota cheklovi. {retry_sec:.0f}s kutilmoqda...")
                time.sleep(retry_sec)
                continue
            
            if is_network_error(error_msg):
                wait_time = min(60, (3 ** attempt) + random.uniform(2, 5))
                st.warning(f"🌐 Tarmoq xatosi. {wait_time:.0f}s...")
                time.sleep(wait_time)
                continue
            
            if attempt < MAX_RETRIES - 1:
                wait_time = (3 ** attempt) + random.uniform(2, 5)
                st.warning(f"⚠️ Xatolik. {wait_time:.0f}s...")
                time.sleep(wait_time)
                continue
            
            st.error(f"❌ Xatolik: {error_msg}")
            raise
    
    raise RuntimeError(f"Muvaffaqiyatsiz. Oxirgi xato: {last_error}")

# =========================================================
# 9) RASM QAYTA ISHLASH
# =========================================================
def pil_to_jpeg_bytes(img: Image.Image, quality: int = JPEG_QUALITY, max_side: int = FULL_MAX_SIDE) -> bytes:
    img = img.convert("RGB")
    w, h = img.size
    
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

def create_payload(img_bytes: bytes) -> dict:
    return {
        "mime_type": "image/jpeg",
        "data": base64.b64encode(img_bytes).decode("utf-8")
    }

def auto_crop_text(img: Image.Image) -> Image.Image:
    try:
        img_gray = img.convert("L")
        img_gray = ImageOps.autocontrast(img_gray, cutoff=2)
        
        threshold = 185
        bw = img_gray.point(lambda p: 255 if p > threshold else 0)
        inv = ImageOps.invert(bw)
        
        bbox = inv.getbbox()
        if not bbox:
            return img
        
        x1, y1, x2, y2 = bbox
        w, h = img.size
        margin_x = int(w * 0.06)
        margin_y = int(h * 0.06)
        
        x1 = max(0, x1 - margin_x)
        y1 = max(0, y1 - margin_y)
        x2 = min(w, x2 + margin_x)
        y2 = min(h, y2 + margin_y)
        
        cropped = img.crop((x1, y1, x2, y2))
        
        if cropped.size[0] < w * 0.3 or cropped.size[1] < h * 0.3:
            return img
        
        return cropped
    except Exception as e:
        return img

def preprocess_image(img: Image.Image, brightness: float = 1.1, contrast: float = 1.3, sharpen: float = 1.0) -> Image.Image:
    img = img.convert("RGB")
    img = ImageOps.exif_transpose(img)
    
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    
    if sharpen > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(150 * sharpen), threshold=3))
    
    img = ImageOps.autocontrast(img, cutoff=2)
    
    return img

# =========================================================
# 10) PDF QAYTA ISHLASH
# =========================================================
@st.cache_data(show_spinner=False)
def render_pdf_page(file_bytes: bytes, page_index: int, scale: float = PDF_SCALE_DEFAULT) -> bytes:
    pdf = pdfium.PdfDocument(file_bytes)
    try:
        page = pdf[page_index]
        pil_img = page.render(scale=scale, rotation=0).to_pil().convert("RGB")
        return pil_to_jpeg_bytes(pil_img, quality=95, max_side=2400)
    finally:
        pdf.close()

# =========================================================
# 11) ASOSIY PROMPT
# =========================================================
def build_analysis_prompt(lang: str = "", era: str = "") -> str:
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

🔤 LOTIN YOZUVIDA:
L1: <lotin yozuvida>
L2: <lotin yozuvida>
...

🇺🇿 TARJIMA:
<To'liq, aniq, tushunarli tarjima>

💡 IZOH:
<Noaniq joylar, tarixiy kontekst, muhim so'zlar>

⚠️ ESLATMA: Agar matn o'qilmasa, "⚠️ MATN O'QILMAYDI: [sabab]" deb yozing.
""".strip()

# =========================================================
# 12) SAHIFA TAHLILI
# =========================================================
def analyze_page(img: Image.Image, prompt: str, use_crop: bool = True) -> str:
    payloads = []
    
    full_bytes = pil_to_jpeg_bytes(img, quality=JPEG_QUALITY, max_side=FULL_MAX_SIDE)
    payloads.append(create_payload(full_bytes))
    
    if use_crop:
        try:
            cropped = auto_crop_text(img)
            crop_bytes = pil_to_jpeg_bytes(cropped, quality=JPEG_QUALITY, max_side=CROP_MAX_SIDE)
            payloads.append(create_payload(crop_bytes))
        except Exception as e:
            st.warning(f"⚠️ Auto-crop xatosi: {e}")
    
    parts = [prompt] + payloads
    result = generate_with_retry(parts, max_tokens=MAX_OUT_TOKENS)
    
    return result

# =========================================================
# 13) SESSION STATE
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
# QOLGAN KOD AYNAN SHUNAQA QOLADI...
# (Sidebar, Interfeys, Natijalar - oldingi kodingizdan)
# =========================================================
# ... (914-qator oxirigacha barcha kod) ...
