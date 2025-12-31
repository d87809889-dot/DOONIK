import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA SAHIFA SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Enterprise", 
    page_icon="📜", 
    layout="wide"
)

# --- 2. ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; border-bottom: 2px solid #c5a059; text-align: center; }
    .result-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border-left: 8px solid #c5a059; color: #000000 !important; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 1px solid #c5a059 !important; font-size: 16px !important; }
    .stButton>button { background: #0c1421; color: #c5a059; border: 1px solid #c5a059; font-weight: bold; width: 100%; padding: 10px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK ---
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
        st.markdown("<h2 style='border:none;'>🏛 KIRISH</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kod", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Xato!")
    st.stop()

# --- 4. AI MODELINI TO'G'RI SOZLASH (FIX 404) ---
# MUHIM: models/ prefiksini olib tashlaymiz va stable versiyani ishlatamiz
genai.configure(api_key=GEMINI_KEY)

# Bu funksiya xatolik chiqsa boshqa nomni avtomatik sinab ko'radi
def load_model():
    # Eng barqaror nomlar (2026 standarti)
    names = ["gemini-1.5-flash", "gemini-1.5-flash-latest"]
    for name in names:
        try:
            return genai.GenerativeModel(name)
        except:
            continue
    return None

model = load_model()

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertizasi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Manbani yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    if 'imgs' not in st.session_state or st.session_state.get('fname') != uploaded_file.name:
        imgs = []
        if uploaded_file.type == "application/pdf":
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                imgs.append(pdf[i].render(scale=3).to_pil())
        else:
            imgs.append(Image.open(uploaded_file))
        st.session_state['imgs'] = imgs
        st.session_state['fname'] = uploaded_file.name

    st.markdown("### 📜 Varaqlar")
    cols = st.columns(min(len(st.session_state['imgs']), 4))
    for idx, img in enumerate(st.session_state['imgs']):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ TAHLILNI BOSHLASH'):
        if model is None:
            st.error("Model ulanmadi!")
        else:
            st.session_state['res'] = []
            prompt = f"Siz matnshunos akademiksiz. {lang} va {era} uslubidagi ushbu qo'lyozmani tahlil qiling: 1.Transliteratsiya. 2.Tarjima. 3.Izoh."
            
            for i, img in enumerate(st.session_state['imgs']):
                with st.status(f"Varaq {i+1} o'qilmoqda..."):
                    try:
                        response = model.generate_content([prompt, img])
                        st.session_state['res'].append(response.text)
                    except Exception as e:
                        st.error(f"Xato: {e}")

    # EDITOR
    if 'res' in st.session_state:
        st.divider()
        final_text = ""
        for idx, (img, res) in enumerate(zip(st.session_state['imgs'], st.session_state['res'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, use_container_width=True)
            with c2: st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
            
            ed = st.text_area(f"Tahrir {idx+1}:", value=res, height=350, key=f"ed_{idx}")
            final_text += f"\n\n--- VARAQ {idx+1} ---\n{ed}"

        if final_text:
            doc = Document()
            doc.add_paragraph(final_text)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLASH", bio.getvalue(), "report.docx")
