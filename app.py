import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA SAHIFA SOZLAMALARI (Google qidiruvi uchun optimallashgan)
st.set_page_config(
    page_title="Manuscript AI - Eski Qo'lyozmalar va Tarixiy Hujjatlar Tarjimoni", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL DIZAYN VA BRENDING (CSS) ---
hide_and_style = """
    <style>
    /* Streamlit va GitHub elementlarini yashirish */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stAppDeployButton {display:none;}
    
    /* Umumiy fon va dizayn */
    .main { background-color: #f9fafb; font-family: 'Inter', sans-serif; }
    
    /* Chatbot uslubidagi natija kartalari */
    .result-card {
        background-color: #ffffff;
        padding: 30px;
        border-radius: 15px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 10px rgba(0,0,0,0.03);
        margin-bottom: 25px;
        line-height: 1.8;
        color: #1f2937;
        font-size: 16px;
    }
    
    /* Tugmalar dizayni */
    .stButton>button {
        background: linear-gradient(135deg, #1e293b 0%, #3b82f6 100%);
        color: white;
        border-radius: 10px;
        border: none;
        padding: 14px 28px;
        font-weight: 600;
        width: 100%;
        transition: 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(59, 130, 246, 0.4);
    }

    /* Sidebar dizayni */
    section[data-testid="stSidebar"] {
        background-color: #0f172a;
        color: white;
    }
    </style>
"""
st.markdown(hide_and_style, unsafe_allow_html=True)

# --- 2. XAVFSIZLIK VA SECRETS TEKSHIRUVI ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Diqqat: Streamlit Secrets (GEMINI_API_KEY yoki APP_PASSWORD) sozlanmagan!")
    st.stop()

# KIRISH TIZIMI
if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center; color: #1e293b;'>🔐 Manuscript AI Enterprise</h2>", unsafe_allow_html=True)
        st.write("<p style='text-align: center; color: #64748b;'>Tizimga kirish uchun maxfiy parolni kiriting</p>", unsafe_allow_html=True)
        pwd_input = st.text_input("", type="password", placeholder="Maxfiy kod...")
        if st.button("Kirish"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Xato parol kiritildi!")
    st.stop()

# --- 3. ASOSIY INTERFEYS (TIZIMGA KIRGANDAN KEYIN) ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-flash-lite-latest')

# SIDEBAR SOZLAMALARI
with st.sidebar:
    st.markdown("### 📜 Manuscript AI v3.0")
    st.markdown("---")
    lang = st.selectbox("Tahlil tilini tanlang:", ["Chig'atoy", "Arabcha", "Forscha", "Eski Turkiy", "Noma'lum"])
    st.markdown("---")
    st.markdown("#### 🛠 Imkoniyatlar:")
    st.caption("✅ PDF va Rasm tahlili")
    st.caption("✅ Lotincha transliteratsiya")
    st.caption("✅ Ma'noviy tarjima")
    st.caption("✅ Word eksport")
    st.markdown("---")
    if st.button("🚪 Tizimdan chiqish"):
        st.session_state["authenticated"] = False
        st.rerun()

# ASOSIY SAHIFA MAZMUNI
st.title("📜 Tarixiy Qo'lyozmalar Tahlil Markazi")
st.markdown("#### Eski o'zbek, chig'atoy, fors va arab tillaridagi qo'lyozmalarni professional AI yordamida o'qish va tarjima qilish tizimi.")

st.divider()

# Fayl yuklash
uploaded_file = st.file_uploader("Faylni tanlang (PDF, PNG, JPG)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    images = []
    if uploaded_file.type == "application/pdf":
        with st.spinner('PDF sahifalari qayta ishlanmoqda...'):
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                images.append(pdf[i].render(scale=2).to_pil())
    else:
        images.append(Image.open(uploaded_file))

    # Yuklangan sahifalarni ko'rsatish
    st.markdown("### 📄 Yuklangan hujjat sahifalari")
    cols = st.columns(min(len(images), 4))
    for idx, img in enumerate(images):
        cols[idx % 4].image(img, caption=f"{idx+1}-sahifa", use_container_width=True)

    # TAHLIL TUGMASI
    if st.button('✨ Intellektual Tahlilni Boshlash'):
        all_text_results = ""
        # Professional Prompt (O'zbek tilida natija olish uchun)
        prompt = f"""
        Siz dunyodagi eng kuchli {lang} qo'lyozmalari mutaxassisiz. 
        Ushbu tasvirdagi matnni professional darajada tahlil qiling:
        1. Matnni xatosiz lotin alifbosiga ko'chiring (Transliteratsiya).
        2. Matnni hozirgi zamonaviy o'zbek tiliga ma'noviy tarjima qiling.
        3. Hujjatning tarixiy ahamiyati, yozilish uslubi va mavzusi haqida ekspert xulosasini bering.
        Javobni aniq va chiroyli formatda taqdim eting.
        """

        for i, img in enumerate(images):
            with st.status(f"Sahifa {i+1} tahlil qilinmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    res_text = response.text
                    
                    # Natijani professional karta ko'rinishida chiqarish
                    st.markdown(f"### 🖋 Sahifa {i+1} Natijasi:")
                    st.markdown(f"<div class='result-card'>{res_text}</div>", unsafe_allow_html=True)
                    
                    all_text_results += f"\n\n--- SAHIFA {i+1} ---\n{res_text}"
                    status.update(label=f"Sahifa {i+1} muvaffaqiyatli yakunlandi!", state="complete")
                except Exception as e:
                    st.error(f"Kutilmagan xatolik: {e}")

        # WORD EKSPORT FUNKSIYASI
        if all_text_results:
            doc = Document()
            doc.add_heading('Manuscript AI: Professional Tahlil Hisoboti', 0)
            doc.add_paragraph(f"Tahlil qilingan til: {lang}")
            doc.add_paragraph(all_text_results)
            
            bio = io.BytesIO()
            doc.save(bio)
            
            st.divider()
            st.download_button(
                label="📥 Tahlil natijalarini Word (.docx) formatida yuklab olish",
                data=bio.getvalue(),
                file_name="manuscript_analysis_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.balloons()

