import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA SAHIFA SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Antique Professional Edition", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- REKLAMALARNI YASHIRISH VA ANTIK DIZAYN (CSS) ---
hide_and_style = """
    <style>
    /* Streamlit va GitHub elementlarini agressiv yashirish */
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    
    /* Antik-Ilmiy dizayn ranglari */
    .main { 
        background-color: #fdfaf1; /* Pergament foni */
        color: #1a202c;
    }
    
    h1, h2, h3 {
        color: #1e3a8a !important;
        font-family: 'Georgia', serif;
        border-bottom: 2px solid #d4af37;
        padding-bottom: 10px;
    }

    /* Side-by-Side Editor uchun maxsus dizayn */
    .stTextArea textarea {
        background-color: #ffffff !important;
        border: 1px solid #d4af37 !important;
        font-family: 'Courier New', monospace;
        font-size: 15px !important;
        color: #1a202c !important;
    }

    /* Tugmalar dizayni */
    .stButton>button {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
        color: #fdfaf1;
        border-radius: 8px;
        border: 1px solid #d4af37;
        font-weight: bold;
        padding: 12px 20px;
        transition: 0.3s ease;
    }
    .stButton>button:hover {
        background: #d4af37;
        color: #1e3a8a;
        transform: translateY(-2px);
    }

    /* Sidebar - To'q navy fon */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
    }
    </style>
"""
st.markdown(hide_and_style, unsafe_allow_html=True)

# Google Search Console Verification Meta Tag
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# --- 2. XAVFSIZLIK VA SECRETS ---
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
        st.markdown("<h2 style='text-align: center;'>🔐 Manuscript AI Enterprise</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy parol", type="password", placeholder="Parolni kiriting...")
        if st.button("Kirish"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop()

# --- 3. ASOSIY DASTUR ---
# Barqaror modeldan foydalanamiz: gemini-1.5-flash
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Sidebar - Brending va Sozlamalar
with st.sidebar:
    st.markdown("<h2 style='color:white;'>📜 Manuscript AI</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:silver;'>v4.5 Professional Edition</p>", unsafe_allow_html=True)
    st.markdown("---")
    lang = st.selectbox("Hujjat tili:", ["Chig'atoy", "Arabcha", "Forscha", "Eski Turkiy"])
    era = st.selectbox("Tarixiy uslub:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.markdown("---")
    st.markdown("#### 📖 Qo'llanma")
    st.caption("AI tahlilidan so'ng natijani o'ng tomondagi tahrirlash oynasida tuzatishingiz mumkin. Word faylga siz tuzatgan so'nggi variant saqlanadi.")
    if st.button("🚪 Tizimdan chiqish"):
        st.session_state["authenticated"] = False
        st.rerun()

# Asosiy ekran
st.title("📜 Tarixiy Qo'lyozmalar Tahlil Markazi")
st.markdown(f"**Ekspertiza rejimi:** {lang} | **Yozuv uslubi:** {era}")

uploaded_file = st.file_uploader("Faylni tanlang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

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

    if st.button('✨ Intellektual Tahlilni Boshlash'):
        st.session_state['results'] = []
        prompt = f"""
        Siz {lang} tili va {era} uslubi bo'yicha dunyo darajasidagi mutaxassisiz. 
        Ushbu tasvirdagi qo'lyozmani professional tahlil qiling:
        1. Transliteratsiya (lotin alifbosida).
        2. Ma'noviy tarjima (o'zbek tilida).
        3. Tarixiy ahamiyati haqida izoh.
        """
        
        for i, img in enumerate(images):
            with st.status(f"Sahifa {i+1} tahlil qilinmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state['results'].append(response.text)
                    status.update(label=f"Sahifa {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Sahifa {i+1}da xato: {e}")

    # --- 4. SIDE-BY-SIDE EDITOR (TAHRIRLASH) ---
    if 'results' in st.session_state and len(st.session_state['results']) > 0:
        st.markdown("---")
        st.subheader("🖋 Tahlil Natijalari va Tahrirlash")
        
        final_output_for_word = ""
        
        for idx, (img, res) in enumerate(zip(images, st.session_state['results'])):
            st.markdown(f"**Sahifa {idx+1}**")
            col_img, col_edt = st.columns([1, 1])
            
            with col_img:
                st.image(img, use_container_width=True, caption=f"Asl nusxa - {idx+1}")
            
            with col_edt:
                # Har bir sahifa uchun alohida tahrirlash oynasi
                edited_val = st.text_area(f"Tuzatish kiriting (Sahifa {idx+1}):", value=res, height=450, key=f"edit_{idx}")
                final_output_for_word += f"\n\n--- SAHIFA {idx+1} ---\n{edited_val}"

        # WORD EXPORT
        if final_output_for_word:
            doc = Document()
            doc.add_heading('Manuscript AI: Professional Tahlil Hisoboti', 0)
            doc.add_paragraph(f"Til: {lang} | Uslub: {era}")
            doc.add_paragraph(final_output_for_word)
            
            bio = io.BytesIO()
            doc.save(bio)
            
            st.divider()
            st.download_button(
                label="📥 Tuzatilgan natijalarni Word (.docx) formatida yuklab olish",
                data=bio.getvalue(),
                file_name="manuscript_analysis.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.balloons()
