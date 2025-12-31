import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA SAHIFA SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Antique Edition", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ANTIK-ILMIY DIZAYN (CSS) ---
antique_style = """
    <style>
    /* Reklamalarni yashirish */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stAppDeployButton {display:none;}
    
    /* Antik-Ilmiy Ranglar Palitrasi */
    .main { 
        background-color: #fdfaf1; /* Pergament rangi */
        color: #1a202c;
    }
    
    /* Sarlavhalar - Serif shriftida */
    h1, h2, h3 {
        color: #1e3a8a !important; /* To'q ko'k */
        font-family: 'Georgia', serif;
        border-bottom: 2px solid #d4af37; /* Oltin chiziq */
        padding-bottom: 10px;
    }

    /* Yonma-yon Editor dizayni */
    .stTextArea textarea {
        background-color: #ffffff !important;
        border: 1px solid #d4af37 !important;
        font-family: 'Courier New', monospace;
        font-size: 15px !important;
        border-radius: 8px;
    }

    /* Rasmga Zoom effekti */
    .img-zoom:hover {
        transform: scale(1.5);
        transition: transform 0.5s ease;
        z-index: 100;
        cursor: zoom-in;
    }

    /* Tugmalar - Oltin va Ko'k */
    .stButton>button {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
        color: #fdfaf1;
        border-radius: 5px;
        border: 1px solid #d4af37;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background: #d4af37;
        color: #1e3a8a;
    }

    /* Sidebar - To'q Ko'k */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
    }
    </style>
"""
st.markdown(antique_style, unsafe_allow_html=True)
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# --- 2. XAVFSIZLIK VA SECRETS ---
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
        st.markdown("<h2 style='text-align: center;'>🔐 Manuscript AI Enterprise</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy parol", type="password")
        if st.button("Kirish"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Xato!")
    st.stop()

# --- 3. ASOSIY TIZIM ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-flash-lite-latest')

# SIDEBAR - Yangi funksiyalar (Era Selector)
with st.sidebar:
    st.markdown("### 📜 Manuscript AI Pro")
    st.markdown("---")
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    
    # 🆕 Yangi funksiya: Tarixiy davr tanlash
    era = st.selectbox("Tarixiy davr / Uslub:", [
        "Temuriylar davri (Nasta'liq)", 
        "Xonliklar davri (Suls/Riq'a)", 
        "Ilk islomiy davr (Kufiy)",
        "Noma'lum"
    ])
    
    st.markdown("---")
    st.markdown("#### 📖 Yo'riqnoma")
    st.caption("Yonma-yon tahrirlash rejimi yoqilgan. AI natijasini o'ng tomondagi oynada tuzatishingiz mumkin.")
    
    if st.button("🚪 Chiqish"):
        st.session_state["authenticated"] = False
        st.rerun()

# ASOSIY SAHIFA
st.title("📜 Tarixiy Qo'lyozmalar Tahlil Markazi")
st.write(f"**Ekspertiza rejimi:** {lang} | **Uslub:** {era}")

uploaded_file = st.file_uploader("Qo'lyozmani yuklang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    images = []
    if uploaded_file.type == "application/pdf":
        pdf = pdfium.PdfDocument(uploaded_file)
        for i in range(len(pdf)):
            images.append(pdf[i].render(scale=2).to_pil())
    else:
        images.append(Image.open(uploaded_file))

    # TAHLIL BOSHLASH
    if st.button('✨ Sahifalarni tahlil qilish'):
        st.session_state['final_texts'] = [] # Natijalarni saqlash uchun
        
        prompt = f"""
        Siz dunyo darajasidagi {lang} va {era} bo'yicha mutaxassisiz. 
        Tahlil: 1.Transliteratsiya (lotin). 2.O'zbekcha tarjima. 3.Tarixiy izoh.
        """
        
        for i, img in enumerate(images):
            with st.status(f"Sahifa {i+1} o'qilmoqda...") as s:
                response = model.generate_content([prompt, img])
                st.session_state['final_texts'].append(response.text)
                s.update(label=f"Sahifa {i+1} tayyor!", state="complete")

    # 🆕 Yangi funksiya: Side-by-Side Editor (Tahrirlash oynasi)
    if 'final_texts' in st.session_state:
        st.markdown("### 🖋 Tahlil va Tahrirlash")
        st.info("O'ng tomondagi oynada matnni tuzatishingiz mumkin. Word faylga siz tuzatgan variant saqlanadi.")
        
        all_edited_results = ""
        
        for idx, (img, txt) in enumerate(zip(images, st.session_state['final_texts'])):
            st.markdown(f"#### Sahifa {idx+1}")
            col_left, col_right = st.columns([1, 1]) # 50/50 ustunlar
            
            with col_left:
                st.image(img, use_container_width=True, caption=f"Asl nusxa (Sahifa {idx+1})")
            
            with col_right:
                # Tahrirlash oynasi
                edited_txt = st.text_area(f"Tahrirlash (Sahifa {idx+1}):", value=txt, height=450, key=f"edit_{idx}")
                all_edited_results += f"\n\n--- SAHIFA {idx+1} ---\n{edited_txt}"

        # WORD EXPORT
        if all_edited_results:
            doc = Document()
            doc.add_heading('Manuscript AI: Professional Tahlil Hisoboti', 0)
            doc.add_paragraph(f"Til: {lang} | Uslub: {era}")
            doc.add_paragraph(all_edited_results)
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
