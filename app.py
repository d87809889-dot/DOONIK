import streamlit as st
import google.generativeai as genai
import pypdfium2 as pdfium
from PIL import Image
import io, gc, hashlib, time, base64
from docx import Document

# --- 1. SAHIFA VA SEO SOZLAMALARI ---
st.set_page_config(
    page_title="Manuscript AI - Ultimate Stable Edition",
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
    h1, h2, h3, h4 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; padding-bottom: 10px; }
    .result-box { 
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 18px !important; line-height: 1.7 !important;
    }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 10px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK (PAROL) ---
if "auth" not in st.session_state:
    st.session_state.auth = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop()

# --- 4. AQLLI MODEL NAVIGATORI (404 XATOSINI YO'QOTISH) ---
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_best_available_model():
    """Googledan ishlayotgan modelni qidiradi va zaxira tizimini ishlatadi"""
    # 1. 1500 ta limitli barqaror ismlar
    stable_targets = ['models/gemini-1.5-flash', 'gemini-1.5-flash', 'models/gemini-1.5-flash-latest']
    # 2. Yangi lekin limiti kamroq bo'lishi mumkin bo'lgan ismlar (Zaxira)
    backup_targets = ['models/gemini-2.0-flash', 'models/gemini-2.0-flash-exp', 'models/gemini-pro-vision']
    
    all_targets = stable_targets + backup_targets
    
    # Google'dan ruxsat berilgan hamma ismlarni olamiz
    try:
        available_on_server = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for target in all_targets:
            if target in available_on_server or target.replace('models/', '') in available_on_server:
                return genai.GenerativeModel(model_name=target), target
    except:
        pass
    
    # Agar ro'yxatni olib bo'lmasa, eng ishonchlisini majburan qaytaramiz
    return genai.GenerativeModel(model_name='models/gemini-1.5-flash'), 'models/gemini-1.5-flash'

model, active_model_name = load_best_available_model()

# --- 5. YORDAMCHI FUNKSIYALAR ---
def img_to_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

@st.cache_data(show_spinner=False)
def render_page_optimized(file_content: bytes, page_idx: int, scale: float, is_pdf: bool) -> Image.Image:
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            page = pdf[page_idx]
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil()
            pdf.close()
            gc.collect()
            return img
        else:
            return Image.open(io.BytesIO(file_content))
    except:
        return None

# --- 6. SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.markdown("---")
    st.write(f"🤖 **Model:** `{active_model_name.replace('models/', '')}`")
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Fors", "Arab", "Usmonli Turk"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

# --- 7. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Ekspertiza Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Ilmiy manbani yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Manba tayyorlanmoqda...'):
            file_bytes = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(file_bytes)
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page_optimized(file_bytes, i, 2.0, True))
                pdf.close()
            else:
                imgs.append(render_page_optimized(file_bytes, 0, 2.0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    cols = st.columns(min(len(st.session_state.imgs), 4))
    for idx, img in enumerate(st.session_state.imgs):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        prompt = f"Siz matnshunos akademiksiz. {lang} tilidagi va {era} uslubidagi ushbu manbani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"Varaq {i+1} o'qilmoqda...") as s:
                try:
                    response = model.generate_content([prompt, img_to_payload(img)])
                    st.session_state.results[i] = response.text
                    s.update(label=f"Varaq {i+1} tayyor!", state="complete")
                    time.sleep(2)
                except Exception as e:
                    st.error(f"Xato: {e}")

    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        for idx, img in enumerate(st.session_state.imgs):
            if idx in st.session_state.results:
                st.markdown(f"#### 📖 Varaq {idx+1}")
                res = st.session_state.results[idx]
                c1, c2 = st.columns([1, 1.2])
                with c1: st.image(img, use_container_width=True)
                with c2: st.markdown(f"<div class='result-box'><b>Xulosa:</b><br><br>{res}</div>", unsafe_allow_html=True)
                
                ed_val = st.text_area(f"Tahrir {idx+1}:", value=res, height=400, key=f"ed_{idx}")
                final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

                st.markdown(f"##### 💬 Varaq {idx+1} muloqoti")
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("AI tahlil qilmoqda..."):
                            chat_res = model.generate_content([f"Hujjat: {ed_val}\nSavol: {user_q}", img_to_payload(img)])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "report.docx")
