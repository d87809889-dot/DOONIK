import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from supabase import create_client, Client

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI Platinum - Expert Edition",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 15px; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        color: #1a1a1a; line-height: 1.8; font-size: 17px;
    }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-user { background-color: #e2e8f0; color: #000 !important; padding: 12px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #d4af37; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; color: #fdfaf1 !important; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 12px !important; border: 1px solid #c5a059; }
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 10px; cursor: zoom-in; }
    .magnifier-container img:hover { transform: scale(2.5); transition: 0.3s ease; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CORE SERVICES (SUPABASE & AI)
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

try:
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Settings > Secrets qismini tekshiring.")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA PORTALI</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Parol noto'g'ri!")
    st.stop()

# --- AI MOTORINI SOZLASH ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(model_name='gemini-1.5-flash')

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR (SAFE RENDER)
# ==========================================
def img_to_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_live_credits(email: str):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

@st.cache_data(show_spinner=False)
def render_page_safe(file_content: bytes, page_idx: int, is_pdf: bool) -> Image.Image:
    """PDF bo'lsa render qiladi, rasm bo'lsa shunchaki ochadi (BEXATO USUL)"""
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            img = pdf[page_idx].render(scale=3.0).to_pil()
            pdf.close()
            return img
        else:
            return Image.open(io.BytesIO(file_content))
    except Exception as e:
        st.error(f"Faylni o'qishda xato: {e}")
        return None

# ==========================================
# 4. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
    st.metric("💳 Kreditlar", fetch_live_credits(st.session_state.u_email))
    
    st.divider()
    st.markdown("### 🛠 Tasvir Laboratoriyasi")
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Siyoh o'tkirligi:", 0.5, 3.0, 1.3)
    rotate_val = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    
    st.divider()
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertiza Markazi")
uploaded_file = st.file_uploader("Faylni yuklang (PDF, PNG, JPG)", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    # Fayl yangilanganda xotirani tozalash
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Fayl tayyorlanmoqda...'):
            file_bytes = uploaded_file.getvalue()
            is_pdf_file = uploaded_file.type == "application/pdf"
            temp_imgs = []
            
            if is_pdf_file:
                pdf_doc = pdfium.PdfDocument(file_bytes)
                for i in range(min(len(pdf_doc), 15)):
                    temp_imgs.append(render_page_safe(file_bytes, i, True))
                pdf_doc.close()
            else:
                temp_imgs.append(render_page_safe(file_bytes, 0, False))
            
            st.session_state.imgs = temp_imgs
            st.session_state.last_fn = uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    # Image processing (brightness/contrast)
    processed_imgs = []
    for img in st.session_state.imgs:
        if img:
            p_img = img.rotate(rotate_val, expand=True)
            p_img = ImageEnhance.Brightness(p_img).enhance(brightness)
            p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
            processed_imgs.append(p_img)

    selected_pages = st.multiselect("Varaqlarni tanlang:", range(len(processed_imgs)), default=[0], format_func=lambda x: f"Varaq {x+1}")

    if not st.session_state.results:
        cols = st.columns(min(len(selected_pages), 4) if selected_pages else 1)
        for i, idx in enumerate(selected_pages):
            with cols[i % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        current_credits = fetch_live_credits(st.session_state.u_email)
        if current_credits >= len(selected_pages):
            prompt = f"Expert analysis of {lang} manuscript in {style} style. 1.Transliteration 2.Translation 3.Expert Notes."
            for idx in selected_pages:
                with st.status(f"Sahifa {idx+1} tahlil qilinmoqda...") as s:
                    try:
                        response = model.generate_content([prompt, img_to_payload(processed_imgs[idx])])
                        st.session_state.results[idx] = response.text
                        # Kreditni yangilash
                        db.table("profiles").update({"credits": current_credits - 1}).eq("email", st.session_state.u_email).execute()
                        current_credits -= 1
                        s.update(label=f"Sahifa {idx+1} tayyor!", state="complete")
                    except Exception as e: st.error(f"Xato: {e}")
            st.rerun()
        else: st.warning("Kredit yetarli emas!")

    # --- NATIJALAR ---
    if st.session_state.results:
        st.divider()
        final_doc_all = ""
        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res = st.session_state.results[idx]
            c1, c2 = st.columns([1, 1.2])
            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
                st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=300, key=f"ed_{idx}")
                final_doc_all += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}"

                # Chat
                st.session_state.chats.setdefault(idx, [])
                for chat in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>Savol:</b> {chat['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>AI:</b> {chat['a']}</div>", unsafe_allow_html=True)

                u_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if u_q:
                        with st.spinner("..."):
                            chat_res = model.generate_content([f"Doc: {st.session_state.results[idx]}\nQ: {u_q}", img_to_payload(processed_imgs[idx])])
                            st.session_state.chats[idx].append({"q": u_q, "a": chat_res.text}); st.rerun()

        if final_doc_all:
            doc = Document()
            doc.add_paragraph(final_doc_all)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORD HISOBOTNI YUKLAB OLISH", bio.getvalue(), "manuscript_report.docx")

gc.collect()
