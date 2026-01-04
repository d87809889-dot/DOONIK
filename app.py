import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Pro Master 2026",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN (KUCHAYTIRILGAN CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}

    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }

    /* AI TAHLIL KARTASI */
    .result-box {
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important;
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 17px; line-height: 1.7 !important;
    }

    /* TAHRIRLASH OYNASI */
    .stTextArea textarea {
        background-color: #fdfaf1 !important; color: #000000 !important; 
        border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important;
        font-size: 18px !important; padding: 20px !important;
    }

    /* CHAT DIZAYNI */
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #d4af37; }

    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    
    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important; border: 2px solid #c5a059 !important;
        font-weight: bold !important; width: 100% !important; padding: 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Google Verification Meta
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# ==========================================
# 2. XAVFSIZLIK VA PAROL TIZIMI
# ==========================================
if "auth" not in st.session_state:
    st.session_state.auth = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets (GEMINI_API_KEY va APP_PASSWORD) sozlanmagan!")
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

# ==========================================
# 3. AI MODELI (404 XATOSINI ILDIZI BILAN TUZATISH)
# ==========================================
genai.configure(api_key=GEMINI_KEY)

# MUHIM: 404 va v1beta xatosini yo'qotish uchun barqaror model identifikatorini tanlaymiz
@st.cache_resource
def load_stable_engine():
    """Googlening yangi barqaror (stable) tizimidagi modelga ulanadi"""
    # models/ prefiksi orqali v1 tizimiga qattiq ulanishni ta'minlaymiz
    try:
        return genai.GenerativeModel(model_name='gemini-1.5-flash')
    except:
        # Agar SDK eski bo'lsa, zaxira nomlarni sinaymiz
        return genai.GenerativeModel(model_name='gemini-1.5-flash-latest')

model = load_stable_engine()

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR
# ==========================================
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

# ==========================================
# 5. ASOSIY TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.markdown("---")
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.markdown("---")
    st.caption("✅ Model: 1.5 Flash (Stable v1)")
    st.caption("♻️ Sifat: DPI 200 (Optimallashgan)")
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertiza Markazi")
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
            
            st.session_state.imgs = imgs
            st.session_state.last_fn = uploaded_file.name
            st.session_state.results = {}
            st.session_state.chats = {}
            gc.collect()

    cols = st.columns(min(len(st.session_state.imgs), 4))
    for idx, img in enumerate(st.session_state.imgs):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        prompt = f"""
        Siz qadimgi matnshunos akademiksiz. 
        Ushbu {lang} tilidagi va {era} uslubidagi manbani tahlil qiling:
        1. PALEOGRAFIK TAVSIF. 2. TRANSLITERATSIYA. 3. SEMANTIK TARJIMA. 4. ILMIY IZOH.
        """
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"Varaq {i+1} ekspertizadan o'tmoqda...") as s:
                try:
                    payload = img_to_payload(img)
                    response = model.generate_content([prompt, payload])
                    st.session_state.results[i] = response.text
                    s.update(label=f"Varaq {i+1} tayyor!", state="complete")
                    time.sleep(1) # RPM limit himoyasi
                except Exception as e:
                    st.error(f"Xato: {e}")

    # --- RESULTS, EDITOR VA CHAT ---
    if st.session_state.results:
        st.divider()
        st.markdown("### 🖋 Ekspertiza Natijalari va Muloqot")
        
        final_doc_text = ""
        for idx, img in enumerate(st.session_state.imgs):
            if idx in st.session_state.results:
                st.markdown(f"#### 📖 Varaq {idx+1}")
                res = st.session_state.results[idx]
                
                c1, c2 = st.columns([1, 1.2])
                with c1: st.image(img, use_container_width=True)
                with c2: st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
                
                ed_val = st.text_area(f"Varaq {idx+1} tahriri:", value=res, height=400, key=f"ed_{idx}")
                final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

                st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan muloqot")
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-bubble-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-bubble-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("AI tahlil qilmoqda..."):
                            chat_prompt = f"Hujjat: {ed_val}\nSavol: {user_q}"
                            chat_res = model.generate_content([chat_prompt, img_to_payload(img)])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")

