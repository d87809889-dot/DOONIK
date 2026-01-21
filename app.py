import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64, asyncio
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI Enterprise v2.7",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="auto"
)

# --- PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; padding-bottom: 10px; }
    
    /* Mobil qurilmalar uchun moslashuvchanlik */
    @media (max-width: 768px) {
        .main .block-container { padding-top: 3.5rem !important; }
    }
    
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border-left: 10px solid #c5a059; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        color: #1a1a1a; font-size: 17px; line-height: 1.8;
    }
    
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000 !important; border: 1px solid #c5a059 !important; font-size: 16px; }
    .chat-user { background-color: #e2e8f0; color: #000; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; color: white !important; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; width: 100% !important; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CORE SERVICES (DAXLSIZ QISMLAR)
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

# Session states
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""
if "imgs" not in st.session_state: st.session_state.imgs = []
if "results" not in st.session_state: st.session_state.results = {}
if "chat_history" not in st.session_state: st.session_state.chat_history = {}

# --- 3. XAVFSIZLIK VA AUTH ---
if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == st.secrets["APP_PASSWORD"]:
                st.session_state.auth = True
                st.session_state.u_email = email_in
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop()

# --- AI INTEGRATSIYA ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(model_name="gemini-1.5-flash-002")

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR
# ==========================================
def img_to_payload(img):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_credits(email):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

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
# 5. SIDEBAR VA TADQIQOT SOZLAMALARI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
    live_credits = fetch_credits(st.session_state.u_email)
    st.metric("💳 Qolgan kredit", f"{live_credits} sahifa")
    st.divider()
    
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    br = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    ct = st.slider("Kontrast:", 0.5, 3.0, 1.2)
    
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

# ==========================================
# 6. ASOSIY INTERFEYS
# ==========================================
st.title("📜 Raqamli Qo'lyozmalar Ekspertiza Markazi")

uploaded_file = st.file_uploader("Manbani yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

if uploaded_file:
    # Fayl yangilansa, xotirani tozalash (Memory Guard)
    if st.session_state.get("last_fn") != uploaded_file.name:
        with st.spinner("Fayl tayyorlanmoqda..."):
            data = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(data)
                # Maksimal 15 sahifa barqarorlik uchun
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page(data, i, 2.0, True))
                pdf.close()
            else:
                imgs.append(render_page(data, 0, 2.0
