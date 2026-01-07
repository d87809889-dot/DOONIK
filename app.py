import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# ==========================================
# 1. TIZIM VA PREMIUM SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Global Academic Master",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PREMIUM UI & UX DIZAYN (ADVANCED CSS) ---
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
    /* Umumiy fon va Shriftlar */
    .main { background-color: #f4ecd8 !important; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Playfair Display', serif !important; color: #0c1421 !important; border-bottom: 2px solid #c5a059; padding-bottom: 15px; }
    
    /* Natija kartalari (Premium Glassmorphism) */
    .result-box { 
        background: rgba(255, 255, 255, 0.9) !important;
        backdrop-filter: blur(10px);
        padding: 30px !important; 
        border-radius: 20px !important; 
        border: 1px solid rgba(197, 160, 89, 0.3) !important;
        box-shadow: 0 15px 35px rgba(0,0,0,0.05) !important;
        color: #1a1a1a !important; 
        line-height: 1.8 !important;
        font-size: 17px !important;
    }

    /* Tahrirlash oynasi (Custom Styling) */
    .stTextArea textarea {
        background-color: #ffffff !important;
        color: #000000 !important; 
        border: 1px solid #c5a059 !important;
        border-radius: 12px !important;
        font-family: 'Courier New', monospace !important;
        font-size: 16px !important;
    }

    /* Sidebar - Premium Dark Mode */
    section[data-testid="stSidebar"] {
        background-color: #0c1421 !important;
        border-right: 3px solid #c5a059;
    }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }

    /* Tugmalar - Premium Gradient */
    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important;
        border: 1px solid #c5a059 !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        padding: 14px 28px !important;
        transition: all 0.4s ease !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stButton>button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 10px 20px rgba(197, 160, 89, 0.4) !important;
        background: #c5a059 !important;
        color: #0c1421 !important;
    }

    /* Chat xabarlari */
    .chat-user { background-color: #e2e8f0; color: #000; padding: 15px; border-radius: 15px; border-bottom-right-radius: 0; margin-bottom: 10px; border-left: 5px solid #1e3a8a; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a; padding: 15px; border-radius: 15px; border-bottom-left-radius: 0; border: 1px solid #d4af37; margin-bottom: 20px; }
    
    /* Lupa effekti hoshiyasi */
    .magnifier-container { border: 2px solid #c5a059; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. XAVFSIZLIK VA BAZA (SUPABASE)
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Xatolik: Secrets (GEMINI_API_KEY yoki APP_PASSWORD) topilmadi!")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2 style='border:none; text-align:center;'>🏛 ACADEMIC PORTAL</h2>", unsafe_allow_html=True)
        email_in = st.text_input("E-mail Address")
        pwd_in = st.text_input("Access Password", type="password")
        if st.button("ENTER SYSTEM"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Access Denied: Incorrect Password")
    st.stop()

# ==========================================
# 3. AI MOTORINI SOZLASH (DAXLSIZ!)
# ==========================================
genai.configure(api_key=GEMINI_KEY)

# --- AI IDENTITY BRANDING ---
system_instruction = f"""
Siz "Manuscript AI" platformasining professional akademik AI mutaxassisiz. 
Ushbu tizim tadqiqotchi d87809889-dot tomonidan yaratilgan.
Vazifangiz: Qo'lyozmalarni paleografik tahlil qilish, transliteratsiya va akademik tarjima qilish.
Har doim ilmiy va jiddiy ohangda javob bering.
"""

@st.cache_resource
def load_verified_engine():
    # Eng barqaror 1.5 Flash modeli
    try:
        return genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=system_instruction)
    except:
        return genai.GenerativeModel(model_name='gemini-flash-latest', system_instruction=system_instruction)

model = load_verified_engine()

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR
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

def use_credit_atomic(email: str):
    curr = fetch_live_credits(email)
    if curr > 0:
        db.table("profiles").update({"credits": curr - 1}).eq("email", email).execute()
        return True
    return False

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
        else: return Image.open(io.BytesIO(file_content))
    except: return None

# ==========================================
# 5. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h1 style='color:#c5a059; font-size:24px; text-align:center;'>📜 Manuscript AI</h1>", unsafe_allow_html=True)
    st.write(f"👤 **User:** `{st.session_state.u_email}`")
    st.metric("💳 Credits", f"{fetch_live_credits(st.session_state.u_email)}")
    
    st.divider()
    st.markdown("### 🛠 Image Lab")
    brightness = st.slider("Brightness:", 0.5, 2.0, 1.0)
    contrast = st.slider("Contrast:", 0.5, 3.0, 1.2)
    rotate_angle = st.select_slider("Rotate:", options=[0, 90, 180, 270], value=0)
    
    st.divider()
    lang = st.selectbox("Language:", ["Chigatoy", "Persian", "Arabic", "Old Turkish"])
    era = st.selectbox("Script Type:", ["Nasta'liq", "Suls", "Riq'a", "Kufic", "Unknown"])
    
    if st.button("🚪 LOGOUT"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Digital Manuscript Expertise Center")

uploaded_file = st.file_uploader("Upload Manuscript", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Preparing source...'):
            file_bytes = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(file_bytes)
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page_optimized(file_bytes, i, 2.0, True))
                pdf.close()
            else: imgs.append(render_page_optimized(file_bytes, 0, 2.0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    # --- IMAGE LAB PROCESSING ---
    processed_imgs = []
    for img in st.session_state.imgs:
        p_img = img.rotate(rotate_angle, expand=True)
        p_img = ImageEnhance.Brightness(p_img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    if not st.session_state.results:
        cols = st.columns(min(len(processed_imgs), 4))
        for idx, img in enumerate(processed_imgs):
            with cols[idx % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(img, caption=f"Page {idx+1}", width='stretch')
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ START ACADEMIC ANALYSIS'):
        cred = fetch_live_credits(st.session_state.u_email)
        if cred >= len(processed_imgs):
            prompt = f"Siz matnshunos akademiksiz. {lang} va {era} uslubidagi ushbu manbani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
            for i, img in enumerate(processed_imgs):
                with st.status(f"Analyzing Page {i+1}...") as s:
                    try:
                        response = model.generate_content([prompt, img_to_payload(img)])
                        st.session_state.results[i] = response.text
                        use_credit_atomic(st.session_state.u_email)
                        s.update(label=f"Page {i+1} Done!", state="complete")
                    except Exception as e: st.error(f"Error: {e}")
            st.rerun()
        else: st.warning("Not enough credits!")

    # --- RESULTS & CHAT ---
    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        today = datetime.now().strftime("%d.%m.%Y")
        
        for idx, img in enumerate(processed_imgs):
            if idx in st.session_state.results:
                st.markdown(f"### 📖 Page {idx+1}")
                res = st.session_state.results[idx]
                c1, c2 = st.columns([1, 1.2])
                with c1:
                    st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                    st.image(img, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div class='result-box'><b>AI Expert Conclusion:</b><br><br>{res}</div>", unsafe_allow_html=True)
                    
                    st.session_state.results[idx] = st.text_area(f"Refine Analysis ({idx+1}):", value=res, height=350, key=f"ed_{idx}")
                    
                    cite = f"Citation: Manuscript AI (2026). Analysis of page {idx+1} ({lang}). Created by d87809889-dot. Date: {today}."
                    st.markdown(f"<div style='font-size:12px; color:gray; font-style:italic;'>{cite}</div>", unsafe_allow_html=True)
                    
                    final_doc_text += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}\n\n{cite}"

                    # Chat
                    st.markdown("##### 💬 Academic Dialogue")
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user'><b>Q:</b> {ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                    user_q = st.text_input("Ask a question about this page:", key=f"q_in_{idx}")
                    if st.button(f"Ask AI {idx+1}", key=f"btn_{idx}"):
                        if user_q:
                            with st.spinner("Manuscript AI is thinking..."):
                                chat_res = model.generate_content([f"Context: {st.session_state.results[idx]}\nQuestion: {user_q}", img_to_payload(img)])
                                st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                                st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report - Premium Edition', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 DOWNLOAD WORD REPORT", bio.getvalue(), "manuscript_pro_report.docx")
