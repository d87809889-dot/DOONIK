import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document
import gc
import time

# 1. SEO VA AKADEMIK MUHIT SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Master 2026", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK-AKADEMIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; font-size: 17px; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; font-size: 18px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%); color: #c5a059 !important; font-weight: bold; width: 100%; padding: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets topilmadi!")
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
                st.error("Xato!")
    st.stop()

# --- 4. MODELNI JONLI TEKSHIRIB YUKLASH (404 VA 429 FIX) ---
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_best_stable_model():
    """Serverdan hozirgi ishlayotgan 1.5 Flash nomini qidiradi"""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Faqat 1500 talik limitga ega modellarni tanlaymiz
        for target in ["models/gemini-1.5-flash-latest", "models/gemini-1.5-flash", "models/gemini-flash-latest"]:
            if target in models:
                return genai.GenerativeModel(model_name=target)
        return genai.GenerativeModel(model_name=models[0])
    except:
        return genai.GenerativeModel(model_name='gemini-1.5-flash')

model = load_best_stable_model()

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    if st.button("🚪 CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Faylni yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state['imgs'] = []
if 'academic_results' not in st.session_state: st.session_state['academic_results'] = []
if 'chat_histories' not in st.session_state: st.session_state['chat_histories'] = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('DPI 300 sifatda tayyorlanmoqda...'):
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(min(len(pdf), 15)):
                    imgs.append(pdf[i].render(scale=3).to_pil())
                    gc.collect()
                pdf.close()
            else:
                imgs.append(Image.open(uploaded_file))
            st.session_state['imgs'] = imgs
            st.session_state['last_fn'] = uploaded_file.name
            st.session_state['academic_results'] = []
            st.session_state['chat_histories'] = {}

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
                    time.sleep(4) # Limit himoyasi
                except Exception as e:
                    new_results.append(f"Xato: {e}")
        st.session_state['academic_results'] = new_results

    # --- 6. TAHLIL VA INTERAKTIV CHAT ---
    if st.session_state['academic_results']:
        st.divider()
        final_text_doc = ""
        for idx, (img, res) in enumerate(zip(st.session_state['imgs'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, width="stretch")
            with c2: st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
            
            ed_val = st.text_area(f"Tahrir {idx+1}:", value=res, height=400, key=f"ed_{idx}")
            final_text_doc += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

            # Interaktiv Chat (Fixed Colors)
            st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan muloqot")
            chat_id = f"chat_{idx}"
            if chat_id not in st.session_state['chat_histories']: st.session_state['chat_histories'][chat_id] = []

            for chat in st.session_state['chat_histories'][chat_id]:
                st.markdown(f"""<div style="background-color: #e2e8f0; color: #000000 !important; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #1e3a8a;">
                <b style="color: #1e3a8a;">Savol:</b> {chat['q']}</div>""", unsafe_allow_html=True)
                st.markdown(f"""<div style="background-color: #ffffff; color: #000000 !important; padding: 10px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #d4af37;">
                <b style="color: #0c1421;">AI Javobi:</b> {chat['a']}</div>""", unsafe_allow_html=True)

            user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
            if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                if user_q:
                    try:
                        # Chat tejamkorligi: rasm yuborilmaydi
                        chat_res = model.generate_content(f"Hujjat tahlili: {ed_val}\nSavol: {user_q}\nAkademik javob ber.")
                        st.session_state['chat_histories'][chat_id].append({"q": user_q, "a": chat_res.text})
                        st.rerun()
                    except Exception as e:
                        st.error("Limit oshdi. 60 soniya kuting.")
            st.markdown("---")

        if final_text_doc:
            doc = Document()
            doc.add_paragraph(final_text_doc)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")
