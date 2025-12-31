import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SAHIFA VA SEO SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Professional Academic Master", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;} .stAppDeployButton {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; font-size: 17px; }
    
    /* TAHRIRLASH OYNASI - MATN QORA VA ANIQ */
    .stTextArea textarea {
        background-color: #fdfaf1 !important;
        color: #000000 !important; 
        border: 2px solid #c5a059 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 18px !important;
        padding: 20px !important;
    }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%); color: #c5a059 !important; border: 2px solid #c5a059; font-weight: bold; width: 100%; padding: 12px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Streamlit Cloud sozlamalariga kiring.")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2 style='border:none;'>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kod", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Xato!")
    st.stop()

# --- 4. MODELNI AVTOMATIK ANIQLASH (XATONI YO'QOTISH) ---
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def get_working_model():
    """Google serveridan hozirgi ishlayotgan modelni qidirib topadi"""
    try:
        # Avval ro'yxatni olamiz
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Eng yaxshi variantlarni tartib bilan tekshiramiz
        targets = ["models/gemini-1.5-flash-latest", "models/gemini-2.0-flash", "models/gemini-1.5-flash", "models/gemini-pro-vision"]
        
        for target in targets:
            if target in available_models:
                return genai.GenerativeModel(target)
        
        # Agar hech biri topilmasa, ro'yxatdagi birinchi flash modelni olamiz
        for m in available_models:
            if 'flash' in m:
                return genai.GenerativeModel(m)
        
        return genai.GenerativeModel(available_models[0])
    except Exception as e:
        st.error(f"Modelni yuklashda xato: {e}")
        return None

model = get_working_model()

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Til:", ["Chig'atoy", "Fors", "Arab", "Eski Turkiy"])
    era = st.selectbox("Uslub:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertizasi</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Manbani yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    if 'images' not in st.session_state or st.session_state.get('last_file') != uploaded_file.name:
        images = []
        if uploaded_file.type == "application/pdf":
            with st.spinner('Raqamlashtirilmoqda...'):
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(len(pdf)):
                    images.append(pdf[i].render(scale=3).to_pil())
        else:
            images.append(Image.open(uploaded_file))
        st.session_state['images'] = images
        st.session_state['last_file'] = uploaded_file.name

    st.markdown("### 📜 Yuklangan varaqlar")
    cols = st.columns(min(len(st.session_state['images']), 4))
    for idx, img in enumerate(st.session_state['images']):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ CHUQUR AKADEMIK TAHLILNI BOSHLASH'):
        if model is None:
            st.error("AI modeli ulanmadi. API kalitini tekshiring.")
        else:
            st.session_state['academic_results'] = []
            prompt = f"""
            Siz qo'lyozmalar bo'yicha dunyo darajasidagi akademiksiz. 
            Ushbu {lang} tilidagi va {era} uslubidagi manbani tahlil qiling:
            1. PALEOGRAFIK TAVSIF. 2. TRANSLITERATSIYA (Lotin). 3. SEMANTIK TARJIMA. 4. ILMIY IZOH.
            """
            for i, img in enumerate(st.session_state['images']):
                with st.status(f"Varaq {i+1} ekspertizadan o'tmoqda..."):
                    try:
                        response = model.generate_content([prompt, img])
                        st.session_state['academic_results'].append(response.text)
                    except Exception as e:
                        st.error(f"Xato: {e}")

    # --- 6. EDITOR ---
    if 'academic_results' in st.session_state and len(st.session_state['academic_results']) > 0:
        st.divider()
        final_report = ""
        for idx, (img, res) in enumerate(zip(st.session_state['images'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, use_container_width=True)
            with c2: st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
            
            edited = st.text_area(f"Tahrir {idx+1}:", value=res, height=400, key=f"ed_{idx}")
            final_report += f"\n\n--- VARAQ {idx+1} ---\n{edited}"

        if final_report:
            doc = Document()
            doc.add_heading('Academic Report', 0)
            doc.add_paragraph(final_report)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLASH", bio.getvalue(), "report.docx")
            st.balloons()
