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

# --- ILMIY-ANTIK DIZAYN (PROFESSIONAL CSS) ---
academic_style = """
    <style>
    /* Reklamalarni yashirish */
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;} .stAppDeployButton {display:none !important;}
    
    /* Arxiv foni va shriftlar */
    .main { 
        background-color: #f4ecd8; /* Haqiqiy pergament foni */
        color: #1a1a1a;
        font-family: 'Times New Roman', serif;
    }
    
    /* Akademik sarlavhalar */
    h1, h2, h3 {
        color: #0c1421 !important;
        font-family: 'Georgia', serif;
        border-bottom: 3px double #c5a059;
        padding-bottom: 15px;
        text-align: center;
    }

    /* Side-by-Side Editor */
    .stTextArea textarea {
        background-color: #ffffff !important;
        border: 2px solid #c5a059 !important;
        font-family: 'Courier New', monospace;
        font-size: 17px !important;
        color: #000000 !important;
        border-radius: 4px;
    }

    /* Tugmalar - Ilmiy uslub */
    .stButton>button {
        background-color: #0c1421;
        color: #c5a059;
        border: 2px solid #c5a059;
        border-radius: 0px;
        font-weight: bold;
        padding: 15px 30px;
        text-transform: uppercase;
        letter-spacing: 2px;
        transition: 0.4s;
    }
    .stButton>button:hover {
        background-color: #c5a059;
        color: #0c1421;
        border: 2px solid #0c1421;
    }

    /* Sidebar - To'q arxiv foni */
    section[data-testid="stSidebar"] {
        background-color: #0c1421 !important;
        border-right: 2px solid #c5a059;
    }
    </style>
"""
st.markdown(academic_style, unsafe_allow_html=True)

# --- 2. XAVFSIZLIK VA MAXFIY KALITLAR ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Tizim sozlamalari (Secrets) topilmadi!")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<h2 style='border:none;'>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kirish kodi", type="password", placeholder="Kodni kiriting...")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Ruxsat berilmadi: Kod noto'g'ri!")
    st.stop()

# --- 3. ILMIY ANALIZ TIZIMI ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 ARXIV AI</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:white; text-align:center; font-size:12px;'>Academic Master Edition v5.0</p>", unsafe_allow_html=True)
    st.markdown("---")
    lang = st.sidebar.selectbox("Hujjatning filologik tili:", ["Chig'atoy (Eski o'zbek)", "Fors (Klassik)", "Arab (Ilmiy)", "Usmonli Turk"])
    era = st.sidebar.selectbox("Paleografik uslub (Xat):", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Devoniy", "Noma'lum"])
    
    st.markdown("---")
    st.markdown("<h4 style='color:#c5a059;'>🏛 Ilmiy yo'riqnoma:</h4>", unsafe_allow_html=True)
    st.caption("Ushbu platforma matnshunoslik va paleografiya qoidalariga asoslangan holda tahlil o'tkazadi.")
    
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# ASOSIY EKRAN
st.markdown("<h1>Tarixiy Qo'lyozmalar bo'yicha Raqamli Ekspertiza</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center;'><b>Soha:</b> {lang} filologiyasi | <b>Yozuv turi:</b> {era} paleografiyasi</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Ilmiy manbani yuklang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    images = []
    if uploaded_file.type == "application/pdf":
        with st.spinner('Manba sahifalari raqamlashtirilmoqda...'):
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                images.append(pdf[i].render(scale=3).to_pil()) # Sifatni 3x oshiramiz
    else:
        images.append(Image.open(uploaded_file))

    st.markdown("### 🏛 Tadqiqot ob'ekti sahifalari")
    cols = st.columns(min(len(images), 4))
    for idx, img in enumerate(images):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ CHUQUR AKADEMIK TAHLILNI BOSHLASH'):
        st.session_state['academic_results'] = []
        
        # --- ENG MUKAMMAL AKADEMIK PROMPT ---
        prompt = f"""
        Siz qadimiy qo'lyozmalar, matnshunoslik va paleografiya bo'yicha dunyo darajasidagi akademiksiz. 
        Ushbu {lang} tilidagi va {era} uslubidagi manbani quyidagi qat'iy ilmiy mezonlar asosida tahlil qiling:

        1. PALEOGRAFIK TAVSIF: Yozuv uslubi, xatning o'ziga xosligi va matnning joylashuvi haqida codicological ma'lumot bering.
        2. DIPLOMATIK TRANSLITERATSIYA: Matnni harfma-harf, asl imlosini saqlagan holda lotin alifbosiga ko'chiring.
        3. SEMANTIK TARJIMA: Matnning ma'nosini zamonaviy o'zbek adabiy tiliga, ilmiy aniqlik bilan o'giring.
        4. TANQIDIY APPARAT (KOMMENTARIY): Matndagi arxaizmlar, tarixiy shaxslar, joy nomlari va terminlarga matnshunoslik nuqtai nazaridan ilmiy izoh bering.
        
        Tahlilni o'ta professional, akademik va tushunarli tilda taqdim eting.
        """
        
        for i, img in enumerate(images):
            with st.status(f"Varaq {i+1} ekspertizadan o'tkazilmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state['academic_results'].append(response.text)
                    status.update(label=f"Varaq {idx+1} tahlili yakunlandi!", state="complete")
                except Exception as e:
                    st.error(f"Ekspertiza xatosi: {e}")

    # --- 4. AKADEMIK EDITOR (SIDE-BY-SIDE) ---
    if 'academic_results' in st.session_state and len(st.session_state['academic_results']) > 0:
        st.markdown("---")
        st.markdown("<h3>🖋 Ilmiy Tahrir va Tanqidiy Matn Ustida Ishlash</h3>", unsafe_allow_html=True)
        
        final_academic_report = ""
        
        for idx, (img, res) in enumerate(zip(images, st.session_state['academic_results'])):
            st.markdown(f"#### Varaq {idx+1}")
            col_img, col_edt = st.columns([1, 1])
            
            with col_img:
                st.image(img, use_container_width=True, caption=f"Asl Manba (Varaq {idx+1})")
            
            with col_edt:
                # Akademik tahrirlash oynasi
                edited_val = st.text_area(f"Ilmiy tahrir (Varaq {idx+1}):", value=res, height=550, key=f"acad_edit_{idx}")
                final_academic_report += f"\n\n--- VARAQ {idx+1} ---\n{edited_val}"

        # WORD EXPORT (PROFESSIONAL REPORT)
        if final_academic_report:
            doc = Document()
            doc.add_heading('Manuscript AI: Akademik Ekspertiza Hisoboti', 0)
            doc.add_paragraph(f"Ilmiy soha: {lang}\nPaleografiya: {era}")
            doc.add_paragraph(final_academic_report)
            
            bio = io.BytesIO()
            doc.save(bio)
            
            st.divider()
            st.download_button(
                label="📥 AKADEMIK HISOBOTNI YUKLAB OLISH (.DOCX)",
                data=bio.getvalue(),
                file_name="academic_manuscript_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.balloons()

