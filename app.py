import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document
import gc

# 1. SEO VA AKADEMIK INTERFEYS SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Professional Academic Master 2026", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK-AKADEMIK DIZAYN (KUCHAYTIRILGAN CSS) ---
st.markdown("""
    <style>
    /* Reklamalarni ildizi bilan yashirish */
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;} .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}

    /* Pergament foni va umumiy ranglar */
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }

    /* AI TAHLIL KARTASI */
    .result-box {
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important;
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 17px;
    }

    /* TAHRIRLASH OYNASI - MATN RANGI QORA */
    .stTextArea textarea {
        background-color: #fdfaf1 !important; color: #000000 !important; 
        border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important;
        font-size: 18px !important; padding: 20px !important;
    }

    /* CHAT DIZAYNI */
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #d4af37; }

    /* Sidebar va Tugmalar */
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important; border: 2px solid #c5a059 !important;
        font-weight: bold !important; width: 100% !important; padding: 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Google Search Console Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# --- 3. XAVFSIZLIK ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Settings > Secrets qismini tekshiring.")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kod", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Kod noto'g'ri!")
    st.stop()

# --- 4. MODELNI BARQAROR (STABLE) REJIMDA SOZLASH ---
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_working_model():
    """Google'dan ruxsat berilgan va 404 bermaydigan modelni tanlaydi"""
    # SIZNING RO'YXATINGIZDA ISHLAYOTGAN NOM: gemini-flash-latest
    # Bu nom versiyadan qat'iy nazar barqaror ishlaydi.
    try:
        # models/ prefiksisiz to'g'ridan-to'g'ri chaqirish stable versiyani ishlatishga majbur qiladi
        return genai.GenerativeModel(model_name='gemini-flash-latest')
    except:
        return genai.GenerativeModel(model_name='gemini-1.5-flash-latest')

model = load_working_model()

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertiza Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Ilmiy manbani yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

# Session state elementlari
if 'imgs' not in st.session_state: st.session_state['imgs'] = []
if 'academic_results' not in st.session_state: st.session_state['academic_results'] = []
if 'chat_history' not in st.session_state: st.session_state['chat_history'] = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('DPI 300 sifatda raqamlashtirilmoqda...'):
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(len(pdf)):
                    imgs.append(pdf[i].render(scale=3).to_pil())
                    gc.collect()
                pdf.close()
            else:
                imgs.append(Image.open(uploaded_file))
            st.session_state['imgs'] = imgs
            st.session_state['last_fn'] = uploaded_file.name
            st.session_state['academic_results'] = []
            st.session_state['chat_history'] = {}

    cols = st.columns(min(len(st.session_state['imgs']), 4))
    for idx, img in enumerate(st.session_state['imgs']):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width="stretch")

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        new_results = []
        prompt = f"Siz matnshunos akademiksiz. {lang} va {era} uslubidagi qo'lyozmani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
        
        for i, img in enumerate(st.session_state['imgs']):
            with st.status(f"Varaq {i+1} o'qilmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    new_results.append(response.text)
                    status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                except Exception as e:
                    new_results.append(f"Xato: {e}")
        st.session_state['academic_results'] = new_results

    # --- 6. SIDE-BY-SIDE TAHLIL, TAHRIR VA CHAT ---
    if st.session_state['academic_results']:
        st.divider()
        st.markdown("### 🖋 Natijalar va Ilmiy Tahrir")
        
        final_text_for_word = ""
        for idx, (img, res) in enumerate(zip(st.session_state['imgs'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, width="stretch")
            with c2: st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            ed_val = st.text_area(f"Varaq {idx+1} bo'yicha tahrir:", value=res, height=400, key=f"ed_{idx}")
            final_text_for_word += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

            # INTERAKTIV CHAT
            st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan muloqot")
            chat_id = f"chat_{idx}"
            if chat_id not in st.session_state['chat_history']: st.session_state['chat_history'][chat_id] = []

            for chat in st.session_state['chat_history'][chat_id]:
                st.markdown(f"""<div style="background-color: #e2e8f0; color: #000000; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #1e3a8a;">
                <b>Savol:</b> {chat['q']}</div>""", unsafe_allow_html=True)
                st.markdown(f"""<div style="background-color: #ffffff; color: #1a1a1a; padding: 10px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #d4af37;">
                <b>AI:</b> {chat['a']}</div>""", unsafe_allow_html=True)

            user_q = st.text_input(f"Savol yozing ({idx+1}):", key=f"q_in_{idx}")
            if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                if user_q:
                    chat_res = model.generate_content([f"Savol: {user_q}\nMatn: {ed_val}", img])
                    st.session_state['chat_history'][chat_id].append({"q": user_q, "a": chat_res.text})
                    st.rerun()
            st.markdown("---")

        if final_text_for_word:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_text_for_word)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")
