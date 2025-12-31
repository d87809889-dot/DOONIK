import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA SAHIFA SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Ultimate Academic Master", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- REKLAMALARNI YASHIRISH VA ANTIK-AKADEMIK DIZAYN (KUCHAYTIRILGAN CSS) ---
ultimate_style = """
    <style>
    /* Streamlit va GitHub elementlarini agressiv yashirish */
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}

    /* Fon va shriftlar - Arxiv pergament uslubi */
    .main { 
        background-color: #f4ecd8 !important; 
        color: #1a1a1a !important;
        font-family: 'Times New Roman', serif;
    }

    /* Akademik sarlavhalar */
    h1, h2, h3, h4 {
        color: #0c1421 !important;
        font-family: 'Georgia', serif;
        border-bottom: 2px solid #c5a059;
        text-align: center;
        padding-bottom: 10px;
    }

    /* Chatbot uslubidagi natija kartasi */
    .result-box {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        border-left: 10px solid #c5a059;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        color: #1a1a1a !important;
        font-size: 17px;
        margin-bottom: 15px;
        line-height: 1.6;
    }

    /* TAHRIRLASH OYNASI (TEXT AREA) - Qora matn va pergament fon */
    .stTextArea textarea {
        background-color: #fdfaf1 !important;
        color: #000000 !important;
        border: 2px solid #c5a059 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 18px !important;
        padding: 20px !important;
        border-radius: 8px !important;
    }

    /* Sidebar - To'q navy va oltin */
    section[data-testid="stSidebar"] {
        background-color: #0c1421 !important;
        border-right: 2px solid #c5a059;
    }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }

    /* Tugmalar dizayni */
    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%);
        color: #c5a059 !important;
        border: 2px solid #c5a059;
        border-radius: 5px;
        font-weight: bold;
        padding: 12px;
        width: 100%;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stButton>button:hover {
        background: #c5a059 !important;
        color: #0c1421 !important;
        transform: translateY(-2px);
    }
    </style>
"""
st.markdown(ultimate_style, unsafe_allow_html=True)

# Google Search Console Verification Meta Tag
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# --- 2. XAVFSIZLIK VA TIZIMGA KIRISH ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Xatolik: Streamlit Secrets (GEMINI_API_KEY va APP_PASSWORD) sozlanmagan!")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2 style='border:none;'>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kirish kodi", type="password", placeholder="Kodni kiriting...")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Ruxsat berilmadi!")
    st.stop()

# --- 3. AI TIZIMI (BARQAROR MODEL: GEMINI 1.5 FLASH) ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# SIDEBAR - Funksional boshqaruv
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.markdown("---")
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Paleografik uslub:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.markdown("---")
    st.markdown("#### 🏛 Status:")
    st.caption("✅ Barqaror Model: Gemini 1.5 Flash")
    st.caption("✅ Sifat: DPI 300 (Scale 3)")
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 4. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar bo'yicha Ilmiy Markaz</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Ilmiy manbani yuklang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    # Fayl almashganda rasmlarni yangilash
    if 'images' not in st.session_state or st.session_state.get('last_file') != uploaded_file.name:
        images = []
        if uploaded_file.type == "application/pdf":
            with st.spinner('Manba raqamlashtirilmoqda (DPI 300)...'):
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(len(pdf)):
                    images.append(pdf[i].render(scale=3).to_pil())
        else:
            images.append(Image.open(uploaded_file))
        st.session_state['images'] = images
        st.session_state['last_file'] = uploaded_file.name

    st.markdown("### 📜 Yuklangan sahifalar")
    cols = st.columns(min(len(st.session_state['images']), 4))
    for idx, img in enumerate(st.session_state['images']):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ CHUQUR AKADEMIK TAHLILNI BOSHLASH'):
        st.session_state['academic_results'] = []
        
        # ENG MUKAMMAL AKADEMIK PROMPT
        prompt = f"""
        Siz qo'lyozmalar, paleografiya va matnshunoslik bo'yicha dunyo darajasidagi akademiksiz. 
        Ushbu {lang} tilidagi va {era} uslubidagi manbani quyidagi mezonlar asosida tahlil qiling:
        1. PALEOGRAFIK TAVSIF: Yozuv uslubi va xattotlik xususiyatlari.
        2. DIPLOMATIK TRANSLITERATSIYA: Matnni xatosiz lotin alifbosiga ko'chiring.
        3. SEMANTIK TARJIMA: Ma'nosini zamonaviy o'zbek tiliga ilmiy uslubda o'giring.
        4. ILMIY IZOH: Matndagi terminlar, shaxslar va joylarga akademik sharh bering.
        """
        
        for i, img in enumerate(st.session_state['images']):
            with st.status(f"Varaq {i+1} ekspertizadan o'tmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state['academic_results'].append(response.text)
                    status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato (Varaq {i+1}): {e}")

    # --- 5. OPTIMALLASHGAN SIDE-BY-SIDE EDITOR ---
    if 'academic_results' in st.session_state and len(st.session_state['academic_results']) > 0:
        st.divider()
        st.markdown("### 🖋 Natijalar va Ilmiy Tahrir")
        
        final_academic_report = ""
        
        for idx, (img, res) in enumerate(zip(st.session_state['images'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            
            # 1-qator: Rasm va AI natijasi yonma-yon
            col_img, col_res = st.columns([1, 1.2])
            with col_img:
                st.image(img, use_container_width=True, caption=f"Asl varaq {idx+1}")
            with col_res:
                st.markdown(f"<div class='result-box'><b>Akademik Tahlil:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            # 2-qator: Tahrirlash oynasi (Full width, qora matn)
            st.write("**Ushbu varaq bo'yicha yakuniy ilmiy tahrir:**")
            edited_val = st.text_area("", value=res, height=400, key=f"acad_edit_{idx}", label_visibility="collapsed")
            final_academic_report += f"\n\n--- VARAQ {idx+1} ---\n{edited_val}"
            st.markdown("---")

        # WORD EXPORT
        if final_academic_report:
            doc = Document()
            doc.add_heading('Manuscript AI: Akademik Ekspertiza Hisoboti', 0)
            doc.add_paragraph(f"Ilmiy soha: {lang} | Paleografiya: {era}")
            doc.add_paragraph(final_academic_report)
            
            bio = io.BytesIO()
            doc.save(bio)
            
            st.divider()
            st.download_button(
                label="📥 AKADEMIK HISOBOTNI WORDDA YUKLAB OLISH",
                data=bio.getvalue(),
                file_name="academic_analysis_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.balloons()

