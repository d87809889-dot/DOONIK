import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SAHIFA SOZLAMALARI (ENG TEPADA)
st.set_page_config(page_title="Manuscript AI Pro", page_icon="📜", layout="wide")

# --- 2. PROFESSIONAL ANTIK DIZAYN (BARQAROR CSS) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; }
    
    /* TAHRIRLASH OYNASI - MATN QORA VA ANIQ */
    .stTextArea textarea {
        background-color: #fdfaf1 !important;
        color: #000000 !important; 
        border: 2px solid #c5a059 !important;
        font-size: 17px !important;
    }

    .result-box {
        background-color: #ffffff; padding: 20px; border-radius: 10px;
        border-left: 8px solid #c5a059; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        color: #000000 !important; font-size: 16px; margin-bottom: 15px;
    }

    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important; font-weight: bold !important; width: 100% !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK (PAROL) ---
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
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy parol", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Kod noto'g'ri!")
    st.stop()

# --- 4. AI MODELI (ENG BARQAROR VARIANT) ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertizasi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Qo'lyozma yuklang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

# Session state xotirasi
if 'processed_images' not in st.session_state: st.session_state['processed_images'] = []
if 'analysis_results' not in st.session_state: st.session_state['analysis_results'] = []

if uploaded_file:
    if st.session_state.get('current_file') != uploaded_file.name:
        with st.spinner('Fayl qayta ishlanmoqda...'):
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(len(pdf)):
                    imgs.append(pdf[i].render(scale=2).to_pil())
            else:
                imgs.append(Image.open(uploaded_file))
            st.session_state['processed_images'] = imgs
            st.session_state['current_file'] = uploaded_file.name
            st.session_state['analysis_results'] = []

    # Prevyu
    cols = st.columns(min(len(st.session_state['processed_images']), 4))
    for i, img in enumerate(st.session_state['processed_images']):
        cols[i % 4].image(img, caption=f"Varaq {i+1}", use_container_width=True)

    if st.button('✨ TAHLILNI BOSHLASH'):
        results = []
        prompt = f"Siz matnshunos akademiksiz. {lang} va {era} uslubidagi ushbu qo'lyozmani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
        
        for i, img in enumerate(st.session_state['processed_images']):
            with st.status(f"Varaq {i+1} o'qilmoqda..."):
                try:
                    response = model.generate_content([prompt, img])
                    results.append(response.text)
                except Exception as e:
                    results.append(f"Xato: {e}")
        st.session_state['analysis_results'] = results

    # --- 6. TAHLIL VA TAHRIR ---
    if st.session_state['analysis_results']:
        st.divider()
        final_doc_text = ""
        
        for idx, (img, res) in enumerate(zip(st.session_state['processed_images'], st.session_state['analysis_results'])):
            st.subheader(f"📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            with c1:
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<div class='result-box'><b>AI Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            # Tahrirlash oynasi (noyob key bilan)
            edited = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"edit_area_{idx}")
            final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{edited}"
            st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "report.docx")

