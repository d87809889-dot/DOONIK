import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA ILMIY MUHIT SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Master v10.0", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; padding-bottom: 10px; }
    
    /* TAHRIRLASH OYNASI - MATN HAR DOIM QORA */
    .stTextArea textarea {
        background-color: #fdfaf1 !important;
        color: #000000 !important; 
        border: 2px solid #c5a059 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 17px !important;
    }

    /* AI TAHLIL KARTASI */
    .result-box {
        background-color: #ffffff; padding: 20px; border-radius: 12px;
        border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        color: #1a1a1a !important; font-size: 17px; margin-bottom: 15px;
    }

    /* CHAT ELEMENTLARI */
    .user-box { background-color: #e2e8f0; color: #000; padding: 12px; border-radius: 8px; border-left: 5px solid #1e3a8a; margin-bottom: 10px; }
    .ai-box { background-color: #ffffff; color: #1a1a1a; padding: 12px; border-radius: 8px; border: 1px solid #d4af37; margin-bottom: 20px; }

    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important; font-weight: bold !important; width: 100% !important;
    }
    </style>
""", unsafe_allow_html=True)

# Google Search Console Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# --- 3. XAVFSIZLIK VA SESSION STATE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'res' not in st.session_state: st.session_state.res = {}
if 'chat_history' not in st.session_state: st.session_state.chat_history = {}

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

if not st.session_state.authenticated:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kod", type="password", key="login_key")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Xato kod!")
    st.stop()

# --- 4. AI MODELINI SOZLASH ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 CHIQISH"):
        st.session_state.authenticated = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertiza Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Ilmiy manbani yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Yuklanmoqda...'):
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(len(pdf)):
                    imgs.append(pdf[i].render(scale=2.5).to_pil()) # Barqarorlik uchun 2.5 scale
            else:
                imgs.append(Image.open(uploaded_file))
            st.session_state.imgs = imgs
            st.session_state.last_fn = uploaded_file.name
            st.session_state.res = {}
            st.session_state.chat_history = {}

    # Prevyu
    cols = st.columns(min(len(st.session_state.imgs), 4))
    for idx, img in enumerate(st.session_state.imgs):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ TAHLILNI BOSHLASH'):
        prompt = f"Siz akademiksiz. {lang} va {era} uslubidagi qo'lyozmani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"Varaq {i+1} o'qilmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state.res[i] = response.text
                    status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato: {e}")

    # --- 6. TAHLIL VA INTERAKTIV CHAT (BARQAROR TIZIM) ---
    if st.session_state.res:
        st.divider()
        final_text_doc = ""
        
        for idx, img in enumerate(st.session_state.imgs):
            # removeChild xatosini oldini olish uchun har bir varaqni statik konteynerga joylaymiz
            with st.container():
                st.subheader(f"📖 Varaq {idx+1}")
                res_content = st.session_state.res.get(idx, "")
                
                c1, c2 = st.columns([1, 1.2])
                with c1:
                    st.image(img, use_container_width=True)
                with c2:
                    st.markdown(f"<div class='result-box'><b>AI Xulosasi:</b><br><br>{res_content}</div>", unsafe_allow_html=True)
                
                # Tahrirlash oynasi
                ed_val = st.text_area(f"Tahrir ({idx+1}):", value=res_content, height=350, key=f"edit_{idx}")
                final_text_doc += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

                # Chat bo'limi
                st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan muloqot")
                chat_id = f"chat_{idx}"
                if chat_id not in st.session_state.chat_history:
                    st.session_state.chat_history[chat_id] = []

                # Xabarlarni ko'rsatish
                for chat in st.session_state.chat_history[chat_id]:
                    st.markdown(f"<div class='user-box'><b>Savol:</b> {chat['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='ai-box'><b>AI:</b> {chat['a']}</div>", unsafe_allow_html=True)

                # Savol yozish (Noyob kalitlar bilan)
                u_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"q_btn_{idx}"):
                    if u_q:
                        with st.spinner("AI tahlil qilmoqda..."):
                            chat_prompt = f"Ushbu qo'lyozma matni yuzasidan akademik javob bering: {u_q}\nMatn: {ed_val}"
                            chat_res = model.generate_content([chat_prompt, img])
                            st.session_state.chat_history[chat_id].append({"q": u_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_text_doc:
            doc = Document()
            doc.add_paragraph(final_text_doc)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORD (.docx)", bio.getvalue(), "report.docx", key="doc_down")
            st.balloons()
