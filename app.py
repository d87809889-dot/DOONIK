import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA ILMIY MUHIT SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Master Edition", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ILMIY-ANTIK DIZAYN (KUCHAYTIRILGAN CSS) ---
st.markdown("""
    <style>
    /* Reklamalarni yashirish */
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;} .stAppDeployButton {display:none !important;}
    
    /* Fon va umumiy ranglar */
    .main { 
        background-color: #f4ecd8 !important; 
        color: #1a1a1a !important;
        font-family: 'Times New Roman', serif;
    }
    
    /* Sarlavhalar */
    h1, h2, h3, h4 {
        color: #0c1421 !important;
        font-family: 'Georgia', serif;
        border-bottom: 2px solid #c5a059;
        text-align: center;
    }

    /* TAHRIRLASH OYNASI (TEXT AREA) - KO'RINISHNI TUZATISH */
    .stTextArea textarea {
        background-color: #fdfaf1 !important; /* Och sarg'ish fon */
        color: #000000 !important; /* MATN QORA RANGDA (KO'RINARLI) */
        border: 2px solid #c5a059 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 18px !important;
        padding: 15px !important;
        border-radius: 8px !important;
    }

    /* AI tahlili chiqadigan karta (Card) */
    .result-box {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        border-left: 10px solid #c5a059;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        color: #1a1a1a !important;
        font-size: 17px;
        margin-bottom: 20px;
    }

    /* Tugmalar */
    .stButton>button {
        background-color: #0c1421;
        color: #c5a059;
        border: 2px solid #c5a059;
        font-weight: bold;
        padding: 12px 25px;
        width: 100%;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #c5a059;
        color: #0c1421;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0c1421 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. XAVFSIZLIK ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<h2 style='border:none;'>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kirish kodi", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Kod noto'g'ri!")
    st.stop()

# --- 3. AI TIZIMI ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 ARXIV AI</h2>", unsafe_allow_html=True)
    lang = st.sidebar.selectbox("Filologik til:", ["Chig'atoy", "Fors", "Arab", "Usmonli Turk"])
    era = st.sidebar.selectbox("Paleografik uslub:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# ASOSIY EKRAN
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertizasi</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Ilmiy manbani yuklang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    images = []
    if uploaded_file.type == "application/pdf":
        with st.spinner('Manba yuklanmoqda...'):
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                images.append(pdf[i].render(scale=3).to_pil())
    else:
        images.append(Image.open(uploaded_file))

    st.markdown("### 🏛 Tadqiqot ob'ekti")
    cols = st.columns(min(len(images), 4))
    for idx, img in enumerate(images):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ CHUQUR AKADEMIK TAHLILNI BOSHLASH'):
        st.session_state['academic_results'] = []
        
        prompt = f"""
        Siz qo'lyozmalar bo'yicha dunyo darajasidagi akademiksiz. 
        Ushbu {lang} tilidagi va {era} uslubidagi manbani tahlil qiling:
        1. PALEOGRAFIK TAVSIF: Yozuv uslubi va paleografiyasi.
        2. DIPLOMATIK TRANSLITERATSIYA: Matnni harfma-harf lotinga ko'chiring.
        3. SEMANTIK TARJIMA: Ma'nosini zamonaviy o'zbek tiliga o'giring.
        4. ILMIY IZOH: Terminlar va tarixiy shaxslarga sharh.
        """
        
        for i, img in enumerate(images):
            with st.status(f"Varaq {i+1} tahlil qilinmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state['academic_results'].append(response.text)
                    status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato: {e}")

    # --- 4. OPTIMALLASHGAN TAHLIL VA TAHRIR (PASTGA KO'CHIRILDI) ---
    if 'academic_results' in st.session_state and len(st.session_state['academic_results']) > 0:
        st.divider()
        st.markdown("### 🖋 Tahlil Natijalari va Ilmiy Tahrir")
        
        final_report = ""
        
        for idx, (img, res) in enumerate(zip(images, st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            
            # Rasm va AI natijasi (Karta ko'rinishida)
            col_img, col_res = st.columns([1, 1.2])
            with col_img:
                st.image(img, use_container_width=True)
            with col_res:
                st.markdown(f"<div class='result-box'><b>AI Ekspertiza:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            # TAHRIRLASH OYNASI - RASM VA TAHLILNING TAGIDA (FULL WIDTH)
            edited_val = st.text_area(f"Ilmiy tahrir (Varaq {idx+1}):", value=res, height=400, key=f"acad_edit_{idx}")
            final_report += f"\n\n--- VARAQ {idx+1} ---\n{edited_val}"
            st.markdown("---")

        # WORD EXPORT
        if final_report:
            doc = Document()
            doc.add_heading('Manuscript AI: Akademik Hisobot', 0)
            doc.add_paragraph(final_report)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 HISOBOTNI WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")
            st.balloons()

