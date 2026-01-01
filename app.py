import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA SAHIFA SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Enterprise 2026", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK-AKADEMIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    /* Streamlit reklamalarini yashirish */
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}

    /* Pergament foni */
    .main { 
        background-color: #f4ecd8 !important; 
        color: #1a1a1a !important;
        font-family: 'Times New Roman', serif;
    }

    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }

    /* AI TAHLIL KARTASI */
    .result-box {
        background-color: #ffffff !important;
        padding: 25px !important;
        border-radius: 12px !important;
        border-left: 10px solid #c5a059 !important;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important;
        font-size: 17px;
    }

    /* TAHRIRLASH OYNASI - MATN HAR DOIM QORA */
    .stTextArea textarea {
        background-color: #fdfaf1 !important;
        color: #000000 !important; 
        border: 2px solid #c5a059 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 18px !important;
        padding: 20px !important;
    }

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
    st.error("Secrets (GEMINI_API_KEY yoki APP_PASSWORD) sozlanmagan!")
    st.stop()

if not st.session_state.authenticated:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kirish kodi", type="password", key="main_pass")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Kod noto'g'ri!")
    st.stop()

# --- 4. AI MODELINI SOZLASH (SIZDA MAVJUD BO'LGAN MODEL) ---
genai.configure(api_key=GEMINI_KEY)

# Terminaldan olingan ma'lumotga ko'ra eng yaxshi model nomini tanlaymiz
# Bu 404 xatosini ildizi bilan yo'qotadi
model = genai.GenerativeModel('gemini-2.0-flash')

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], key="s_lang")
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"], key="s_era")
    st.divider()
    if st.button("🚪 TIZIMDAN CHIQISH", key="logout"):
        st.session_state.authenticated = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertiza Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Ilmiy manbani yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if uploaded_file:
    # Fayl almashganda xotirani yangilash
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('DPI 300 sifatda raqamlashtirilmoqda...'):
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

    # Prevyu
    cols = st.columns(min(len(st.session_state.imgs), 4))
    for idx, img in enumerate(st.session_state.imgs):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH', key="start_analysis"):
        prompt = f"Siz matnshunos akademiksiz. {lang} va {era} uslubidagi qo'lyozmani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"Varaq {i+1} o'qilmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    st.session_state.res[i] = response.text
                    status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato: {e}")

    # --- 6. TAHLIL, TAHRIR VA INTERAKTIV CHAT ---
    if st.session_state.res:
        st.divider()
        st.markdown("### 🖋 Natijalar va Ilmiy Tahrir")
        
        final_text_for_word = ""
        for idx, img in enumerate(st.session_state.imgs):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res_txt = st.session_state.res.get(idx, "")
            
            # Side-by-side qismi
            c1, c2 = st.columns([1, 1.2])
            with c1:
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{res_txt}</div>", unsafe_allow_html=True)
            
            # Tahrirlash oynasi
            st.write(f"**Varaq {idx+1} bo'yicha yakuniy tahrir:**")
            ed_val = st.text_area("", value=res_txt, height=400, key=f"ed_{idx}", label_visibility="collapsed")
            final_text_for_word += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

            # --- INTERAKTIV CHAT BO'LIMI ---
            st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan muloqot")
            cid = f"chat_{idx}"
            if cid not in st.session_state.chat_history: st.session_state.chat_history[cid] = []

            # Chat tarixini chiqarish (Majburiy qora matn bilan)
            for chat in st.session_state.chat_history[cid]:
                st.markdown(f"""<div style="background-color: #e2e8f0; color: #000; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #1e3a8a;">
                <b>Savol:</b> {chat['q']}</div>""", unsafe_allow_html=True)
                st.markdown(f"""<div style="background-color: #fff; color: #1a1a1a; padding: 12px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #d4af37;">
                <b>AI:</b> {chat['a']}</div>""", unsafe_allow_html=True)

            u_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
            if st.button(f"So'rash {idx+1}", key=f"q_btn_{idx}"):
                if u_q:
                    with st.spinner("AI tahlil qilmoqda..."):
                        chat_prompt = f"Ushbu qo'lyozma matni asosida akademik javob bering: {u_q}\nMatn: {ed_val}"
                        chat_res = model.generate_content([chat_prompt, img])
                        st.session_state.chat_history[cid].append({"q": u_q, "a": chat_res.text})
                        st.rerun()
            st.markdown("---")

        if final_text_for_word:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_text_for_word)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx", key="word_down")
            st.balloons()
