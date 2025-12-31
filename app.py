import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA SAHIFA SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Eski Qo'lyozmalar va Tarixiy Hujjatlar Tarjimoni", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- GOOGLE VERIFICATION VA PROFESSIONAL DIZAYN (CSS) ---
meta_and_style = """
    <!-- Google Search Console Verification -->
    <meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />
    
    <style>
    /* Streamlit elementlarini yashirish */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stAppDeployButton {display:none;}
    
    /* Fon va shriftlar */
    .main { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
    
    /* Natija kartalari (Chatbot uslubi) */
    .result-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 15px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
        line-height: 1.8;
        color: #1e293b;
    }
    
    /* Tugmalar dizayni */
    .stButton>button {
        background: linear-gradient(135deg, #0f172a 0%, #2563eb 100%);
        color: white;
        border-radius: 12px;
        border: none;
        padding: 12px 24px;
        font-weight: 600;
        width: 100%;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.4);
    }
    </style>
"""
st.markdown(meta_and_style, unsafe_allow_html=True)

# --- 2. XAVFSIZLIK VA PAROL TIZIMI ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Xatolik: Streamlit Secrets (GEMINI_API_KEY yoki APP_PASSWORD) topilmadi!")
    st.stop()

# Kirish oynasi
if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>🔐 Manuscript AI Enterprise</h2>", unsafe_allow_html=True)
        st.write("<p style='text-align: center; color: #64748b;'>Tizimga kirish uchun maxfiy parolni kiriting</p>", unsafe_allow_html=True)
        pwd_input = st.text_input("", type="password", placeholder="Maxfiy kod...")
        if st.button("Kirish"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop()

# --- 3. ASOSIY DASTUR (KIRGANDAN KEYIN) ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-flash-lite-latest')

# SIDEBAR - Brending va Qo'llanma
with st.sidebar:
    st.markdown("### 📜 Manuscript AI v3.5")
    st.markdown("---")
    lang = st.selectbox("Tahlil tilini tanlang:", ["Chig'atoy", "Arabcha", "Forscha", "Eski Turkiy", "Noma'lum"])
    st.markdown("---")
    st.markdown("#### 📖 Yo'riqnoma")
    st.caption("1. Qo'lyozma rasm yoki PDF yuklang.")
    st.caption("2. AI tahlilini kuting.")
    st.caption("3. Natijani Wordda yuklab oling.")
    st.markdown("---")
    if st.button("🚪 Tizimdan chiqish"):
        st.session_state["authenticated"] = False
        st.rerun()

# ASOSIY SAHIFA
st.title("📜 Tarixiy Qo'lyozmalar Tahlil Markazi")
st.markdown("#### Eski o'zbek, chig'atoy, fors va arab tillaridagi matnlarni professional AI tahlili.")

uploaded_file = st.file_uploader("Faylni yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    images = []
    if uploaded_file.type == "application/pdf":
        with st.spinner('PDF sahifalarga ajratilmoqda...'):
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                images.append(pdf[i].render(scale=2).to_pil())
    else:
        images.append(Image.open(uploaded_file))

    st.markdown("### 📄 Yuklangan sahifalar")
    cols = st.columns(min(len(images), 4))
    for idx, img in enumerate(images):
        cols[idx % 4].image(img, caption=f"{idx+1}-sahifa", use_container_width=True)

    if st.button('✨ Intellektual Tahlilni Boshlash'):
        all_text_results = ""
        # Professional batafsil Prompt
        prompt = f"""
        Siz dunyodagi eng kuchli {lang} qo'lyozmalari mutaxassisiz. 
        Ushbu tasvirdagi matnni professional darajada tahlil qiling:
        1. Matnni xatosiz lotin alifbosiga ko'chiring (Transliteratsiya).
        2. Matnni hozirgi zamonaviy o'zbek tiliga ma'noviy tarjima qiling.
        3. Hujjatning tarixiy ahamiyati va uslubi haqida ekspert xulosasini bering.
        Javobni aniq va chiroyli formatda taqdim eting.
        """

        for i, img in enumerate(images):
            with st.status(f"Sahifa {i+1} tahlil qilinmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    res_text = response.text
                    
                    st.markdown(f"#### 🖋 Sahifa {i+1} natijasi:")
                    st.markdown(f"<div class='result-card'>{res_text}</div>", unsafe_allow_html=True)
                    
                    all_text_results += f"\n\n--- SAHIFA {i+1} ---\n{res_text}"
                    status.update(label=f"Sahifa {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato: {e}")

        # WORD EXPORT
        if all_text_results:
            doc = Document()
            doc.add_heading('Manuscript AI: Professional Tahlil Hisoboti', 0)
            doc.add_paragraph(f"Tahlil tili: {lang}\n{all_text_results}")
            bio = io.BytesIO()
            doc.save(bio)
            
            st.divider()
            st.download_button(
                label="📥 Natijalarni Word (.docx) formatida yuklab olish",
                data=bio.getvalue(),
                file_name="manuscript_analysis.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.balloons()
