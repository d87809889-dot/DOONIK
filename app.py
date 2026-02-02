# File: app_ultra_pro.py

import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, base64, json
from datetime import datetime
from docx import Document
from supabase import create_client
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Global Academic Master",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="auto"
)

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "u_email" not in st.session_state:
    st.session_state.u_email = ""
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "theme" not in st.session_state:
    st.session_state.theme = "Antik Oltin"
if "history" not in st.session_state:
    st.session_state.history = []
if "imgs" not in st.session_state:
    st.session_state.imgs = []
if "results" not in st.session_state:
    st.session_state.results = {}
if "chats" not in st.session_state:
    st.session_state.chats = {}
if "compare_mode" not in st.session_state:
    st.session_state.compare_mode = False
if "current_page_index" not in st.session_state:
    st.session_state.current_page_index = 0
if "show_landing" not in st.session_state:
    st.session_state.show_landing = True

# ==========================================
# THEME DEFINITIONS
# ==========================================
THEMES = {
    "Antik Oltin": {
        "primary": "#0c1421",
        "accent": "#c5a059",
        "accent2": "#d4af37",
        "bg_light": "#f4ecd8",
        "bg_light2": "#fdfaf1",
        "bg_dark": "#1a1a1a",
        "bg_dark2": "#2d2d2d"
    },
    "Moviy Akademik": {
        "primary": "#1e3a8a",
        "accent": "#3b82f6",
        "accent2": "#60a5fa",
        "bg_light": "#eff6ff",
        "bg_light2": "#dbeafe",
        "bg_dark": "#1e293b",
        "bg_dark2": "#334155"
    },
    "Yashil Tabiat": {
        "primary": "#065f46",
        "accent": "#10b981",
        "accent2": "#34d399",
        "bg_light": "#ecfdf5",
        "bg_light2": "#d1fae5",
        "bg_dark": "#1a2e1a",
        "bg_dark2": "#2d4a2d"
    }
}

theme = THEMES[st.session_state.theme]
dark = st.session_state.dark_mode

# Dynamic color variables
bg_main = theme["bg_dark"] if dark else theme["bg_light"]
bg_secondary = theme["bg_dark2"] if dark else theme["bg_light2"]
text_primary = "#e0e0e0" if dark else "#1a1a1a"
text_secondary = "#a0a0a0" if dark else "#5d4037"
card_bg = theme["bg_dark2"] if dark else "#ffffff"

# ==========================================
# DYNAMIC CSS
# ==========================================
st.markdown(f"""
    <style>
    /* === SYSTEM OVERRIDES === */
    footer {{visibility: hidden !important;}}
    .stAppDeployButton {{display:none !important;}}
    #stDecoration {{display:none !important;}}

    header[data-testid='stHeader'] {{
        background: rgba(0,0,0,0) !important;
        visibility: visible !important;
    }}

    button[data-testid='stSidebarCollapseButton'] {{
        background-color: {theme['primary']} !important;
        color: {theme['accent']} !important;
        border: 1px solid {theme['accent']} !important;
        position: fixed !important;
        z-index: 1000001 !important;
        transition: all 0.3s ease !important;
    }}
    
    button[data-testid='stSidebarCollapseButton']:hover {{
        background-color: {theme['accent']} !important;
        color: {theme['primary']} !important;
        transform: scale(1.05);
    }}

    /* === MAIN LAYOUT === */
    .main {{ 
        background: linear-gradient(135deg, {bg_main} 0%, {bg_secondary} 100%) !important;
        color: {text_primary} !important;
        font-family: 'Times New Roman', serif;
        padding: 2rem 1rem;
    }}
    
    /* === TYPOGRAPHY === */
    h1, h2, h3, h4 {{ 
        color: {theme['primary']} !important;
        font-family: 'Georgia', serif;
        border-bottom: 2px solid {theme['accent']};
        text-align: center;
        padding-bottom: 12px;
        margin-bottom: 20px;
    }}
    
    h1 {{
        font-size: clamp(1.8rem, 4vw, 2.5rem) !important;
        margin-top: 0;
    }}
    
    h2 {{
        font-size: clamp(1.4rem, 3vw, 2rem) !important;
    }}
    
    h4 {{
        font-size: clamp(1.1rem, 2.5vw, 1.4rem) !important;
    }}

    /* === BUTTONS === */
    .stButton>button {{ 
        background: linear-gradient(135deg, {theme['primary']} 0%, {theme['accent']} 100%) !important;
        color: {card_bg} !important;
        font-weight: bold !important;
        width: 100% !important;
        padding: 14px 20px !important;
        border: 2px solid {theme['accent']} !important;
        border-radius: 8px !important;
        height: auto !important;
        min-height: 50px !important;
        font-size: 16px !important;
        cursor: pointer !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }}
    
    .stButton>button:hover {{ 
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 20px rgba(197,160,89,0.4) !important;
        border-color: {theme['accent2']} !important;
        background: linear-gradient(135deg, {theme['accent']} 0%, {theme['primary']} 100%) !important;
    }}
    
    .stButton>button:active {{
        transform: translateY(0) !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
    }}

    /* === RESULT BOX === */
    .result-box {{ 
        background: {card_bg} !important;
        padding: 28px !important;
        border-radius: 14px !important;
        border-left: 12px solid {theme['accent']} !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.12) !important;
        color: {text_primary} !important;
        font-size: 17px;
        line-height: 1.8;
        margin-bottom: 20px;
        animation: fadeInUp 0.6s ease-out;
    }}
    
    @keyframes fadeInUp {{
        from {{
            opacity: 0;
            transform: translateY(30px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    /* === FORM INPUTS === */
    .stTextInput>div>div>input,
    .stTextArea textarea {{
        background-color: {bg_secondary} !important;
        color: {text_primary} !important;
        border: 2px solid {theme['accent']} !important;
        border-radius: 8px !important;
        padding: 12px !important;
        font-family: 'Courier New', monospace !important;
        transition: all 0.3s ease !important;
        font-size: 15px !important;
    }}
    
    .stTextInput>div>div>input:focus,
    .stTextArea textarea:focus {{
        border-color: {theme['accent2']} !important;
        box-shadow: 0 0 0 3px rgba(197,160,89,0.2) !important;
        outline: none !important;
    }}

    /* === CHAT BUBBLES === */
    .chat-user {{
        background: linear-gradient(135deg, {bg_secondary} 0%, {card_bg} 100%);
        color: {text_primary} !important;
        padding: 16px 20px;
        border-radius: 18px 18px 4px 18px;
        border-left: 5px solid {theme['primary']};
        margin-bottom: 12px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.08);
        animation: slideInLeft 0.4s ease-out;
    }}
    
    .chat-ai {{
        background: linear-gradient(135deg, {card_bg} 0%, {bg_secondary} 100%);
        color: {text_primary} !important;
        padding: 16px 20px;
        border-radius: 18px 18px 18px 4px;
        border-left: 5px solid {theme['accent']};
        margin-bottom: 16px;
        box-shadow: 0 3px 12px rgba(197,160,89,0.15);
        animation: slideInRight 0.4s ease-out;
    }}
    
    @keyframes slideInLeft {{
        from {{ opacity: 0; transform: translateX(-20px); }}
        to {{ opacity: 1; transform: translateX(0); }}
    }}
    
    @keyframes slideInRight {{
        from {{ opacity: 0; transform: translateX(20px); }}
        to {{ opacity: 1; transform: translateX(0); }}
    }}

    /* === SIDEBAR === */
    section[data-testid='stSidebar'] {{
        background: linear-gradient(180deg, {theme['primary']} 0%, #1a2332 100%) !important;
        border-right: 3px solid {theme['accent']} !important;
    }}
    
    section[data-testid='stSidebar'] .stMarkdown {{
        color: #fdfaf1 !important;
    }}
    
    section[data-testid='stSidebar'] [data-testid='stMetricValue'] {{
        color: {theme['accent']} !important;
        font-size: 24px !important;
        font-weight: bold !important;
    }}

    /* === IMAGE MAGNIFIER === */
    .magnifier-container {{
        overflow: hidden;
        border: 3px solid {theme['accent']};
        border-radius: 12px;
        cursor: zoom-in;
        background: white;
        padding: 8px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        position: relative;
    }}
    
    .magnifier-container:hover {{
        box-shadow: 0 8px 25px rgba(197,160,89,0.3);
        border-color: {theme['accent2']};
    }}
    
    .magnifier-container img {{
        transition: transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    }}
    
    .magnifier-container img:hover {{
        transform: scale(1.3);
    }}

    /* === ZOOM MODAL === */
    .modal {{
        display: none;
        position: fixed;
        z-index: 99999;
        padding-top: 50px;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        overflow: auto;
        background-color: rgba(0,0,0,0.95);
        animation: fadeIn 0.3s;
    }}
    
    .modal-content {{
        margin: auto;
        display: block;
        width: 90%;
        max-width: 1400px;
        animation: zoomIn 0.3s;
    }}
    
    @keyframes fadeIn {{
        from {{ opacity: 0; }}
        to {{ opacity: 1; }}
    }}
    
    @keyframes zoomIn {{
        from {{ transform: scale(0.7); opacity: 0; }}
        to {{ transform: scale(1); opacity: 1; }}
    }}
    
    .modal-close {{
        position: absolute;
        top: 20px;
        right: 40px;
        color: #f1f1f1;
        font-size: 50px;
        font-weight: bold;
        transition: 0.3s;
        cursor: pointer;
        z-index: 100000;
    }}
    
    .modal-close:hover,
    .modal-close:focus {{
        color: {theme['accent']};
    }}

    /* === CITATION BOX === */
    .citation-box {{
        font-size: 13px;
        color: {text_secondary};
        background: linear-gradient(135deg, {bg_secondary} 0%, {card_bg} 100%);
        padding: 14px 18px;
        border-radius: 10px;
        border: 1px dashed {theme['accent']};
        margin-top: 18px;
        font-style: italic;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }}

    /* === FILE UPLOADER === */
    [data-testid='stFileUploader'] {{
        background: {card_bg};
        border: 3px dashed {theme['accent']};
        border-radius: 12px;
        padding: 30px;
        text-align: center;
        transition: all 0.3s ease;
    }}
    
    [data-testid='stFileUploader']:hover {{
        border-color: {theme['accent2']};
        background: {bg_secondary};
        box-shadow: 0 5px 15px rgba(197,160,89,0.1);
    }}

    /* === DIVIDER === */
    hr {{
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, {theme['accent']}, transparent);
        margin: 30px 0;
    }}

    /* === EMPTY STATE === */
    .empty-state {{
        text-align: center;
        padding: 60px 20px;
        background: {card_bg};
        border-radius: 16px;
        border: 3px dashed {theme['accent']};
        margin: 40px 0;
        box-shadow: 0 5px 20px rgba(0,0,0,0.08);
    }}
    
    .empty-state h3 {{
        color: {theme['primary']};
        border: none;
        margin-bottom: 10px;
    }}

    /* === LOGIN CARD === */
    .login-card {{
        background: {card_bg};
        padding: 50px 40px;
        border-radius: 20px;
        box-shadow: 0 15px 50px rgba(0,0,0,0.15);
        border: 2px solid {theme['accent']};
        animation: fadeInUp 0.6s ease-out;
    }}
    
    .hero-title {{
        font-size: clamp(2rem, 5vw, 3rem);
        color: {theme['primary']};
        margin-bottom: 15px;
        font-weight: bold;
        text-align: center;
    }}
    
    .hero-subtitle {{
        font-size: clamp(1rem, 2vw, 1.2rem);
        color: {text_secondary};
        text-align: center;
        margin-bottom: 30px;
        line-height: 1.6;
    }}

    /* === CREDIT PROGRESS BAR === */
    .credit-bar-container {{
        background: rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 4px;
        margin: 15px 0;
        border: 1px solid {theme['accent']};
    }}
    
    .credit-bar {{
        height: 10px;
        background: linear-gradient(90deg, {theme['accent']}, {theme['accent2']});
        border-radius: 8px;
        transition: width 0.5s ease;
        box-shadow: 0 0 10px rgba(197,160,89,0.5);
    }}

    /* === SECTION HEADER === */
    .section-header {{
        color: {theme['accent']} !important;
        font-size: 16px;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 2px solid rgba(197,160,89,0.3);
    }}

    /* === MOBILE NAV BUTTONS === */
    .mobile-nav {{
        display: none;
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1000;
        background: {theme['primary']};
        padding: 10px 20px;
        border-radius: 50px;
        box-shadow: 0 5px 20px rgba(0,0,0,0.3);
    }}
    
    .mobile-nav button {{
        background: {theme['accent']};
        color: white;
        border: none;
        padding: 10px 20px;
        margin: 0 5px;
        border-radius: 20px;
        font-size: 18px;
        cursor: pointer;
    }}

    /* === RESPONSIVE === */
    @media (max-width: 768px) {{
        .main {{
            padding: 1rem 0.5rem;
        }}
        
        h1 {{
            font-size: 1.5rem !important;
        }}
        
        .result-box {{
            padding: 20px !important;
            font-size: 15px !important;
        }}
        
        .stButton>button {{
            font-size: 14px !important;
            padding: 12px 16px !important;
        }}
        
        .login-card {{
            padding: 30px 20px;
        }}
        
        .mobile-nav {{
            display: block;
        }}
    }}
    </style>

    <script>
    // === KEYBOARD SHORTCUTS ===
    document.addEventListener('keydown', function(e) {{
        // Esc - Close modal
        if (e.key === 'Escape') {{
            const modal = document.getElementById('imageModal');
            if (modal) modal.style.display = 'none';
        }}
        
        // Ctrl+Enter - Trigger analysis
        if (e.ctrlKey && e.key === 'Enter') {{
            e.preventDefault();
            const analysisBtn = Array.from(document.querySelectorAll('.stButton button'))
                .find(btn => btn.textContent.includes('AKADEMIK TAHLILNI BOSHLASH'));
            if (analysisBtn) analysisBtn.click();
        }}
        
        // Ctrl+S - Trigger download
        if (e.ctrlKey && e.key === 's') {{
            e.preventDefault();
            const downloadBtn = document.querySelector('[data-testid="stDownloadButton"]');
            if (downloadBtn) downloadBtn.click();
        }}
    }});

    // === IMAGE MODAL ===
    function setupModal() {{
        const images = document.querySelectorAll('.magnifier-container img');
        const modal = document.getElementById('imageModal');
        const modalImg = document.getElementById('modalImage');
        const closeBtn = document.querySelector('.modal-close');
        
        images.forEach(img => {{
            img.onclick = function() {{
                if (modal && modalImg) {{
                    modal.style.display = "block";
                    modalImg.src = this.src;
                }}
            }}
        }});
        
        if (closeBtn) {{
            closeBtn.onclick = function() {{
                modal.style.display = "none";
            }}
        }}
        
        if (modal) {{
            modal.onclick = function(e) {{
                if (e.target === modal) {{
                    modal.style.display = "none";
                }}
            }}
        }}
    }}

    // === MOBILE SWIPE GESTURES ===
    let touchstartX = 0;
    let touchendX = 0;
    
    document.addEventListener('touchstart', e => {{
        touchstartX = e.changedTouches[0].screenX;
    }});
    
    document.addEventListener('touchend', e => {{
        touchendX = e.changedTouches[0].screenX;
        handleSwipe();
    }});
    
    function handleSwipe() {{
        const threshold = 100;
        if (touchendX < touchstartX - threshold) {{
            // Swipe left - next page
            const nextBtn = document.getElementById('mobileNext');
            if (nextBtn) nextBtn.click();
        }}
        if (touchendX > touchstartX + threshold) {{
            // Swipe right - previous page
            const prevBtn = document.getElementById('mobilePrev');
            if (prevBtn) prevBtn.click();
        }}
    }}

    // Run after Streamlit renders
    setTimeout(setupModal, 1000);
    setInterval(setupModal, 2000); // Refresh for dynamic content
    </script>

    <!-- Modal HTML -->
    <div id="imageModal" class="modal">
        <span class="modal-close">&times;</span>
        <img class="modal-content" id="modalImage">
    </div>
""", unsafe_allow_html=True)

# --- 2. CORE SERVICES (SUPABASE & AI) ---
try:
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

# ==========================================
# DEMO MODE (PITCH / TANLOV UCHUN)
# ==========================================
# Eslatma:
# - DEMO_MODE=True bo'lsa, tizimga kirishda parol so'ralmaydi (faqat email).
# - Yangi foydalanuvchi birinchi kirishda avtomatik 50 kredit bilan yaratiladi.
DEMO_MODE = True
DEFAULT_DEMO_CREDITS = 50

def ensure_demo_user(email: str) -> None:
    """Agar foydalanuvchi mavjud bo'lmasa, uni demo krediti bilan yaratadi.

    Muhim:
    - Faqat tanlov/pitch jarayonida qulaylik uchun.
    - Jadval sxemasi noma'lum bo'lgani uchun minimal fieldlar bilan insert qilinadi.
    """
    try:
        # Avval mavjudligini tekshiramiz
        res = db.table("profiles").select("email").eq("email", email).execute()
        if not res.data:
            db.table("profiles").insert({
                "email": email,
                "credits": DEFAULT_DEMO_CREDITS,
            }).execute()
    except Exception:
        # Demo rejimda login to'xtab qolmasligi uchun xatoni yumshoq usulda yutamiz.
        # Kreditlar baribir 0 bo'lib qolishi mumkin (bazaga yozilmasa).
        pass

if not st.session_state.auth:
    # === ENHANCED LOGIN PAGE ===
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.markdown(f"""
            <div class='login-card'>
                <div class='hero-title'>🏛 Manuscript AI</div>
                <div class='hero-subtitle'>
                    Qadimiy qo'lyozmalarni raqamli tahlil qilish va transliteratsiya 
                    qilish uchun sun'iy intellekt asosidagi platforma
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h2 style='margin-top:30px;'>🔐 Tizimga Kirish</h2>", unsafe_allow_html=True)
        
        email_in = st.text_input("📧 Email manzili", placeholder="example@domain.com")

        # DEMO_MODE=True bo'lsa, parol maydoni ko'rsatilmaydi (pitch/tanlov uchun qulay).
        if not DEMO_MODE:
            pwd_in = st.text_input("🔑 Parol", type="password", placeholder="Parolingizni kiriting")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("✨ TIZIMGA KIRISH"):
            if not email_in:
                st.warning("⚠️ Iltimos, email manzilini kiriting")
            elif DEMO_MODE:
                st.session_state.auth = True
                st.session_state.u_email = email_in.strip().lower()
                ensure_demo_user(st.session_state.u_email)
                st.toast("✅ Demo rejimda tizimga kirdingiz!", icon="🎉")
                st.rerun()
            else:
                if pwd_in == CORRECT_PASSWORD:
                    st.session_state.auth = True
                    st.session_state.u_email = email_in.strip().lower()
                    st.toast("✅ Muvaffaqiyatli kirdingiz!", icon="🎉")
                    st.rerun()
                else:
                    st.error("❌ Parol noto'g'ri! Iltimos, qaytadan urinib ko'ring.")
    st.stop()

# --- AI ENGINE (UNCHANGED - DO NOT MODIFY) ---
genai.configure(api_key=GEMINI_KEY)
system_instruction = "Siz Manuscript AI mutaxassisiz. Tadqiqotchi d87809889-dot muallifligida ilmiy tahlillar qilasiz."
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}
model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    system_instruction=system_instruction,
    safety_settings=safety_settings
)

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR (UNCHANGED)
# ==========================================
def enhance_image_for_ai(img: Image.Image):
    """Rasmni AI tahlili uchun optimallashtirish (XATO TUZATILDI)"""
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(2.8)
    img = ImageEnhance.Sharpness(img).enhance(2.5)
    return img

def img_to_png_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return {"mime_type": "image/png", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_live_credits(email: str):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except:
        return 0

def use_credit_atomic(email: str, count: int = 1):
    curr = fetch_live_credits(email)
    if curr >= count:
        db.table("profiles").update({"credits": curr - count}).eq("email", email).execute()
        return True
    return False

@st.cache_data(show_spinner=False)
def render_page(file_content, page_idx, scale, is_pdf):
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            img = pdf[page_idx].render(scale=scale).to_pil()
            pdf.close()
            return img
        return Image.open(io.BytesIO(file_content))
    except:
        return None

# ==========================================
# UI CONSTANTS (DEMO METRICS - NOT LIVE DATA)
# ==========================================
# NOTE: These are placeholder values for demo purposes
DEMO_MANUSCRIPTS_ANALYZED = 2840
DEMO_LANGUAGES_SUPPORTED = 12
DEMO_AVG_TIME_MINUTES = 2.5
DEMO_ACCURACY_RATE = 92.1
DEMO_ACTIVE_USERS = 180
DEMO_COUNTRIES = 4

# ==========================================
# LANDING PAGE FUNCTION (UI ONLY)
# ==========================================
def render_landing_page():
    """Render professional landing page for Hult Prize judges"""
    
    # Hero Section
    st.markdown(f"""
        <div style='text-align:center; padding:60px 20px; background:{card_bg}; 
                    border-radius:20px; box-shadow:0 10px 40px rgba(0,0,0,0.15); margin-bottom:40px;'>
            <h1 style='font-size:clamp(2.5rem, 6vw, 4rem); margin-bottom:20px; border:none; color:{theme['primary']};'>
                🏛 Manuscript AI
            </h1>
            <p style='font-size:clamp(1.2rem, 3vw, 1.8rem); color:{text_secondary}; margin-bottom:30px; line-height:1.6;'>
                Qadimiy qo'lyozmalarni raqamli tahlil qilish va transliteratsiya qilish uchun<br>
                sun'iy intellekt asosidagi akademik platforma
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # CTA Buttons
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        col_demo, col_learn = st.columns(2)
        with col_demo:
            if st.button("▶ DEMO'NI BOSHLASH", key="try_demo_btn", use_container_width=True):
                st.session_state.show_landing = False
                st.rerun()
        with col_learn:
            if st.button("📖 Batafsil Ma'lumot", key="learn_more_btn", use_container_width=True):
                st.session_state.show_landing = False
                st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Three-column layout for Problem/Solution/Impact
    col1, col2, col3 = st.columns(3)
    
    # PROBLEM Section
    with col1:
        st.markdown(f"""
            <div style='background:{card_bg}; padding:30px; border-radius:15px; 
                        border-left:8px solid #e74c3c; box-shadow:0 5px 20px rgba(0,0,0,0.1); min-height:400px;'>
                <h2 style='color:#e74c3c; font-size:1.8rem; margin-bottom:20px; border:none; text-align:left;'>
                    📊 MUAMMO
                </h2>
                <ul style='color:{text_primary}; font-size:1.1rem; line-height:2; list-style:none; padding:0;'>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#e74c3c;'>100M+</span><br>
                        <span style='color:{text_secondary};'>qo'lyozmalar arxivda</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#e74c3c;'>99%</span><br>
                        <span style='color:{text_secondary};'>raqamli emas</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#e74c3c;'>$500-1000</span><br>
                        <span style='color:{text_secondary};'>sahifa uchun xarajat</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#e74c3c;'>2-3 hafta</span><br>
                        <span style='color:{text_secondary};'>manual tahlil vaqti</span>
                    </li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
    
    # SOLUTION Section
    with col2:
        st.markdown(f"""
            <div style='background:{card_bg}; padding:30px; border-radius:15px; 
                        border-left:8px solid #3498db; box-shadow:0 5px 20px rgba(0,0,0,0.1); min-height:400px;'>
                <h2 style='color:#3498db; font-size:1.8rem; margin-bottom:20px; border:none; text-align:left;'>
                    ✨ YECHIM
                </h2>
                <ul style='color:{text_primary}; font-size:1.1rem; line-height:2; list-style:none; padding:0;'>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#3498db;'>AI-powered</span><br>
                        <span style='color:{text_secondary};'>OCR va tahlil</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#3498db;'>2 daqiqa</span><br>
                        <span style='color:{text_secondary};'>tahlil vaqti</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#3498db;'>95%</span><br>
                        <span style='color:{text_secondary};'>aniqlik darajasi</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#3498db;'>$5-10</span><br>
                        <span style='color:{text_secondary};'>sahifa uchun xarajat</span>
                    </li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
    
    # IMPACT Section
    with col3:
        st.markdown(f"""
            <div style='background:{card_bg}; padding:30px; border-radius:15px; 
                        border-left:8px solid #2ecc71; box-shadow:0 5px 20px rgba(0,0,0,0.1); min-height:400px;'>
                <h2 style='color:#2ecc71; font-size:1.8rem; margin-bottom:20px; border:none; text-align:left;'>
                    📈 TA'SIR
                </h2>
                <ul style='color:{text_primary}; font-size:1.1rem; line-height:2; list-style:none; padding:0;'>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#2ecc71;'>{DEMO_MANUSCRIPTS_ANALYZED:,}</span><br>
                        <span style='color:{text_secondary};'>tahlil qilingan</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#2ecc71;'>{DEMO_LANGUAGES_SUPPORTED}</span><br>
                        <span style='color:{text_secondary};'>til qo'llab-quvvatlash</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#2ecc71;'>{DEMO_COUNTRIES}</span><br>
                        <span style='color:{text_secondary};'>mamlakatda foydalanilmoqda</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#2ecc71;'>{DEMO_ACTIVE_USERS:,}</span><br>
                        <span style='color:{text_secondary};'>faol foydalanuvchi</span>
                    </li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # How it Works Section (Expandable)
    with st.expander("📖 QANDAY ISHLAYDI?", expanded=False):
        st.markdown(f"""
            <div style='padding:20px; color:{text_primary};'>
                <h3 style='color:{theme['accent']}; border:none;'>4 Oddiy Qadam:</h3>
                <ol style='font-size:1.1rem; line-height:2;'>
                    <li><b>Yuklash</b> - PDF, PNG, JPG formatidagi qo'lyozma faylini yuklang</li>
                    <li><b>Sozlash</b> - Til, xat turi va rasm sozlamalarini tanlang</li>
                    <li><b>Tahlil</b> - AI 2 daqiqada transliteratsiya va tarjima qiladi</li>
                    <li><b>Export</b> - Natijalarni DOCX, TXT yoki JSON formatida yuklab oling</li>
                </ol>
                <p style='margin-top:20px; font-size:1rem; color:{text_secondary};'>
                    <i>💡 Maslahat: Demo'ni sinab ko'rish uchun yuqoridagi "Demo'ni Boshlash" tugmasini bosing</i>
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    # Footer note
    st.markdown(f"""
        <div style='text-align:center; margin-top:60px; padding:30px; background:{bg_secondary}; border-radius:10px;'>
            <p style='color:{text_secondary}; font-size:0.9rem; margin:0;'>
                📊 Ko'rsatilgan statistik ma'lumotlar demo maqsadida keltirilgan<br>
                🔬 Tadqiqot: d87809889-dot | 📧 Aloqa uchun: {st.session_state.u_email}
            </p>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# 4. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown(f"<h2 style='color:{theme['accent']}; text-align:center; border:none;'>📜 Manuscript AI</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center; color:#fdfaf1; font-size:14px;'>👤 <b>{st.session_state.u_email}</b></p>", unsafe_allow_html=True)
    
    current_credits = fetch_live_credits(st.session_state.u_email)
    
    # Enhanced credit display with progress bar
    st.metric("💳 Mavjud Kredit", f"{current_credits} sahifa")
    credit_percent = min((current_credits / 100) * 100, 100) if current_credits <= 100 else 100
    st.markdown(f"""
        <div class='credit-bar-container'>
            <div class='credit-bar' style='width:{credit_percent}%'></div>
        </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # === DARK MODE TOGGLE ===
    st.markdown("<p class='section-header'>🎨 Dizayn Sozlamalari</p>", unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("🌙 Tungi Rejim" if not st.session_state.dark_mode else "☀️ Kunduzgi Rejim")
    with col2:
        if st.button("🔄", key="dark_toggle"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()
    
    # === COLOR THEME SELECTOR ===
    new_theme = st.selectbox("Rang Sxemasi", list(THEMES.keys()), key="theme_select")
    if new_theme != st.session_state.theme:
        st.session_state.theme = new_theme
        st.rerun()
    
    st.divider()
    
    # Section: Til va Xat
    st.markdown(f"<p class='section-header'>🌍 Til va Xat Tanlash</p>", unsafe_allow_html=True)
    lang = st.selectbox("Qo'lyozma tili", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat turi", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    
    st.divider()
    
    # Section: Rasm Sozlamalari
    st.markdown(f"<p class='section-header'>🎨 Rasm Sozlamalari</p>", unsafe_allow_html=True)
    br = st.slider("☀️ Yorqinlik", 0.5, 2.0, 1.0, 0.1)
    ct = st.slider("🎭 Kontrast", 0.5, 3.0, 1.3, 0.1)
    rot = st.select_slider("🔄 Aylantirish", options=[0, 90, 180, 270], value=0)

    st.divider()
    
    # === COMPARE MODE ===
    st.markdown(f"<p class='section-header'>🔄 Maxsus Rejimlar</p>", unsafe_allow_html=True)
    st.session_state.compare_mode = st.checkbox("🔄 Solishtirish Rejimi", value=st.session_state.compare_mode)
    
    st.divider()
    
    # === HISTORY SIDEBAR ===
    if st.session_state.history:
        with st.expander("📜 Tarix (Oxirgi 10 ta)"):
            for h in st.session_state.history[-10:][::-1]:
                if st.button(f"{h['date']} - {h['filename'][:25]}...", key=f"hist_{h['id']}"):
                    st.session_state.results = h['results']
                    st.session_state.chats = h.get('chats', {})
                    st.toast(f"✅ {h['filename']} yuklandi!", icon="📂")
                    st.rerun()
    
    st.divider()
    
    # KEYBOARD SHORTCUTS INFO
    with st.expander("⌨️ Klaviatura Yorliqlari"):
        st.markdown("""
            - **Esc** - Modal yopish
            - **Ctrl+Enter** - Tahlilni boshlash
            - **Ctrl+S** - Faylni saqlash
        """)
    
    st.divider()
    
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.toast("👋 Xayr!", icon="👋")
        st.rerun()
    
    # Back to Landing button
    if not st.session_state.show_landing:
        if st.button("🏠 Bosh Sahifaga Qaytish", key="back_to_landing"):
            st.session_state.show_landing = True
            st.rerun()

# === LANDING PAGE OR MAIN APP ===
if st.session_state.show_landing:
    render_landing_page()
    st.stop()

# === MAIN CONTENT AREA ===
st.markdown("<h1>📜 Raqamli Qo'lyozmalar Ekspertizasi</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:{text_secondary}; font-size:18px; margin-bottom:30px;'>Sun'iy intellekt yordamida qadimiy matnlarni tahlil qiling va transliteratsiya qiling</p>", unsafe_allow_html=True)

file = st.file_uploader("📤 Qo'lyozma faylini yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="visible")

if not file:
    # === EMPTY STATE ===
    st.markdown(f"""
        <div class='empty-state'>
            <h3 style='font-size:3rem; margin-bottom:20px;'>📜</h3>
            <h3>Qo'lyozma yuklang</h3>
            <p style='color:{text_secondary}; font-size:16px; line-height:1.6;'>
                PDF, PNG, JPG yoki JPEG formatidagi fayllarni yuklashingiz mumkin<br>
                Maksimal 15 sahifagacha tahlil qilish imkoniyati
            </p>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

if file:
    if st.session_state.get("last_fn") != file.name:
        with st.spinner("📂 Fayl tayyorlanmoqda..."):
            data = file.getvalue()
            imgs = []
            if file.type == "application/pdf":
                pdf = pdfium.PdfDocument(data)
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page(data, i, 3.5, True))
                pdf.close()
            else:
                imgs.append(render_page(data, 0, 1.0, False))

            st.session_state.imgs = imgs
            st.session_state.last_fn = file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()
            st.toast("✅ Fayl yuklandi!", icon="📁")

    processed = []
    for im in st.session_state.imgs:
        p = im.rotate(rot, expand=True)
        p = ImageEnhance.Brightness(p).enhance(br)
        p = ImageEnhance.Contrast(p).enhance(ct)
        processed.append(p)

    st.markdown("<h3 style='margin-top:30px;'>📑 Varaqlarni Tanlang</h3>", unsafe_allow_html=True)
    indices = st.multiselect(
        "Tahlil qilish uchun varaqlarni belgilang:",
        range(len(processed)),
        default=[0],
        format_func=lambda x: f"📄 Varaq {x+1}"
    )

    if not st.session_state.results and indices:
        st.markdown("<h3 style='margin-top:30px;'>🖼 Tanlangan Varaqlar</h3>", unsafe_allow_html=True)
        
        # === COMPARE MODE ===
        if st.session_state.compare_mode and len(indices) >= 2:
            st.info("🔄 Solishtirish rejimi: Birinchi 2 ta varaq yonma-yon")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"<h4>📄 Varaq {indices[0]+1}</h4>", unsafe_allow_html=True)
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[indices[0]], use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<h4>📄 Varaq {indices[1]+1}</h4>", unsafe_allow_html=True)
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[indices[1]], use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            cols = st.columns(min(len(indices), 3))
            for i, idx in enumerate(indices):
                with cols[i % 3]:
                    st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                    st.image(processed[idx], caption=f"Varaq {idx+1}", use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
        if current_credits >= len(indices):
            prompt = f"Academic analysis of {lang} manuscript ({era}). 1.Transliteration 2.Translation 3.Expert Notes."
            
            # === PROGRESS TRACKER ===
            progress_bar = st.progress(0, text="🔍 Tahlil boshlanmoqda...")
            
            for i, idx in enumerate(indices):
                with st.status(f"🔍 Varaq {idx+1} ekspertizadan o'tkazilmoqda..."):
                    try:
                        ai_img = enhance_image_for_ai(processed[idx])
                        resp = model.generate_content([prompt, img_to_png_payload(ai_img)])

                        if resp.candidates and resp.candidates[0].content.parts:
                            st.session_state.results[idx] = resp.text
                            use_credit_atomic(st.session_state.u_email)
                            st.toast(f"✅ Varaq {idx+1} tayyor!", icon="🎉")
                            st.success(f"✅ Varaq {idx+1} muvaffaqiyatli tahlil qilindi")
                        else:
                            st.error("⚠️ AI javob berish imkoniyatiga ega emas")
                    except Exception as e:
                        st.error(f"❌ Xatolik yuz berdi: {e}")
                
                # Update progress
                progress_bar.progress((i+1)/len(indices), text=f"📊 {i+1}/{len(indices)} varaq tahlil qilindi")
            
            # Save to history
            st.session_state.history.append({
                'id': datetime.now().timestamp(),
                'date': datetime.now().strftime("%d.%m.%Y %H:%M"),
                'filename': file.name,
                'results': st.session_state.results.copy(),
                'chats': st.session_state.chats.copy()
            })
            
            # Keep only last 10
            if len(st.session_state.history) > 10:
                st.session_state.history = st.session_state.history[-10:]
            
            progress_bar.empty()
            st.balloons()
            st.toast("🎉 Barcha varaqlar tahlil qilindi!", icon="✨")
            st.rerun()
        else:
            st.warning(f"⚠️ Kredit yetarli emas! Sizda {current_credits} sahifa kredit bor, {len(indices)} sahifa tahlil qilish uchun yetarli emas.")

    if st.session_state.results:
        st.divider()
        st.markdown("<h2>📊 Tahlil Natijalari</h2>", unsafe_allow_html=True)
        
        # === EXPORT FORMAT SELECTOR ===
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"<p style='font-size:16px; color:{text_secondary};'>Natijalarni yuklab oling:</p>", unsafe_allow_html=True)
        with col2:
            export_format = st.selectbox("📥 Format", ["DOCX", "TXT", "JSON"], label_visibility="collapsed")
        
        final_text = ""
        today = datetime.now().strftime("%d.%m.%Y")
        
        # Mobile navigation buttons
        result_indices = sorted(st.session_state.results.keys())
        if len(result_indices) > 1:
            nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
            with nav_col1:
                if st.button("⬅️ Oldingi", key="mobilePrev", use_container_width=True):
                    if st.session_state.current_page_index > 0:
                        st.session_state.current_page_index -= 1
                        st.rerun()
            with nav_col3:
                if st.button("Keyingi ➡️", key="mobileNext", use_container_width=True):
                    if st.session_state.current_page_index < len(result_indices) - 1:
                        st.session_state.current_page_index += 1
                        st.rerun()

        for idx in result_indices:
            st.markdown(f"<h4 style='margin-top:40px;'>📖 Varaq {idx+1} - Tahlil</h4>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 1.3])

            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[idx], use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with c2:
                st.markdown(f"<div class='result-box'>{st.session_state.results[idx]}</div>", unsafe_allow_html=True)
                cite = f"Iqtibos: Manuscript AI (2026). Varaq {idx+1} tahlili ({lang}). Ekspert: d87809889-dot. Sana: {today}."
                st.markdown(f"<div class='citation-box'>📌 {cite}</div>", unsafe_allow_html=True)

                st.markdown(f"<p style='color:{text_secondary}; font-weight:bold; margin-top:20px; margin-bottom:8px;'>✏️ Tahrirlash:</p>", unsafe_allow_html=True)
                st.session_state.results[idx] = st.text_area(
                    f"Natijani tahrirlash",
                    value=st.session_state.results[idx],
                    height=350,
                    key=f"ed_{idx}",
                    label_visibility="collapsed"
                )

                final_text += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}\n\n{cite}"

                # === CHAT INTERFACE ===
                st.markdown(f"<p style='color:{text_secondary}; font-weight:bold; margin-top:25px; margin-bottom:12px;'>💬 Savollar va Javoblar:</p>", unsafe_allow_html=True)
                
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>Savol:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>Javob:</b> {ch['a']}</div>", unsafe_allow_html=True)

                q = st.text_input("🤔 Savolingizni yozing:", key=f"q_in_{idx}", placeholder="Matn haqida savol bering...")
                if st.button(f"📤 So'rash", key=f"btn_{idx}"):
                    if q:
                        with st.spinner("🤖 AI javob tayyorlayapti..."):
                            chat_res = model.generate_content([
                                f"Hujjat: {st.session_state.results[idx]}\nQ: {q}",
                                img_to_png_payload(processed[idx])
                            ])
                            st.session_state.chats[idx].append({"q": q, "a": chat_res.text})
                            st.toast("✅ Javob olindi!", icon="💬")
                            st.rerun()
                    else:
                        st.warning("⚠️ Iltimos, avval savol yozing!")

        if final_text:
            st.divider()
            
            # === EXPORT BASED ON FORMAT ===
            if export_format == "DOCX":
                doc = Document()
                doc.add_paragraph(final_text)
                bio = io.BytesIO()
                doc.save(bio)
                st.download_button(
                    "📥 WORD FORMATDA YUKLAB OLISH",
                    bio.getvalue(),
                    "manuscript_ai_report.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    on_click=lambda: st.toast("✅ DOCX yuklab olindi!", icon="📥")
                )
            elif export_format == "TXT":
                st.download_button(
                    "📥 TEXT FORMATDA YUKLAB OLISH",
                    final_text,
                    "manuscript_ai_report.txt",
                    mime="text/plain",
                    on_click=lambda: st.toast("✅ TXT yuklab olindi!", icon="📥")
                )
            elif export_format == "JSON":
                json_data = json.dumps({
                    "metadata": {
                        "date": today,
                        "language": lang,
                        "script": era,
                        "filename": file.name,
                        "user": st.session_state.u_email
                    },
                    "results": st.session_state.results,
                    "chats": st.session_state.chats
                }, ensure_ascii=False, indent=2)
                st.download_button(
                    "📥 JSON FORMATDA YUKLAB OLISH",
                    json_data,
                    "manuscript_ai_report.json",
                    mime="application/json",
                    on_click=lambda: st.toast("✅ JSON yuklab olindi!", icon="📥")
                )

gc.collect()
