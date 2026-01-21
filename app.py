import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64, asyncio
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Global Academic v27.0",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="auto" # Mobil qurilmalarda avtomatik yashiriladi
)

# --- PROFESSIONAL ANTIK DIZAYN (MOBILE-FIRST CSS) ---
st.markdown("""
    <style>
    /* 1. Mobil qurilmalar uchun menyu tugmasini (>) saqlab qolish */
    header[data-testid="stHeader"] {
        background: rgba(0,0,0,0) !important;
        visibility: visible !important;
    }
    button[data-testid="stSidebarCollapseButton"] {
        background-color: #0c1421 !important;
        color: #c5a059 !important;
        border: 1px solid #c5a059 !important;
        border-radius: 8px !important;
    }

    /* 2. Asosiy fon va shriftlar */
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    
    /* 3. Mobil qurilmalarda kontentni to'g'ri joylash (Padding) */
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 3.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
    }

    /* 4. Akademik natijalar kartasi */
    .result-box { 
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 17px; line-height: 1.8;
    }
    
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 12px !important; border: 1px solid #c5a059; }
    
    /* Lupa effekti */
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 10px; cursor: zoom-in; }
    .magnifier-container img { transition: transform 0.3s ease; }
    .magnifier-container:hover img { transform: scale(2.5); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. XAVFSIZLIK VA BAZA (SUPABASE)
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == st.secrets["APP_PASSWORD"]:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop()

# ==========================================
# 3. AI MOTORINI SOZLASH (DAXLSIZ)
# ==========================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(model_name='gemini-1.5-flash')

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR
# ==========================================
def img_to_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG") # Lossless format for better OCR
    return {"mime_type": "image/png", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_live_credits(email: str):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

def use_credit_atomic(email: str):
    curr = fetch_live_credits(email)
    if curr > 0:
        db.table("profiles").update({"credits": curr - 1}).eq("email", email).execute()
        return True
    return False

@st.cache_data(show_spinner=False)
def render_page_optimized(file_content: bytes, page_idx: int, scale: float, is_pdf: bool) -> Image.Image:
    """Xotira uchun optimallashgan va keshlanadigan renderlash"""
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            img = pdf[page_idx].render(scale=scale).to_pil()
            pdf.close()
            gc.collect()
            return img
        return Image.open(io.BytesIO(file_content))
    except: return None

# ==========================================
# 5. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **User:** `{st.session_state.u_email}`")
    live_credits = fetch_live_credits(st.session_state.u_email)
    st.metric("💳 Kreditlar", f"{live_credits}")
    
    st.divider()
    lang = st.selectbox("Hujjat tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    
    st.divider()
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)
    
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Manuscript AI Research Center")
uploaded_file = st.file_uploader("Faylni yuklang (PDF/Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Preparing...'):
            file_bytes = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(file_bytes)
                for i in range(min(len(pdf), 15)): # Max 15 pages safety
                    imgs.append(render_page_optimized(file_bytes, i, 3.5, True))
                pdf.close()
            else:
                imgs.append(render_page_optimized(file_bytes, 0, 1.0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    # Tasvirlarga ishlov berish
    processed_imgs = []
    for img in st.session_state.imgs:
        p_img = ImageEnhance.Brightness(img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    if not st.session_state.results:
        cols = st.columns(min(len(processed_imgs), 4))
        for idx, img in enumerate(processed_imgs):
            with cols[idx % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(img, caption=f"Varaq {idx+1}", width=None)
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        if live_credits >= len(processed_imgs):
            prompt = f"Siz matnshunos akademiksiz. {lang} va {era} uslubidagi ushbu manbani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya (Lotin). 3.Tarjima (O'zbek). 4.Izoh."
            for i, img in enumerate(processed_imgs):
                with st.status(f"Sahifa {i+1}...") as s:
                    try:
                        # Async-like blocking call in thread
                        response = model.generate_content([prompt, img_to_payload(img)])
                        if response.candidates and response.candidates[0].content.parts:
                            st.session_state.results[i] = response.text
                            use_credit_atomic(st.session_state.u_email)
                            s.update(label="Tayyor!", state="complete")
                        else:
                            st.error(f"AI bloklandi (Reason: {response.candidates[0].finish_reason})")
                    except Exception as e: st.error(f"Xato: {e}")
            st.rerun()
        else: st.warning("Kredit yetarli emas!")

    # --- NATIJALAR VA CHAT ---
    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        for idx, img in enumerate(processed_imgs):
            if idx in st.session_state.results:
                st.markdown(f"#### 📖 Varaq {idx+1}")
                res = st.session_state.results[idx]
                c1, c2 = st.columns([1, 1.2])
                with c1:
                    st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                    st.image(img, width=None)
                    st.markdown('</div>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div class='result-box'><b>AI Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
                    st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"ed_{idx}")
                    final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}"

                    # Chat
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user'><b>Savol:</b> {ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                    user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                    if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                        if user_q:
                            with st.spinner("AI tahlil qilmoqda..."):
                                chat_res = model.generate_content([f"Hujjat: {st.session_state.results[idx]}\nSavol: {user_q}", img_to_payload(processed_imgs[idx])])
                                st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                                st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "expert_report.docx")

gc.collect()
