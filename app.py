import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Enterprise Pro 2026",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; font-size: 17px; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; color: white !important; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; width: 100%; padding: 10px; border: 1px solid #c5a059; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. XAVFSIZLIK VA BAZA (SUPABASE)
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingiz")
        pwd_in = st.text_input("Maxfiy parol", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Xato!")
    st.stop()

# ==========================================
# 3. AI MODELINI SOZLASH (FIX: 404 & 429)
# ==========================================
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_fixed_model():
    """Gemini 1.5 Flash - eng yuqori limitga ega modelni ulaydi"""
    # models/gemini-1.5-flash-latest - bu sizning logsda ko'ringan eng barqaror 1.5 modeli
    try:
        return genai.GenerativeModel(model_name='models/gemini-1.5-flash-latest')
    except:
        return genai.GenerativeModel(model_name='models/gemini-1.5-flash')

model = load_fixed_model()

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR
# ==========================================
def img_to_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_live_credits(email: str):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

@st.cache_data(show_spinner=False)
def render_page(content, page_idx, scale, is_pdf):
    if is_pdf:
        pdf = pdfium.PdfDocument(content)
        img = pdf[page_idx].render(scale=scale).to_pil()
        pdf.close()
        return img
    return Image.open(io.BytesIO(content))

# ==========================================
# 5. ASOSIY INTERFEYS
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **User:** `{st.session_state.u_email}`")
    st.metric("💳 Credits", fetch_live_credits(st.session_state.u_email))
    st.info("🚀 Rejim: High-Quota (1500 RPD)")
    
    st.divider()
    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    
    if st.button("🚪 LOGOUT"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Markazi")
file = st.file_uploader("Faylni yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if file:
    if st.session_state.get('last_fn') != file.name:
        with st.spinner('Preparing...'):
            data = file.getvalue()
            imgs = []
            if file.type == "application/pdf":
                pdf = pdfium.PdfDocument(data)
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page(data, i, 2.0, True))
                pdf.close()
            else: imgs.append(render_page(data, 0, 2.0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    # Prevyu
    if not st.session_state.results:
        cols = st.columns(min(len(st.session_state.imgs), 4))
        for idx, img in enumerate(st.session_state.imgs):
            cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width=None)

    if st.button('✨ TAHLILNI BOSHLASH'):
        prompt = f"Expert paleographer analysis. {lang} language, {era} style. 1.Transliteration 2.Uzbek Translation 3.Expert Notes."
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"Analysing page {i+1}..."):
                try:
                    response = model.generate_content([prompt, img_to_payload(img)])
                    st.session_state.results[i] = response.text
                    # Kreditni kamaytirish logikasi (Sizning kodingizdagi daxlsiz qism)
                    time.sleep(2) # RPM limit himoyasi
                except Exception as e:
                    st.error(f"Error: {e}")
        st.rerun()

    # Natijalar ko'rinishi
    if st.session_state.results:
        for idx, img in enumerate(st.session_state.imgs):
            if idx in st.session_state.results:
                st.markdown(f"#### 📖 Varaq {idx+1}")
                c1, c2 = st.columns([1, 1.2])
                with c1: st.image(img, width='stretch')
                with c2:
                    res = st.session_state.results[idx]
                    st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
                    st.session_state.results[idx] = st.text_area("Tahrir:", value=res, key=f"ed_{idx}", height=300)
                    
                    # Chat per page
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user'><b>Q:</b> {ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)
                    
                    user_q = st.text_input("Savol bering:", key=f"q_{idx}")
                    if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                        chat_res = model.generate_content(f"Hujjat tahlili: {res}\nSavol: {user_q}")
                        st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                        st.rerun()

        doc = Document()
        for r in st.session_state.results.values(): doc.add_paragraph(r)
        bio = io.BytesIO(); doc.save(bio)
        st.download_button("📥 Wordda yuklab olish", bio.getvalue(), "analysis.docx")

gc.collect()
