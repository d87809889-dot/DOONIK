import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SAHIFA VA SEO SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Master 2026", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK-AKADEMIK DIZAYN ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; font-size: 17px; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace; font-size: 18px; }
    .user-box { background-color: #e2e8f0; color: #000; padding: 12px; border-radius: 8px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .ai-box { background-color: #ffffff; color: #1a1a1a; padding: 12px; border-radius: 8px; border: 1px solid #d4af37; margin-bottom: 15px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; border: 2px solid #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 12px !important; }
    </style>
""", unsafe_allow_html=True)

# Google Search Console Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# --- 3. XAVFSIZLIK ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

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
        pwd_input = st.text_input("Maxfiy kirish kodi", type="password", key="login_pass")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Xato kod!")
    st.stop()

# --- 4. AI MODELI (SIZNING RO'YXATINGIZDAGI ENG KUCHLISI: GEMINI 2.0 FLASH) ---
genai.configure(api_key=GEMINI_KEY)
# SIZNING RO'YXATINGIZDAGI ANIQ NOM: models/gemini-2.0-flash
model = genai.GenerativeModel('gemini-2.0-flash')

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.authenticated = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertiza Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Ilmiy manbani yuklang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    if 'imgs' not in st.session_state or st.session_state.get('last_fn') != uploaded_file.name:
        imgs = []
        if uploaded_file.type == "application/pdf":
            with st.spinner('DPI 300 sifatda raqamlashtirilmoqda...'):
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
        prompt = f"""
        Siz qadimiy matnshunos va paleograf bo'yicha dunyo darajasidagi akademiksiz. 
        Ushbu {lang} tilidagi va {era} uslubidagi manbani quyidagi mezonlar asosida tahlil qiling:
        1. PALEOGRAFIK TAVSIF. 2. DIPLOMATIK TRANSLITERATSIYA. 3. SEMANTIK TARJIMA. 4. ILMIY IZOH.
        Javobni o'ta professional akademik tilda bering.
        """
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"Varaq {i+1} ekspertizadan o'tmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state.res[i] = response.text
                    status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato (Varaq {i+1}): {e}")

    # --- 6. NATIJALAR, TAHRIR VA INTERAKTIV CHAT ---
    if st.session_state.get('res'):
        st.divider()
        final_text_doc = ""
        for idx, img in enumerate(st.session_state.imgs):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res_txt = st.session_state.res.get(idx, "")
            
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, use_container_width=True)
            with c2: st.markdown(f"<div class='result-box'><b>AI Xulosasi:</b><br><br>{res_txt}</div>", unsafe_allow_html=True)
            
            ed_val = st.text_area(f"Tahrir ({idx+1}):", value=res_txt, height=400, key=f"ed_{idx}")
            final_text_doc += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

            # --- CHAT BO'LIMI (Fixed Colors) ---
            st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan muloqot")
            cid = f"chat_{idx}"
            if cid not in st.session_state.chat_history: st.session_state.chat_history[cid] = []

            for chat in st.session_state.chat_history[cid]:
                st.markdown(f"<div class='user-box'><b>Savol:</b> {chat['q']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='ai-box'><b>AI:</b> {chat['a']}</div>", unsafe_allow_html=True)

            u_q = st.text_input(f"Savol yozing ({idx+1}):", key=f"q_in_{idx}")
            if st.button(f"So'rash {idx+1}", key=f"q_btn_{idx}"):
                if u_q:
                    with st.spinner("AI tahlil qilmoqda..."):
                        c_prompt = f"Ushbu qo'lyozma matni asosida akademik javob bering: {u_q}\nMatn: {ed_val}"
                        c_res = model.generate_content([c_prompt, img])
                        st.session_state.chat_history[cid].append({"q": u_q, "a": c_res.text})
                        st.rerun()
            st.markdown("---")

        if final_text_doc:
            doc = Document()
            doc.add_paragraph(final_text_doc)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx", key="doc_down")
