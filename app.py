import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA SAHIFA SOZLAMALARI (Eng tepada bo'lishi shart)
st.set_page_config(
    page_title="Manuscript AI - Professional Edition", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- REKLAMALARNI BUTUNLAY YASHIRISH VA DIZAYN (CSS) ---
# Bu qism mobil va desktopda ortiqcha belgilarni 100% yashiradi
hide_and_style = """
    <style>
    /* Streamlit va GitHub reklamalarini majburiy yashirish */
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    
    /* Umumiy fon va professional chatbot dizayni */
    .main { background-color: #f9fafb; font-family: 'Inter', sans-serif; }
    
    .result-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        line-height: 1.8;
        color: #1a1a1a;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #1e293b 0%, #3b82f6 100%);
        color: white; border-radius: 10px; border: none; padding: 12px;
        font-weight: 600; width: 100%; transition: 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(59, 130, 246, 0.3);
    }
    </style>
"""
st.markdown(hide_and_style, unsafe_allow_html=True)

# Google Search Console Verification (Sizning kodingiz)
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# --- 2. XAVFSIZLIK VA PAROL TIZIMI ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Secrets'dan ma'lumotlarni olish
try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Secrets sozlanmagan! Streamlit Settings > Secrets qismini tekshiring.")
    st.stop()

# Parol kiritilmaguncha hamma narsani bloklash
if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>🔐 Manuscript AI Enterprise</h2>", unsafe_allow_html=True)
        st.write("<p style='text-align: center; color: gray;'>Kirish uchun maxfiy parolni kiriting</p>", unsafe_allow_html=True)
        pwd_input = st.text_input("", type="password", placeholder="Parol...")
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

# Sidebar sozlamalari
with st.sidebar:
    st.markdown("### 📜 Manuscript Pro v4.0")
    st.markdown("---")
    lang = st.selectbox("Tahlil tili:", ["Chig'atoy", "Arabcha", "Forscha", "Eski Turkiy", "Noma'lum"])
    st.markdown("---")
    st.markdown("#### 📖 Yo'riqnoma")
    st.caption("1. Rasm yoki PDF yuklang.")
    st.caption("2. AI tahlilini kuting.")
    st.caption("3. Natijani Wordda yuklang.")
    if st.button("🚪 Tizimdan chiqish"):
        st.session_state["authenticated"] = False
        st.rerun()

st.title("📜 Tarixiy Qo'lyozmalar Tahlili")
st.markdown(f"**Ekspert rejimi:** {lang} mutaxassisi yordamida tahlil")

# Fayl yuklash
uploaded_file = st.file_uploader("Faylni yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    images = []
    if uploaded_file.type == "application/pdf":
        with st.spinner('PDF sahifalanmoqda...'):
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                images.append(pdf[i].render(scale=2).to_pil())
    else:
        images.append(Image.open(uploaded_file))

    st.markdown("### 📄 Sahifalar")
    cols = st.columns(min(len(images), 4))
    for idx, img in enumerate(images):
        cols[idx % 4].image(img, caption=f"{idx+1}-sahifa", use_container_width=True)

    if st.button('✨ Tahlilni boshlash'):
        all_text_results = ""
        prompt = f"Siz dunyo darajasidagi {lang} mutaxassisiz. Lotinchaga o'gir, o'zbekcha tarjima qil va batafsil izoh ber."

        for i, img in enumerate(images):
            with st.status(f"{i+1}-sahifa tahlil qilinmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    res_text = response.text
                    st.markdown(f"#### 🖋 {i+1}-sahifa natijasi:")
                    st.markdown(f"<div class='result-card'>{res_text}</div>", unsafe_allow_html=True)
                    all_text_results += f"\n\n--- SAHIFA {i+1} ---\n{res_text}"
                    status.update(label=f"{i+1}-sahifa tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato: {e}")

        # 4. WORD EKSPORT
        if all_text_results:
            doc = Document()
            doc.add_heading(f'Manuscript AI Hisoboti - {lang}', 0)
            doc.add_paragraph(all_text_results)
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

