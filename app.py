import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA AKADEMIK MUHIT SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Master 2026", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK-AKADEMIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;} .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; }
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; font-size: 18px; }
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #d4af37; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%); color: #c5a059 !important; font-weight: bold; width: 100%; padding: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK VA KIRISH ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Settings > Secrets qismini tekshiring.")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kod", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Xato!")
    st.stop()

# --- 4. MODELNI TO'G'RI TANLASH (LOGS ASOSIDA) ---
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_verified_model():
    """Logsda ko'ringan ishchi modellardan birini tanlaydi"""
    # Sizning ro'yxatingizdagi ishlaydigan nomlar
    working_models = ["gemini-flash-latest", "gemini-2.0-flash", "gemini-pro-latest"]
    for name in working_models:
        try:
            return genai.GenerativeModel(name)
        except:
            continue
    return genai.GenerativeModel("gemini-1.5-flash") # Oxirgi chora

model = load_verified_model()

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertiza Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Ilmiy manbani yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state['imgs'] = []
if 'academic_results' not in st.session_state: st.session_state['academic_results'] = []
if 'chat_histories' not in st.session_state: st.session_state['chat_histories'] = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        imgs = []
        if uploaded_file.type == "application/pdf":
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                imgs.append(pdf[i].render(scale=3).to_pil())
        else:
            imgs.append(Image.open(uploaded_file))
        st.session_state['imgs'] = imgs
        st.session_state['last_fn'] = uploaded_file.name
        st.session_state['academic_results'] = []
        st.session_state['chat_histories'] = {}

    cols = st.columns(min(len(st.session_state['imgs']), 4))
    for idx, img in enumerate(st.session_state['imgs']):
        # Ogohlantirishni yo'qotish uchun width='stretch' ishlatamiz
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width=None)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        new_results = []
        prompt = f"""
        Siz qadimiy matnshunos akademiksiz. {lang} va {era} uslubidagi qo'lyozmani tahlil qiling: 
        1.Paleografiya. 2.Transliteratsiya (lotin). 3.Ma'noviy tarjima. 4.Ilmiy izoh.
        """
        for i, img in enumerate(st.session_state['imgs']):
            with st.status(f"Varaq {i+1} o'qilmoqda..."):
                try:
                    response = model.generate_content([prompt, img])
                    new_results.append(response.text)
                except Exception as e:
                    new_results.append(f"Xato: {e}")
        st.session_state['academic_results'] = new_results

    # --- 6. TAHLIL VA CHAT ---
    if st.session_state['academic_results']:
        st.divider()
        final_text = ""
        for idx, (img, res) in enumerate(zip(st.session_state['imgs'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, width=None)
            with c2: st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            ed_val = st.text_area(f"Varaq {idx+1} bo'yicha tahrir:", value=res, height=400, key=f"ed_{idx}")
            final_text += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

            # Interaktiv Chat
            st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan muloqot")
            chat_id = f"chat_{idx}"
            if chat_id not in st.session_state['chat_histories']: st.session_state['chat_histories'][chat_id] = []

            for chat in st.session_state['chat_histories'][chat_id]:
                st.markdown(f"<div class='chat-bubble-user'><b>Savol:</b> {chat['q']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='chat-bubble-ai'><b>AI:</b> {chat['a']}</div>", unsafe_allow_html=True)

            user_q = st.text_input(f"Savol yozing ({idx+1}):", key=f"q_in_{idx}")
            if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                if user_q:
                    chat_prompt = f"Ushbu qo'lyozma bo'yicha savolga akademik javob ber: {user_q}\nMatn: {ed_val}"
                    chat_res = model.generate_content([chat_prompt, img])
                    st.session_state['chat_history'][chat_id].append({"q": user_q, "a": chat_res.text})
                    st.rerun()
            st.markdown("---")

        if final_text:
            doc = Document()
            doc.add_paragraph(final_text)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")
