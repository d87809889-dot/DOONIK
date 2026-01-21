import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from supabase import create_client, Client
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI Platinum - Scientific Edition",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    /* Streamlit reklamalarini yashirish, lekin menyu tugmasini saqlash */
    footer {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    
    header[data-testid="stHeader"] {
        background: rgba(0,0,0,0) !important;
        visibility: visible !important;
    }

    /* Mobil qurilmalarda sidebar ustunligini to'g'irlash */
    button[data-testid="stSidebarCollapseButton"] {
        background-color: #0c1421 !important;
        color: #c5a059 !important;
        border: 1px solid #c5a059 !important;
    }

    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    
    /* Tahlil natijalari kartasi */
    .result-box { 
        background-color: #ffffff; padding: 30px !important; border-radius: 15px !important; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        color: #000; font-size: 18px; line-height: 1.9;
    }
    
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; font-size: 17px; }
    .chat-user { background-color: #e2e8f0; color: #000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 12px !important; border: 1px solid #c5a059; height: 55px; }
    
    /* Magnifier Image */
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 15px; cursor: zoom-in; }
    .magnifier-container img:hover { transform: scale(2.2); transition: transform 0.3s ease; }
    
    .methodology-note { font-size: 14px; color: #5d4037; background: #e7d8c1; padding: 15px; border-radius: 8px; border: 1px dashed #0c1421; margin-top: 20px; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CORE SERVICES (SUPABASE & AI) ---
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

try:
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except Exception as e:
    st.error("Xatolik: Streamlit Secrets topilmadi! Iltimos Settings panelini tekshiring.")
    st.stop()

# --- 3. AUTH SYSTEM ---
if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA PORTALI</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Email (Hisob)")
        pwd_in = st.text_input("Maxfiy parol", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Xato!")
    st.stop()

# --- 4. AI ENGINE (FIXED 404 AND SAFETY) ---
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_expert_engine():
    """Googlening yangi Stable tizimidagi modelni yuklaydi (404 xatosi yechimi)"""
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    instruction = "Siz Manuscript AI tizimining ilmiy ekspertisiz. Vazifangiz manbalarni Lachmann metodologiyasi asosida filologik tahlil qilish."
    
    # Models ro'yxatini tekshirish
    available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    targets = ['models/gemini-1.5-flash', 'models/gemini-flash-latest', 'models/gemini-1.5-pro']
    
    chosen = next((t for t in targets if t in available), 'models/gemini-1.5-flash')
    return genai.GenerativeModel(model_name=chosen, system_instruction=instruction, safety_settings=safety)

ai_expert = load_expert_engine()

# --- 5. YORDAMCHI FUNKSIYALAR ---
def enhance_manuscript_image(img: Image.Image):
    """Rasmni tahlil uchun raqamli restavratsiya qilish"""
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(2.6)
    img = ImageEnhance.Sharpness(img).enhance(2.2)
    return img

def img_to_png_bytes(img: Image.Image):
    """PNG lossless formatda yuborish (Xatoshikdan asraydi)"""
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return {"mime_type": "image/png", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_credits(email: str):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

def use_credit(email: str, count: int):
    curr = fetch_credits(email)
    if curr >= count:
        db.table("profiles").update({"credits": curr - count}).eq("email", email).execute()
        return True
    return False

@st.cache_data(show_spinner=False)
def render_scientific_page(file_content, page_idx, scale, is_pdf):
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            img = pdf[page_idx].render(scale=scale).to_pil()
            pdf.close()
            return img
        return Image.open(io.BytesIO(file_content))
    except: return None

# ==========================================
# 6. ASOSIY ILOVA INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
    current_credits = fetch_credits(st.session_state.u_email)
    st.metric("💳 Tadqiqot limiti", f"{current_credits} sahifa")
    st.divider()
    
    lang_opt = st.selectbox("Hujjat tili:", ["Chig'atoy (Eski o'zbek)", "Fors (Klassik)", "Arab (Ilmiy)", "Eski Turkiy"])
    style_opt = st.selectbox("Paleografik uslub:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Devoniy", "Noma'lum"])
    
    st.divider()
    st.markdown("### 🛠 Tasvir Restavratsiyasi")
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Siyoh o'tkirligi:", 0.5, 3.0, 1.3)
    rot_val = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    
    if st.button("🚪 CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Matnshunoslik va Ekspertiza Markazi")
file = st.file_uploader("Ilmiy manbani yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'session_imgs' not in st.session_state: st.session_state.session_imgs = []
if 'academic_results' not in st.session_state: st.session_state.academic_results = {}
if 'page_chats' not in st.session_state: st.session_state.page_chats = {}

if file:
    if st.session_state.get('last_filename') != file.name:
        with st.spinner('Manba tayyorlanmoqda...'):
            raw_bytes = file.getvalue()
            imgs = []
            if file.type == "application/pdf":
                pdf = pdfium.PdfDocument(raw_bytes)
                for i in range(min(len(pdf), 20)): # Max 20 pages limit
                    imgs.append(render_scientific_page(raw_bytes, i, 3.5, True))
                pdf.close()
            else: imgs.append(render_scientific_page(raw_bytes, 0, 1.0, False))
            
            st.session_state.session_imgs = imgs
            st.session_state.last_filename = file.name
            st.session_state.academic_results, st.session_state.page_chats = {}, {}
            gc.collect()

    # Pre-processing apply
    final_processed_imgs = []
    for img in st.session_state.session_imgs:
        temp = img.rotate(rot_val, expand=True)
        temp = ImageEnhance.Brightness(temp).enhance(brightness)
        temp = ImageEnhance.Contrast(temp).enhance(contrast)
        final_processed_imgs.append(temp)

    # PAGE SELECTION
    selected_indices = st.multiselect("Varaqlarni tanlang:", range(len(final_processed_imgs)), default=[0], format_func=lambda x: f"Varaq {x+1}")

    if not st.session_state.academic_results:
        # BUG FIX: width=None olib tashlandi, use_container_width=True qo'shildi
        st.info("💡 Maslahat: Harflarni aniq ko'rish uchun sichqonchani rasm ustiga olib boring (Zoom).")
        cols = st.columns(min(len(selected_indices), 4) if selected_indices else 1)
        for i, idx in enumerate(selected_indices):
            with cols[i % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(final_processed_imgs[idx], caption=f"Varaq {idx+1}", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ CHUQUR AKADEMIK EKSPERTIZANI BOSHLASH'):
        if current_credits >= len(selected_indices):
            prompt = f"""
            Ushbu {lang_opt} manbasini ({style_opt} xati) tahlil qiling. Vazifalar:
            I. SEMANTIK TARJIMA: Matnni zamonaviy o'zbek tiliga ravon o'giring.
            II. FILOLOGIK EKSPERTIZA: 
               1. Raw transcription. 2. Diplomatic transliteration (variantlar foiz % bilan).
               3. Paleografik va tarixiy sharhlar.
            """
            for idx in selected_indices:
                with st.status(f"Varaq {idx+1} ekspertizadan o'tkazilmoqda...") as s:
                    try:
                        # Auto-enhance for AI
                        ai_img = enhance_image_for_ai(final_processed_imgs[idx])
                        resp = ai_expert.generate_content([prompt, img_to_png_bytes(ai_img)])
                        if resp.candidates and resp.candidates[0].content.parts:
                            st.session_state.academic_results[idx] = resp.text
                            use_credit(st.session_state.u_email, 1)
                            s.update(label=f"Varaq {idx+1} yakunlandi!", state="complete")
                        else: st.error("AI javobi xavfsizlik filtri tomonidan bloklandi.")
                    except Exception as e: st.error(f"Xato: {e}")
            st.rerun()
        else: st.warning("Hisobda yetarli limit mavjud emas!")

    # --- RESULTS SECTION ---
    if st.session_state.academic_results:
        st.divider()
        report_content = ""
        for idx in sorted(st.session_state.academic_results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(final_processed_imgs[idx], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("<div class='methodology-note'>Metodologiya: Lachmann-transkripsiya va Lossless PNG rendering.</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='result-box'>{st.session_state.academic_results[idx]}</div>", unsafe_allow_html=True)
                st.session_state.academic_results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=st.session_state.academic_results[idx], height=350, key=f"edit_{idx}")
                report_content += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.academic_results[idx]}"
                
                # Per-page Chat
                st.markdown("##### 💬 Varaq yuzasidan ilmiy muloqot")
                st.session_state.page_chats.setdefault(idx, [])
                for chat in st.session_state.page_chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>S:</b> {chat['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>AI:</b> {chat['a']}</div>", unsafe_allow_html=True)

                u_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if u_q:
                        with st.spinner("O'ylanmoqda..."):
                            ch_resp = ai_expert.generate_content([f"Hujjat: {st.session_state.academic_results[idx]}\nSavol: {u_q}", img_to_png_bytes(final_processed_imgs[idx])])
                            st.session_state.page_chats[idx].append({"q": u_q, "a": ch_resp.text}); st.rerun()
                st.markdown("---")

        if report_content:
            doc = Document(); doc.add_paragraph(report_content); bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORD HISOBOTINI YUKLAB OLISH", bio.getvalue(), "expert_report.docx")

gc.collect()
