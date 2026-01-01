import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document
import gc
import time

# 1. SEO VA SAHIFA SOZLAMALARI
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
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; }
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.05); color: #000000 !important; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 10px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #d4af37; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%); color: #c5a059 !important; font-weight: bold; width: 100%; padding: 10px; border: none; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets topilmadi! Streamlit Cloud sozlamalarini tekshiring.")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy parol", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Kod noto'g'ri!")
    st.stop()

# --- 4. AI MODELINI BARQAROR SOZLASH (FIX 404) ---
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_stable_model():
    """Google'ning yangi nomlash tizimidagi eng barqaror modelni tanlaydi"""
    # 404 xatosidan qochish uchun bir nechta barqaror nomlarni tekshiramiz
    model_names = ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-flash-latest"]
    for name in model_names:
        try:
            m = genai.GenerativeModel(model_name=name)
            return m
        except:
            continue
    return genai.GenerativeModel('gemini-pro-vision') # Oxirgi chora

model = load_stable_model()

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    if st.button("🚪 CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertiza Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Ilmiy manbani yuklang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state['imgs'] = []
if 'academic_results' not in st.session_state: st.session_state['academic_results'] = []
if 'chat_history' not in st.session_state: st.session_state['chat_history'] = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Fayl tayyorlanmoqda (DPI 200)...'):
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(uploaded_file)
                # Maksimal 15 sahifa (Limit uchun)
                for i in range(min(len(pdf), 15)):
                    imgs.append(pdf[i].render(scale=2).to_pil())
                pdf.close()
            else:
                imgs.append(Image.open(uploaded_file))
            st.session_state['imgs'] = imgs
            st.session_state['last_fn'] = uploaded_file.name
            st.session_state['academic_results'] = []
            st.session_state['chat_history'] = {}
            gc.collect()

    cols = st.columns(min(len(st.session_state['imgs']), 4))
    for idx, img in enumerate(st.session_state['imgs']):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width="stretch")

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        new_res = []
        # Eng kuchli akademik prompt
        prompt = f"Siz matnshunos akademiksiz. {lang} va {era} xatidagi ushbu qo'lyozmani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya (lotin). 3.Tarjima. 4.Izoh."
        
        for i, img in enumerate(st.session_state['imgs']):
            with st.status(f"Varaq {i+1} o'qilmoqda..."):
                try:
                    response = model.generate_content([prompt, img])
                    new_res.append(response.text)
                    time.sleep(3) # Limitdan qochish uchun
                except Exception as e:
                    new_res.append(f"Xato: {e}")
        st.session_state['academic_results'] = new_res

    # --- 6. TAHLIL, TAHRIR VA CHAT ---
    if st.session_state['academic_results']:
        st.divider()
        final_doc_text = ""
        for idx, (img, res) in enumerate(zip(st.session_state['imgs'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, width="stretch")
            with c2: st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            ed = st.text_area(f"Tahrir {idx+1}:", value=res, height=400, key=f"ed_{idx}")
            final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{ed}"

            # Interaktiv Chat
            st.markdown(f"##### 💬 Varaq {idx+1} muloqoti")
            cid = f"chat_{idx}"
            if cid not in st.session_state['chat_history']: st.session_state['chat_history'][cid] = []

            for chat in st.session_state['chat_history'][cid]:
                st.markdown(f"""<div class='chat-bubble-user'><b>Savol:</b> {chat['q']}</div>""", unsafe_allow_html=True)
                st.markdown(f"""<div class='chat-bubble-ai'><b>AI:</b> {chat['a']}</div>""", unsafe_allow_html=True)

            user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
            if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                if user_q:
                    try:
                        # Tejamkor chat (faqat matn bilan)
                        chat_res = model.generate_content(f"Hujjat tahlili: {ed}\n\nSavol: {user_q}\nAkademik javob ber.")
                        st.session_state['chat_history'][cid].append({"q": user_q, "a": chat_res.text})
                        st.rerun()
                    except:
                        st.error("Limit oshdi. Biroz kuting.")
            st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")
            st.balloons()

