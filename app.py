import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA AKADEMIK MUHIT SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Master 2025", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
# Tahrirlash oynasidagi matnni qora va fonni pergament qilish uchun maxsus ishlov berildi
st.markdown("""
    <style>
    /* Ortiqcha reklamalarni yashirish */
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;} .stAppDeployButton {display:none !important;}

    /* Pergament fon va shriftlar */
    .main { 
        background-color: #f4ecd8 !important; 
        color: #1a1a1a !important;
        font-family: 'Times New Roman', serif;
    }

    h1, h2, h3, h4 {
        color: #0c1421 !important;
        font-family: 'Georgia', serif;
        border-bottom: 2px solid #c5a059;
        text-align: center;
    }

    /* AI TAHLIL KARTASI (Chatbot uslubi) */
    .result-box {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        border-left: 10px solid #c5a059;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        color: #1a1a1a !important;
        font-size: 17px;
        line-height: 1.7;
        margin-bottom: 15px;
    }

    /* TAHRIRLASH OYNASI (TEXT AREA) - MATN ANIQ QORA VA KO'RINARLI */
    .stTextArea textarea {
        background-color: #fdfaf1 !important;
        color: #000000 !important; /* MATN RANGI QORA */
        border: 2px solid #c5a059 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 18px !important;
        padding: 20px !important;
        border-radius: 8px !important;
    }

    /* Sidebar dizayni */
    section[data-testid="stSidebar"] {
        background-color: #0c1421 !important;
        border-right: 2px solid #c5a059;
    }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }

    /* Tugmalar */
    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%);
        color: #c5a059 !important;
        border: 2px solid #c5a059;
        font-weight: bold;
        padding: 12px;
        width: 100%;
        text-transform: uppercase;
    }
    .stButton>button:hover {
        background: #c5a059 !important;
        color: #0c1421 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Google Search Console Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# --- 3. XAVFSIZLIK VA KIRISH ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Streamlit Cloud-dan GEMINI_API_KEY va APP_PASSWORD ni kiriting.")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kod", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Xato kod!")
    st.stop()

# --- 4. AI MODELINI XATOSIZ SOZLASH (Fallback Tizimi) ---
genai.configure(api_key=GEMINI_KEY)

# 404 Xatosini yo'qotish uchun modelni bir necha nom bilan tekshiramiz
@st.cache_resource
def load_model():
    model_names = ["gemini-1.5-flash-latest", "gemini-flash-latest", "gemini-1.5-flash"]
    for name in model_names:
        try:
            m = genai.GenerativeModel(name)
            # Test so'rovi (model borligini tekshirish uchun)
            return m
        except:
            continue
    return genai.GenerativeModel("gemini-pro-vision") # Oxirgi chora

model = load_model()

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.markdown("---")
    lang = st.selectbox("Hujjat tili:", ["Chig'atoy (Eski o'zbek)", "Fors (Klassik)", "Arab (Ilmiy)", "Usmonli Turk"])
    era = st.selectbox("Paleografik uslub:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.markdown("---")
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar bo'yicha Ilmiy Ekspertiza</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Ilmiy manbani yuklang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    if 'images' not in st.session_state or st.session_state.get('last_file') != uploaded_file.name:
        images = []
        if uploaded_file.type == "application/pdf":
            with st.spinner('Raqamlashtirilmoqda (DPI 300)...'):
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(len(pdf)):
                    images.append(pdf[i].render(scale=3).to_pil())
        else:
            images.append(Image.open(uploaded_file))
        st.session_state['images'] = images
        st.session_state['last_file'] = uploaded_file.name

    st.markdown("### 📜 Yuklangan sahifalar")
    cols = st.columns(min(len(st.session_state['images']), 4))
    for idx, img in enumerate(st.session_state['images']):
        cols[idx % 4].image(img, caption=f"Sahifa {idx+1}", use_container_width=True)

    if st.button('✨ CHUQUR AKADEMIK TAHLILNI BOSHLASH'):
        st.session_state['academic_results'] = []
        # Eng kuchli akademik prompt
        prompt = f"""
        Siz qadimgi matnshunos va paleograf bo'yicha dunyo darajasidagi akademiksiz. 
        Ushbu {lang} tilidagi va {era} uslubidagi manbani quyidagi mezonlar asosida tahlil qiling:
        1. PALEOGRAFIK TAVSIF: Yozuv turi, xatning o'ziga xos xususiyatlari.
        2. DIPLOMATIK TRANSLITERATSIYA: Matnni harfma-harf lotin alifbosiga ko'chiring.
        3. SEMANTIK TARJIMA: Ma'nosini zamonaviy o'zbek tiliga ilmiy va badiiy mahorat bilan o'giring.
        4. ILMIY IZOH: Tarixiy shaxslar, joy nomlari va arxaik terminlarga akademik sharh bering.
        """
        
        for i, img in enumerate(st.session_state['images']):
            with st.status(f"Sahifa {i+1} ekspertizadan o'tmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state['academic_results'].append(response.text)
                    status.update(label=f"Sahifa {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato (Sahifa {i+1}): {e}")

    # --- 6. OPTIMALLASHGAN SIDE-BY-SIDE + FULL WIDTH EDITOR ---
    if 'academic_results' in st.session_state and len(st.session_state['academic_results']) > 0:
        st.divider()
        st.markdown("### 🖋 Natijalar va Ilmiy Tahrir")
        
        final_academic_report = ""
        for idx, (img, res) in enumerate(zip(st.session_state['images'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Sahifa {idx+1}")
            
            # 1-qator: Rasm va AI natijasi yonma-yon
            col_img, col_res = st.columns([1, 1.2])
            with col_img:
                st.image(img, use_container_width=True, caption=f"Asl manba {idx+1}")
            with col_res:
                st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            # 2-qator: Tahrirlash oynasi (Full width, qora matn)
            st.write("**Ushbu sahifa bo'yicha tahrirlangan yakuniy matn:**")
            edited_val = st.text_area("", value=res, height=450, key=f"edit_{idx}", label_visibility="collapsed")
            final_academic_report += f"\n\n--- SAHIFA {idx+1} ---\n{edited_val}"
            st.markdown("---")

        # WORD EXPORT
        if final_academic_report:
            doc = Document()
            doc.add_heading('Manuscript AI: Professional Akademik Hisobot', 0)
            doc.add_paragraph(f"Ilmiy soha: {lang} | Paleografiya: {era}")
            doc.add_paragraph(final_academic_report)
            
            bio = io.BytesIO()
            doc.save(bio)
            
            st.divider()
            st.download_button(
                label="📥 AKADEMIK HISOBOTNI WORDDA YUKLAB OLISH",
                data=bio.getvalue(),
                file_name="academic_analysis_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.balloons()
