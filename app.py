import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SAHIFA SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI Enterprise", 
    page_icon="📜", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL DIZAYN VA BRENDING (CSS) ---
hide_style = """
    <style>
    /* Streamlit va GitHub belgilarini yashirish */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stAppDeployButton {display:none;}
    
    /* Umumiy fon va shriftlar */
    .main { background-color: #f8f9fa; font-family: 'Inter', sans-serif; }
    
    /* Chatbot uslubidagi natija bloklari */
    .result-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        margin-bottom: 20px;
        line-height: 1.6;
        color: #1a1a1a;
    }
    
    /* Tugmalar dizayni */
    .stButton>button {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        color: white;
        border-radius: 8px;
        border: none;
        padding: 12px 24px;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(52, 152, 219, 0.3);
    }
    
    /* Sidebar dizayni */
    section[data-testid="stSidebar"] {
        background-color: #1e293b;
        color: white;
    }
    section[data-testid="stSidebar"] .stMarkdown { color: white; }
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

# --- 2. XAVFSIZLIK (KIRISH TIZIMI) ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Streamlit sozlamalarini tekshiring.")
    st.stop()

if not st.session_state["authenticated"]:
    # Kirish oynasini markazga olish
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>🔐 Manuscript AI Pro</h2>", unsafe_allow_html=True)
        st.write("<p style='text-align: center; color: gray;'>Tizimga kirish uchun maxfiy parolni kiriting</p>", unsafe_allow_html=True)
        pwd_input = st.text_input("", type="password", placeholder="Parol...")
        if st.button("Kirish"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop()

# --- 3. ASOSIY INTERFEYS (KIRGANDAN KEYIN) ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-flash-lite-latest')

# SIDEBAR - Brending va Qo'llanma
with st.sidebar:
    st.markdown("### 📜 Manuscript AI v2.0")
    st.markdown("---")
    lang = st.selectbox("Qo'lyozma tili:", ["Chig'atoy", "Arabcha", "Forscha", "Eski Turkiy"])
    st.markdown("---")
    st.markdown("#### 📖 Yo'riqnoma")
    st.caption("1. Qo'lyozma rasm yoki PDF faylini yuklang.")
    st.caption("2. AI tahlilini kuting.")
    st.caption("3. Natijani o'qing va Word formatda yuklab oling.")
    st.markdown("---")
    if st.button("🚪 Tizimdan chiqish"):
        st.session_state["authenticated"] = False
        st.rerun()

# ASOSIY SAHIFA
st.title("📜 Tarixiy Qo'lyozmalar Tahlili")
st.markdown(f"**Ekspert rejimi:** {lang} tili bo'yicha tahlilchi")

uploaded_file = st.file_uploader("Faylni tanlang (PDF, PNG, JPG)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    images = []
    if uploaded_file.type == "application/pdf":
        with st.spinner('PDF sahifalanmoqda...'):
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                images.append(pdf[i].render(scale=2).to_pil())
    else:
        images.append(Image.open(uploaded_file))

    # Sahifalarni chiroyli grid ko'rinishida chiqarish
    st.markdown("### 📄 Yuklangan sahifalar")
    cols = st.columns(min(len(images), 4))
    for idx, img in enumerate(images):
        cols[idx % 4].image(img, caption=f"{idx+1}-sahifa", use_container_width=True)

    if st.button('✨ Tahlilni boshlash'):
        all_results_text = ""
        prompt = f"Siz dunyo darajasidagi {lang} tili mutaxassisiz. Ushbu tasvirdagi qo'lyozmani tahlil qiling. 1. Transliteratsiya (lotin). 2. Ma'noviy tarjima (o'zbekcha). 3. Tarixiy ahamiyati haqida izoh."

        for i, img in enumerate(images):
            with st.status(f"Sahifa {i+1} tahlil qilinmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    res_text = response.text
                    
                    # Natijani chatbot uslubida chiqarish
                    st.markdown(f"#### 🖋 Sahifa {i+1} natijasi:")
                    st.markdown(f"<div class='result-card'>{res_text}</div>", unsafe_allow_html=True)
                    
                    all_results_text += f"\n\n--- SAHIFA {i+1} ---\n{res_text}"
                    status.update(label=f"Sahifa {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xatolik: {e}")

        # WORD EXPORT
        if all_results_text:
            doc = Document()
            doc.add_heading(f'Manuscript AI Tahlil Hisoboti - {lang}', 0)
            doc.add_paragraph(all_results_text)
            bio = io.BytesIO()
            doc.save(bio)
            
            st.divider()
            st.download_button(
                label="📥 Natijalarni Word (.docx) formatida yuklab olish",
                data=bio.getvalue(),
                file_name="manuscript_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.balloons()
