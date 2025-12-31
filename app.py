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

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    /* Reklamalarni yashirish */
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;} .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}

    /* Pergament foni */
    .main { 
        background-color: #f4ecd8 !important; 
        color: #1a1a1a !important;
        font-family: 'Times New Roman', serif;
    }

    h1, h2, h3 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }

    /* TAHRIRLASH OYNASI - MATN QORA VA ANIQ */
    .stTextArea textarea {
        background-color: #fdfaf1 !important;
        color: #000000 !important; 
        border: 2px solid #c5a059 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 18px !important;
        padding: 20px !important;
    }

    /* AI TAHLIL KARTASI */
    .result-box {
        background-color: #ffffff !important;
        padding: 25px !important;
        border-radius: 12px !important;
        border-left: 10px solid #c5a059 !important;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important;
        font-size: 17px !important;
    }

    /* Sidebar va Tugmalar */
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important; border: 2px solid #c5a059 !important;
        font-weight: bold !important; width: 100% !important; padding: 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Streamlit Settings > Secrets bo'limini tekshiring.")
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

# --- 4. AI MODELINI BARQAROR SOZLASH (FIX 404/429) ---
genai.configure(api_key=GEMINI_KEY)

def load_robust_model():
    """Modellarni tartib bilan tekshiradi, 404 va 429 xatolarini chetlab o'tadi"""
    # Eng barqaror modellarni sinash tartibi
    model_options = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro-vision"]
    
    for m_name in model_options:
        try:
            m = genai.GenerativeModel(m_name)
            return m
        except:
            continue
    return None

model = load_robust_model()

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertiza Markazi</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Ilmiy manbani yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    if 'images' not in st.session_state or st.session_state.get('last_file') != uploaded_file.name:
        images = []
        if uploaded_file.type == "application/pdf":
            with st.spinner('DPI 300 sifatda raqamlashtirilmoqda...'):
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(len(pdf)):
                    images.append(pdf[i].render(scale=3).to_pil())
        else:
            images.append(Image.open(uploaded_file))
        st.session_state['images'] = images
        st.session_state['last_file'] = uploaded_file.name

    st.markdown("### 📜 Varaqlar")
    cols = st.columns(min(len(st.session_state['images']), 4))
    for idx, img in enumerate(st.session_state['images']):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        if model is None:
            st.error("AI modelini yuklab bo'lmadi. API kalitini tekshiring.")
        else:
            st.session_state['academic_results'] = []
            prompt = f"""
            Siz matnshunos va paleograf bo'yicha dunyo darajasidagi akademiksiz. 
            Ushbu {lang} tilidagi va {era} uslubidagi manbani quyidagi mezonlar asosida tahlil qiling:
            1. PALEOGRAFIK TAVSIF. 2. DIPLOMATIK TRANSLITERATSIYA. 3. SEMANTIK TARJIMA. 4. ILMIY IZOH.
            Javobni o'ta professional akademik tilda bering.
            """
            
            for i, img in enumerate(st.session_state['images']):
                with st.status(f"Varaq {i+1} ekspertizadan o'tmoqda...") as status:
                    try:
                        response = model.generate_content([prompt, img])
                        st.session_state['academic_results'].append(response.text)
                        status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                    except Exception as e:
                        st.error(f"Xato (Varaq {idx+1}): {e}")

    # --- 6. SIDE-BY-SIDE + EDITOR ---
    if 'academic_results' in st.session_state and len(st.session_state['academic_results']) > 0:
        st.divider()
        st.markdown("### 🖋 Natijalar va Ilmiy Tahrir")
        
        final_report = ""
        for idx, (img, res) in enumerate(zip(st.session_state['images'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            col_img, col_res = st.columns([1, 1.2])
            with col_img:
                st.image(img, use_container_width=True)
            with col_res:
                st.markdown(f"<div class='result-box'><b>AI Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            edited = st.text_area(f"Tahrir {idx+1}:", value=res, height=450, key=f"ed_{idx}", label_visibility="collapsed")
            final_report += f"\n\n--- VARAQ {idx+1} ---\n{edited}"
            st.markdown("---")

        if final_report:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_report)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")
            st.balloons()

