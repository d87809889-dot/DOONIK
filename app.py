import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
import gc
import asyncio
import base64
import hashlib
import time
from datetime import datetime
from docx import Document

# --- 1. KONFIGURATSIYA VA DIZAYN ---
st.set_page_config(
    page_title="Manuscript AI - Academic Pro",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Antik-akademik dizayn (CSS)
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; padding-bottom: 10px; }
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        color: #1a1a1a; line-height: 1.7; font-size: 18px;
    }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000 !important; border: 1px solid #c5a059 !important; }
    .chat-bubble-user { background-color: #e2e8f0; color: black; padding: 12px; border-radius: 10px; margin: 5px 0; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: black; padding: 12px; border-radius: 10px; margin: 5px 0; border: 1px solid #d4af37; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; border: none; padding: 12px; }
    [data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    </style>
""", unsafe_allow_html=True)

# --- 2. XAVFSIZLIK (FAQAT PAROL BILAN) ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    # Faqat ikkita asosiy sir kerak
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Streamlit Settings -> Secrets qismini tekshiring.")
    st.stop()

# Tizimga kirish oynasi (Oldingidek)
if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🔐 Manuscript AI: Kirish</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("Tizimga kirish"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Xato parol kiritildi!")
    st.stop()

# --- 3. AI MODELINI SOZLASH (404 XATOSINI YO'QOTISH) ---
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def get_working_model():
    """Googledan hozirgi ishlayotgan modelni so'rab, ulaydi"""
    try:
        # Ruxsat etilgan modellarni olish
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Eng barqaror nomlarni qidirish
        targets = ['models/gemini-1.5-flash', 'models/gemini-1.5-flash-latest', 'models/gemini-pro']
        for t in targets:
            if t in available:
                return genai.GenerativeModel(model_name=t)
        return genai.GenerativeModel(model_name=available[0])
    except:
        return genai.GenerativeModel(model_name='models/gemini-1.5-flash')

model = get_working_model()

# --- 4. YORDAMCHI FUNKSIYALAR ---

def get_file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()

@st.cache_data(show_spinner=False)
def render_page_optimized(file_content: bytes, page_idx: int, scale: float, is_pdf: bool) -> Image.Image:
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            page = pdf[page_idx]
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil()
            pdf.close()
            gc.collect()
            return img
        else:
            return Image.open(io.BytesIO(file_content))
    except: return None

def img_to_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

async def call_ai_async(prompt: str, img: Image.Image):
    """Asinxron AI chaqiruvi"""
    try:
        payload = img_to_payload(img)
        response = await asyncio.to_thread(model.generate_content, [prompt, payload])
        return response.text
    except Exception as e:
        return f"🚨 AI Xatosi: {str(e)}"

# --- 5. ASOSIY INTERFEYS ---

with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    if st.button("🚪 Tizimdan chiqish"):
        st.session_state["authenticated"] = False
        st.rerun()

st.title("📜 Qo'lyozmalar Ekspertiza Markazi")
uploaded_file = st.file_uploader("Faylni yuklang (PDF, JPG, PNG)", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'res_store' not in st.session_state: st.session_state.res_store = {}
if 'chat_store' not in st.session_state: st.session_state.chat_store = {}

if uploaded_file:
    file_bytes = uploaded_file.getvalue()
    file_id = get_file_hash(file_bytes)
    is_pdf = uploaded_file.type == "application/pdf"
    
    if is_pdf:
        pdf_m = pdfium.PdfDocument(file_bytes)
        t_pages = len(pdf_m)
        pdf_m.close()
        col_p, col_z = st.columns(2)
        p_idx = col_p.number_input(f"Sahifa (1-{t_pages}):", 1, t_pages) - 1
        z_val = col_z.slider("Zoom:", 1.0, 4.0, 2.5)
    else:
        p_idx = 0
        z_val = st.slider("Zoom:", 1.0, 3.0, 1.5)

    state_key = f"{file_id}_{p_idx}"
    st.session_state.chat_store.setdefault(state_key, [])

    col_img, col_info = st.columns([1, 1.2])
    img = render_page_optimized(file_bytes, p_idx, z_val, is_pdf)

    if img:
        with col_img:
            st.image(img, use_container_width=True, caption=f"Varaq: {p_idx + 1}")
            if state_key in st.session_state.res_store:
                doc = Document()
                doc.add_paragraph(st.session_state.res_store[state_key])
                bio = io.BytesIO(); doc.save(bio)
                st.download_button("📥 Wordda yuklash", bio.getvalue(), f"tahlil_{state_key}.docx")

        with col_info:
            t_anal, t_chat = st.tabs(["🖋 Tahlil", "💬 Chat"])
            
            with t_anal:
                if st.button("✨ Tahlilni boshlash"):
                    with st.status("AI ishlamoqda...") as status:
                        prompt = f"Siz matnshunos akademiksiz. {lang} va {style} uslubidagi qo'lyozmani tahlil qiling: 1.Transliteratsiya 2.Tarjima 3.Izoh."
                        res = asyncio.run(call_ai_async(prompt, img))
                        st.session_state.res_store[state_key] = res
                        status.update(label="✅ Tayyor!", state="complete")
                        st.rerun()

                if state_key in st.session_state.res_store:
                    new_val = st.text_area("Tahrirlash:", value=st.session_state.res_store[state_key], height=450, key=f"ar_{state_key}")
                    st.session_state.res_store[state_key] = new_val

            with t_chat:
                c_container = st.container(height=400)
                for m in st.session_state.chat_store[state_key]:
                    c_container.chat_message(m["role"]).write(m["content"])

                if u_q := st.chat_input("Savol bering...", key=f"q_{state_key}"):
                    st.session_state.chat_store[state_key].append({"role": "user", "content": u_q})
                    with st.spinner("O'ylanmoqda..."):
                        ctx = st.session_state.res_store.get(state_key, "Tahlil yo'q.")
                        ans = asyncio.run(call_ai_async(f"Kontekst: {ctx}\n\nSavol: {u_q}", img))
                        st.session_state.chat_store[state_key].append({"role": "assistant", "content": ans})
                        st.rerun()
    gc.collect()
