import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SAHIFA SOZLAMALARI
st.set_page_config(page_title="Manuscript AI Pro", page_icon="📜", layout="wide")

# --- DIZAYN ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; }
    .result-box { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    </style>
""", unsafe_allow_html=True)

# --- 2. XAVFSIZLIK (SECRETS) ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

try:
    # BU NOMLLAR SECRETS'DAGI BILAN BIR XIL BO'LISHI SHART
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Sirlari (GEMINI_API_KEY yoki APP_PASSWORD) sozlanmagan! Streamlit Settings > Secrets qismini tekshiring.")
    st.stop()

if not st.session_state.authenticated:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kirish kodi", type="password", key="login_key")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Xato kod!")
    st.stop()

# --- 3. AI MODELI ---
genai.configure(api_key=GEMINI_KEY)
# SIZNING RO'YXATINGIZDAGI ISHLAYDIGAN MODEL
model = genai.GenerativeModel('gemini-2.0-flash')

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 CHIQISH"):
        st.session_state.authenticated = False
        st.rerun()

# Asosiy ekran
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertiza Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Faylni yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Yuklanmoqda...'):
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(len(pdf)):
                    imgs.append(pdf[i].render(scale=3).to_pil())
            else:
                imgs.append(Image.open(uploaded_file))
            st.session_state.imgs = imgs
            st.session_state.last_fn = uploaded_file.name
            st.session_state.res = {}
            st.session_state.chat_history = {}

    st.markdown("### 📜 Varaqlar")
    cols = st.columns(min(len(st.session_state.imgs), 4))
    for idx, img in enumerate(st.session_state.imgs):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        st.session_state.res = {}
        prompt = f"Siz akademiksiz. {lang} va {era} uslubidagi qo'lyozmani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"Varaq {i+1} o'qilmoqda..."):
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state.res[i] = response.text
                except Exception as e:
                    st.error(f"Xato: {e}")

    if st.session_state.res:
        st.divider()
        final_doc = ""
        for idx, img in enumerate(st.session_state.imgs):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, use_container_width=True)
            with c2:
                txt = st.session_state.res.get(idx, "")
                st.markdown(f"<div class='result-box'>{txt}</div>", unsafe_allow_html=True)
            
            ed = st.text_area(f"Tahrir {idx+1}:", value=txt, height=400, key=f"edit_{idx}")
            final_doc += f"\n\n--- VARAQ {idx+1} ---\n{ed}"

            # Chat
            st.markdown(f"💬 **Varaq {idx+1} yuzasidan muloqot**")
            chat_id = f"chat_{idx}"
            if chat_id not in st.session_state.chat_history: st.session_state.chat_history[chat_id] = []
            for chat in st.session_state.chat_history[chat_id]:
                st.markdown(f"<div style='background-color:#e2e8f0; color:#000; padding:10px; border-radius:8px; margin-bottom:5px;'><b>Savol:</b> {chat['q']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='background-color:#fff; color:#1a1a1a; padding:10px; border-radius:8px; margin-bottom:15px; border:1px solid #d4af37;'><b>AI:</b> {chat['a']}</div>", unsafe_allow_html=True)

            u_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
            if st.button(f"So'rash {idx+1}", key=f"q_btn_{idx}"):
                if u_q:
                    with st.spinner("AI tahlil qilmoqda..."):
                        c_res = model.generate_content([f"Matn: {ed}\nSavol: {u_q}", img])
                        st.session_state.chat_history[chat_id].append({"q": u_q, "a": c_res.text})
                        st.rerun()

        if final_doc:
            doc = Document()
            doc.add_paragraph(final_doc)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORD (.docx)", bio.getvalue(), "academic_report.docx", key="dw_btn")
