import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA AKADEMIK MUHIT SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Master 2026", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; }
    .result-box {
        background-color: #ffffff !important; padding: 25px; border-radius: 12px;
        border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        color: #1a1a1a !important; font-size: 17px;
    }
    .stTextArea textarea {
        background-color: #fdfaf1 !important; color: #000000 !important; 
        border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace;
    }
    .user-msg { background-color: #e2e8f0; color: #000; padding: 10px; border-radius: 8px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .ai-msg { background-color: #ffffff; color: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px solid #d4af37; margin-bottom: 15px; }
    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important; font-weight: bold !important; width: 100% !important;
    }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK VA SECRETS ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets topilmadi! Streamlit Settings > Secrets bo'limini tekshiring.")
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

# --- 4. AI MODELINI SOZLASH (FIX 404) ---
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_stable_model():
    # 404 xatosini oldini olish uchun nomlar ustuvorligi
    model_names = ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-flash-latest"]
    for name in model_names:
        try:
            m = genai.GenerativeModel(name)
            return m
        except:
            continue
    return genai.GenerativeModel("gemini-pro-vision")

model = load_stable_model()

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.authenticated = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.title("Raqamli Qo'lyozmalar Ekspertiza Markazi")
file = st.file_uploader("Ilmiy manbani yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if file:
    if st.session_state.get('last_fn') != file.name:
        with st.spinner('Yuklanmoqda...'):
            imgs = []
            if file.type == "application/pdf":
                pdf = pdfium.PdfDocument(file)
                for i in range(len(pdf)):
                    imgs.append(pdf[i].render(scale=2.5).to_pil())
            else:
                imgs.append(Image.open(file))
            st.session_state.imgs = imgs
            st.session_state.last_fn = file.name
            st.session_state.res = {}
            st.session_state.chat = {}

    # Prevyu
    cols = st.columns(min(len(st.session_state.imgs), 4))
    for idx, img in enumerate(st.session_state.imgs):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        prompt = f"Siz matnshunos akademiksiz. {lang} va {era} qo'lyozmasini tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"Varaq {i+1} o'qilmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state.res[i] = response.text
                    status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato (Varaq {i+1}): {e}")

    # --- 6. TAHLIL VA INTERAKTIV CHAT ---
    if st.session_state.get('res'):
        st.divider()
        doc_content = ""
        for idx, img in enumerate(st.session_state.imgs):
            with st.container():
                st.subheader(f"📖 Varaq {idx+1}")
                txt = st.session_state.res.get(idx, "")
                
                c1, c2 = st.columns([1, 1.2])
                with c1: st.image(img, use_container_width=True)
                with c2: st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{txt}</div>", unsafe_allow_html=True)
                
                edited = st.text_area(f"Tahrir ({idx+1}):", value=txt, height=350, key=f"edit_{idx}")
                doc_content += f"\n\n--- VARAQ {idx+1} ---\n{edited}"

                # Interaktiv Chat
                st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan muloqot")
                cid = f"chat_{idx}"
                if cid not in st.session_state.chat: st.session_state.chat[cid] = []

                for chat in st.session_state.chat[cid]:
                    st.markdown(f"<div class='user-msg'><b>Savol:</b> {chat['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='ai-msg'><b>AI:</b> {chat['a']}</div>", unsafe_allow_html=True)

                q_in = st.text_input("Savol yozing:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"q_btn_{idx}"):
                    if q_in:
                        with st.spinner("AI tahlil qilmoqda..."):
                            c_prompt = f"Ushbu qo'lyozma matni asosida akademik javob bering: {q_in}\nMatn: {edited}"
                            c_res = model.generate_content([c_prompt, img])
                            st.session_state.chat[cid].append({"q": q_in, "a": c_res.text})
                            st.rerun()
                st.divider()

        if doc_content:
            doc = Document()
            doc.add_paragraph(doc_content)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx", key="doc_down")
