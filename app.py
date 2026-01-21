import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# ==========================================
# 1. KONFIGURATSIYA VA SEO
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Global Enterprise",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- REKLAMALARNI YASHIRISH VA DIZAYN ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; padding-bottom: 10px; }
    .result-box { background: #fff !important; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #000; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000 !important; border: 1px solid #c5a059 !important; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; width: 100%; border-radius: 8px; }
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 10px; cursor: zoom-in; }
    .magnifier-container img:hover { transform: scale(2.2); transition: 0.3s ease; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. BAZA VA AUTH (GOOGLE OAUTH FIX)
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

# Sessiyani xotirada saqlash (F5 tugmasi uchun)
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False
if "user_data" not in st.session_state:
    st.session_state.user_data = None

def login_with_google():
    """Google OAuth orqali kirish (Sassion Conflict hal qilindi)"""
    res = db.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {"redirect_to": st.secrets["REDIRECT_URL"]}
    })
    st.markdown(f'<meta http-equiv="refresh" content="0;url={res.url}">', unsafe_allow_html=True)
    st.stop()

# URL'dan foydalanuvchi ma'lumotlarini olish (Supabase callback)
try:
    session = db.auth.get_session()
    if session:
        st.session_state.user_authenticated = True
        st.session_state.user_data = session.user
except:
    pass

# ==========================================
# 3. AI MOTOR VA FUNKSIYALAR
# ==========================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-flash-latest')

def fetch_live_credits(email: str):
    """Supabase orqali kreditlarni tekshirish"""
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

def log_activity(email, action):
    """Admin monitoring uchun log yozish"""
    try:
        db.table("usage_logs").insert({"email": email, "action": action}).execute()
    except: pass

@st.cache_data(show_spinner=False)
def render_page(content, page_idx, scale, is_pdf):
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(content)
            img = pdf[page_idx].render(scale=scale).to_pil()
            pdf.close()
            return img
        return Image.open(io.BytesIO(content))
    except: return None

# ==========================================
# 4. SIDEBAR (BOSHQUV PANELI)
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    
    if not st.session_state.user_authenticated:
        st.markdown("### 🔑 Tizimga kirish")
        st.caption("Professional tahlil va yuklab olish uchun kiring.")
        if st.button("🌐 Google orqali kirish"):
            login_with_google()
    else:
        st.write(f"👤 **{st.session_state.user_data.email}**")
        credits = fetch_live_credits(st.session_state.user_data.email)
        st.metric("💳 Balans", f"{credits} Kredit")
        
        if st.button("🚪 Tizimdan chiqish"):
            db.auth.sign_out()
            st.session_state.clear()
            st.rerun()

    st.divider()
    # SOZLAMALAR
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    mode = st.radio("Tahlil rejimi:", ["Diplomatik", "Semantik"])
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)

# ==========================================
# 5. ASOSIY ILOVA (BUSINESS LOGIC)
# ==========================================
st.title("📜 Digital Manuscript Enterprise")
st.write("Professional raqamli paleografiya tizimi.")

uploaded_file = st.file_uploader("Faylni tanlang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if uploaded_file:
    file_bytes = uploaded_file.getvalue()
    is_pdf = uploaded_file.type == "application/pdf"
    
    if is_pdf:
        pdf = pdfium.PdfDocument(file_bytes)
        p_count = len(pdf); pdf.close()
        selected_pages = st.multiselect("Sahifalar:", options=range(p_count), default=[0], format_func=lambda x: f"{x+1}-bet")
    else:
        selected_pages = [0]

    # --- TAHLIL ---
    if st.button('✨ Tahlilni boshlash'):
        # Admin monitoring: Kim nima yukladi?
        current_email = st.session_state.user_data.email if st.session_state.user_authenticated else "Mehmon"
        log_activity(current_email, f"Tahlil: {uploaded_file.name}")
        
        if not st.session_state.user_authenticated and len(selected_pages) > 1:
            st.warning("⚠️ Mehmonlar faqat 1 sahifani tahlil qila oladilar. Davom etish uchun Google orqali kiring!")
        else:
            for idx in selected_pages:
                with st.status(f"{idx+1}-bet...") as s:
                    img = render_page(file_bytes, idx, 2.5, is_pdf)
                    # Tasvirga ishlov berish
                    img = ImageEnhance.Brightness(img).enhance(brightness)
                    img = ImageEnhance.Contrast(img).enhance(contrast)
                    
                    buf = io.BytesIO(); img.save(buf, format="JPEG")
                    payload = {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode("utf-8")}
                    
                    prompt = f"Expert analysis ({lang}, {mode}): Transliteration, Translation, Historical Note."
                    response = model.generate_content([prompt, payload])
                    
                    st.image(img, use_container_width=True)
                    st.markdown(f"<div class='result-box'>{response.text}</div>", unsafe_allow_html=True)
                    
                    if st.session_state.user_authenticated:
                        # Kreditlarni kamaytirish (Atomic Update)
                        db.table("profiles").update({"credits": credits - 1}).eq("email", current_email).execute()
                    
                    s.update(label="Tayyor!", state="complete")

            if not st.session_state.user_authenticated:
                st.info("💡 To'liq Word hisobotni yuklab olish uchun tizimga kiring.")
            else:
                st.balloons()
