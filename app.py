# File: app_improved.py

import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, base64
from datetime import datetime
from docx import Document
from supabase import create_client
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Global Academic Master",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="auto"
)

# --- ENHANCED PROFESSIONAL UI (CSS) ---
st.markdown("""
    <style>
    /* === SYSTEM OVERRIDES === */
    footer {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}

    header[data-testid='stHeader'] {
        background: rgba(0,0,0,0) !important;
        visibility: visible !important;
    }

    button[data-testid='stSidebarCollapseButton'] {
        background-color: #0c1421 !important;
        color: #c5a059 !important;
        border: 1px solid #c5a059 !important;
        position: fixed !important;
        z-index: 1000001 !important;
        transition: all 0.3s ease !important;
    }
    
    button[data-testid='stSidebarCollapseButton']:hover {
        background-color: #1e3a8a !important;
        transform: scale(1.05);
    }

    /* === MAIN LAYOUT === */
    .main { 
        background: linear-gradient(135deg, #f4ecd8 0%, #fdfaf1 100%) !important;
        color: #1a1a1a !important;
        font-family: 'Times New Roman', serif;
        padding: 2rem 1rem;
    }
    
    /* === TYPOGRAPHY === */
    h1, h2, h3, h4 { 
        color: #0c1421 !important;
        font-family: 'Georgia', serif;
        border-bottom: 2px solid #c5a059;
        text-align: center;
        padding-bottom: 12px;
        margin-bottom: 20px;
    }
    
    h1 {
        font-size: clamp(1.8rem, 4vw, 2.5rem) !important;
        margin-top: 0;
    }
    
    h2 {
        font-size: clamp(1.4rem, 3vw, 2rem) !important;
    }
    
    h4 {
        font-size: clamp(1.1rem, 2.5vw, 1.4rem) !important;
    }

    /* === BUTTONS === */
    .stButton>button { 
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important;
        font-weight: bold !important;
        width: 100% !important;
        padding: 14px 20px !important;
        border: 2px solid #c5a059 !important;
        border-radius: 8px !important;
        height: auto !important;
        min-height: 50px !important;
        font-size: 16px !important;
        cursor: pointer !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }
    
    .stButton>button:hover { 
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 20px rgba(197,160,89,0.4) !important;
        border-color: #d4af37 !important;
        background: linear-gradient(135deg, #1e3a8a 0%, #0c1421 100%) !important;
    }
    
    .stButton>button:active {
        transform: translateY(0) !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
    }

    /* === RESULT BOX === */
    .result-box { 
        background: linear-gradient(135deg, #ffffff 0%, #fefefe 100%) !important;
        padding: 28px !important;
        border-radius: 14px !important;
        border-left: 12px solid #c5a059 !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.12) !important;
        color: #1a1a1a !important;
        font-size: 17px;
        line-height: 1.8;
        margin-bottom: 20px;
        animation: fadeInUp 0.6s ease-out;
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* === FORM INPUTS === */
    .stTextInput>div>div>input,
    .stTextArea textarea {
        background-color: #fdfaf1 !important;
        color: #000000 !important;
        border: 2px solid #c5a059 !important;
        border-radius: 8px !important;
        padding: 12px !important;
        font-family: 'Courier New', monospace !important;
        transition: all 0.3s ease !important;
        font-size: 15px !important;
    }
    
    .stTextInput>div>div>input:focus,
    .stTextArea textarea:focus {
        border-color: #d4af37 !important;
        box-shadow: 0 0 0 3px rgba(197,160,89,0.2) !important;
        outline: none !important;
    }

    /* === CHAT BUBBLES === */
    .chat-user {
        background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
        color: #000000 !important;
        padding: 16px 20px;
        border-radius: 18px 18px 4px 18px;
        border-left: 5px solid #1e3a8a;
        margin-bottom: 12px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.08);
        animation: slideInLeft 0.4s ease-out;
    }
    
    .chat-ai {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        color: #1a1a1a !important;
        padding: 16px 20px;
        border-radius: 18px 18px 18px 4px;
        border-left: 5px solid #c5a059;
        margin-bottom: 16px;
        box-shadow: 0 3px 12px rgba(212,175,55,0.15);
        animation: slideInRight 0.4s ease-out;
    }
    
    @keyframes slideInLeft {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }
    
    @keyframes slideInRight {
        from { opacity: 0; transform: translateX(20px); }
        to { opacity: 1; transform: translateX(0); }
    }

    /* === SIDEBAR === */
    section[data-testid='stSidebar'] {
        background: linear-gradient(180deg, #0c1421 0%, #1a2332 100%) !important;
        border-right: 3px solid #c5a059 !important;
    }
    
    section[data-testid='stSidebar'] .stMarkdown {
        color: #fdfaf1 !important;
    }
    
    section[data-testid='stSidebar'] [data-testid='stMetricValue'] {
        color: #c5a059 !important;
        font-size: 24px !important;
        font-weight: bold !important;
    }

    /* === IMAGE MAGNIFIER === */
    .magnifier-container {
        overflow: hidden;
        border: 3px solid #c5a059;
        border-radius: 12px;
        cursor: zoom-in;
        background: white;
        padding: 8px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .magnifier-container:hover {
        box-shadow: 0 8px 25px rgba(197,160,89,0.3);
        border-color: #d4af37;
    }
    
    .magnifier-container img {
        transition: transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    }
    
    .magnifier-container img:hover {
        transform: scale(1.8);
    }

    /* === CITATION BOX === */
    .citation-box {
        font-size: 13px;
        color: #5d4037;
        background: linear-gradient(135deg, #efebe9 0%, #f5f5f5 100%);
        padding: 14px 18px;
        border-radius: 10px;
        border: 1px dashed #c5a059;
        margin-top: 18px;
        font-style: italic;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }

    /* === FILE UPLOADER === */
    [data-testid='stFileUploader'] {
        background: white;
        border: 3px dashed #c5a059;
        border-radius: 12px;
        padding: 30px;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    [data-testid='stFileUploader']:hover {
        border-color: #d4af37;
        background: #fdfaf1;
        box-shadow: 0 5px 15px rgba(197,160,89,0.1);
    }

    /* === DIVIDER === */
    hr {
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, #c5a059, transparent);
        margin: 30px 0;
    }

    /* === EMPTY STATE === */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        background: white;
        border-radius: 16px;
        border: 3px dashed #c5a059;
        margin: 40px 0;
        box-shadow: 0 5px 20px rgba(0,0,0,0.08);
    }
    
    .empty-state h3 {
        color: #0c1421;
        border: none;
        margin-bottom: 10px;
    }

    /* === LOGIN CARD === */
    .login-card {
        background: white;
        padding: 50px 40px;
        border-radius: 20px;
        box-shadow: 0 15px 50px rgba(0,0,0,0.15);
        border: 2px solid #c5a059;
        animation: fadeInUp 0.6s ease-out;
    }
    
    .hero-title {
        font-size: clamp(2rem, 5vw, 3rem);
        color: #0c1421;
        margin-bottom: 15px;
        font-weight: bold;
        text-align: center;
    }
    
    .hero-subtitle {
        font-size: clamp(1rem, 2vw, 1.2rem);
        color: #5d4037;
        text-align: center;
        margin-bottom: 30px;
        line-height: 1.6;
    }

    /* === CREDIT PROGRESS BAR === */
    .credit-bar-container {
        background: rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 4px;
        margin: 15px 0;
        border: 1px solid #c5a059;
    }
    
    .credit-bar {
        height: 10px;
        background: linear-gradient(90deg, #c5a059, #d4af37);
        border-radius: 8px;
        transition: width 0.5s ease;
        box-shadow: 0 0 10px rgba(197,160,89,0.5);
    }

    /* === SECTION HEADER === */
    .section-header {
        color: #c5a059 !important;
        font-size: 16px;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 2px solid rgba(197,160,89,0.3);
    }

    /* === RESPONSIVE === */
    @media (max-width: 768px) {
        .main {
            padding: 1rem 0.5rem;
        }
        
        h1 {
            font-size: 1.5rem !important;
        }
        
        .result-box {
            padding: 20px !important;
            font-size: 15px !important;
        }
        
        .stButton>button {
            font-size: 14px !important;
            padding: 12px 16px !important;
        }
        
        .login-card {
            padding: 30px 20px;
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. CORE SERVICES (SUPABASE & AI) ---
if "auth" not in st.session_state:
    st.session_state.auth = False
if "u_email" not in st.session_state:
    st.session_state.u_email = ""

try:
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

if not st.session_state.auth:
    # === ENHANCED LOGIN PAGE ===
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.markdown("""
            <div class='login-card'>
                <div class='hero-title'>🏛 Manuscript AI</div>
                <div class='hero-subtitle'>
                    Qadimiy qo'lyozmalarni raqamli tahlil qilish va transliteratsiya 
                    qilish uchun sun'iy intellekt asosidagi akademik platforma
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h2 style='margin-top:30px;'>🔐 Tizimga Kirish</h2>", unsafe_allow_html=True)
        
        email_in = st.text_input("📧 Email manzili", placeholder="example@domain.com")
        pwd_in = st.text_input("🔑 Parol", type="password", placeholder="Parolingizni kiriting")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("✨ TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth = True
                st.session_state.u_email = email_in
                st.success("✅ Muvaffaqiyatli kirdingiz!")
                st.rerun()
            else:
                st.error("❌ Parol noto'g'ri! Iltimos, qaytadan urinib ko'ring.")
    st.stop()

# --- AI ENGINE (UNCHANGED - DO NOT MODIFY) ---
genai.configure(api_key=GEMINI_KEY)
system_instruction = "Siz Manuscript AI mutaxassisiz. Tadqiqotchi d87809889-dot muallifligida ilmiy tahlillar qilasiz."
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}
model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    system_instruction=system_instruction,
    safety_settings=safety_settings
)

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR (UNCHANGED)
# ==========================================
def enhance_image_for_ai(img: Image.Image):
    """Rasmni AI tahlili uchun optimallashtirish (XATO TUZATILDI)"""
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(2.8)
    img = ImageEnhance.Sharpness(img).enhance(2.5)
    return img

def img_to_png_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return {"mime_type": "image/png", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_live_credits(email: str):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except:
        return 0

def use_credit_atomic(email: str, count: int = 1):
    curr = fetch_live_credits(email)
    if curr >= count:
        db.table("profiles").update({"credits": curr - count}).eq("email", email).execute()
        return True
    return False

@st.cache_data(show_spinner=False)
def render_page(file_content, page_idx, scale, is_pdf):
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            img = pdf[page_idx].render(scale=scale).to_pil()
            pdf.close()
            return img
        return Image.open(io.BytesIO(file_content))
    except:
        return None

# ==========================================
# 4. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center; border:none;'>📜 Manuscript AI</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center; color:#fdfaf1; font-size:14px;'>👤 <b>{st.session_state.u_email}</b></p>", unsafe_allow_html=True)
    
    current_credits = fetch_live_credits(st.session_state.u_email)
    
    # Enhanced credit display with progress bar
    st.metric("💳 Mavjud Kredit", f"{current_credits} sahifa")
    credit_percent = min((current_credits / 100) * 100, 100) if current_credits <= 100 else 100
    st.markdown(f"""
        <div class='credit-bar-container'>
            <div class='credit-bar' style='width:{credit_percent}%'></div>
        </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Section: Til va Xat
    st.markdown("<p class='section-header'>🌍 Til va Xat Tanlash</p>", unsafe_allow_html=True)
    lang = st.selectbox("Qo'lyozma tili", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat turi", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    
    st.divider()
    
    # Section: Rasm Sozlamalari
    st.markdown("<p class='section-header'>🎨 Rasm Sozlamalari</p>", unsafe_allow_html=True)
    br = st.slider("☀️ Yorqinlik", 0.5, 2.0, 1.0, 0.1)
    ct = st.slider("🎭 Kontrast", 0.5, 3.0, 1.3, 0.1)
    rot = st.select_slider("🔄 Aylantirish", options=[0, 90, 180, 270], value=0)

    st.divider()
    
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

# === MAIN CONTENT AREA ===
st.markdown("<h1>📜 Raqamli Qo'lyozmalar Ekspertizasi</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#5d4037; font-size:18px; margin-bottom:30px;'>Sun'iy intellekt yordamida qadimiy matnlarni tahlil qiling va transliteratsiya qiling</p>", unsafe_allow_html=True)

file = st.file_uploader("📤 Qo'lyozma faylini yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="visible")

if "imgs" not in st.session_state: st.session_state.imgs = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}

if not file:
    # === EMPTY STATE ===
    st.markdown("""
        <div class='empty-state'>
            <h3 style='font-size:3rem; margin-bottom:20px;'>📜</h3>
            <h3>Qo'lyozma yuklang</h3>
            <p style='color:#666; font-size:16px; line-height:1.6;'>
                PDF, PNG, JPG yoki JPEG formatidagi fayllarni yuklashingiz mumkin<br>
                Maksimal 15 sahifagacha tahlil qilish imkoniyati
            </p>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

if file:
    if st.session_state.get("last_fn") != file.name:
        with st.spinner("📂 Fayl tayyorlanmoqda..."):
            data = file.getvalue()
            imgs = []
            if file.type == "application/pdf":
                pdf = pdfium.PdfDocument(data)
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page(data, i, 3.5, True))
                pdf.close()
            else:
                imgs.append(render_page(data, 0, 1.0, False))

            st.session_state.imgs = imgs
            st.session_state.last_fn = file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    processed = []
    for im in st.session_state.imgs:
        p = im.rotate(rot, expand=True)
        p = ImageEnhance.Brightness(p).enhance(br)
        p = ImageEnhance.Contrast(p).enhance(ct)
        processed.append(p)

    st.markdown("<h3 style='margin-top:30px;'>📑 Varaqlarni Tanlang</h3>", unsafe_allow_html=True)
    indices = st.multiselect(
        "Tahlil qilish uchun varaqlarni belgilang:",
        range(len(processed)),
        default=[0],
        format_func=lambda x: f"📄 Varaq {x+1}"
    )

    if not st.session_state.results and indices:
        st.markdown("<h3 style='margin-top:30px;'>🖼 Tanlangan Varaqlar</h3>", unsafe_allow_html=True)
        cols = st.columns(min(len(indices), 3))
        for i, idx in enumerate(indices):
            with cols[i % 3]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[idx], caption=f"Varaq {idx+1}", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
        if current_credits >= len(indices):
            prompt = f"Academic analysis of {lang} manuscript ({era}). 1.Transliteration 2.Translation 3.Expert Notes."
            for idx in indices:
                with st.status(f"🔍 Varaq {idx+1} ekspertizadan o'tkazilmoqda..."):
                    try:
                        ai_img = enhance_image_for_ai(processed[idx])
                        resp = model.generate_content([prompt, img_to_png_payload(ai_img)])

                        if resp.candidates and resp.candidates[0].content.parts:
                            st.session_state.results[idx] = resp.text
                            use_credit_atomic(st.session_state.u_email)
                            st.success(f"✅ Varaq {idx+1} muvaffaqiyatli tahlil qilindi")
                        else:
                            st.error("⚠️ AI javob berish imkoniyatiga ega emas")
                    except Exception as e:
                        st.error(f"❌ Xatolik yuz berdi: {e}")
            st.rerun()
        else:
            st.warning(f"⚠️ Kredit yetarli emas! Sizda {current_credits} sahifa kredit bor, {len(indices)} sahifa tahlil qilish uchun yetarli emas.")

    if st.session_state.results:
        st.divider()
        st.markdown("<h2>📊 Tahlil Natijalari</h2>", unsafe_allow_html=True)
        
        final_text = ""
        today = datetime.now().strftime("%d.%m.%Y")

        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"<h4 style='margin-top:40px;'>📖 Varaq {idx+1} - Tahlil</h4>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 1.3])

            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[idx], use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with c2:
                st.markdown(f"<div class='result-box'>{st.session_state.results[idx]}</div>", unsafe_allow_html=True)
                cite = f"Iqtibos: Manuscript AI (2026). Varaq {idx+1} tahlili ({lang}). Ekspert: d87809889-dot. Sana: {today}."
                st.markdown(f"<div class='citation-box'>📌 {cite}</div>", unsafe_allow_html=True)

                st.markdown(f"<p style='color:#5d4037; font-weight:bold; margin-top:20px; margin-bottom:8px;'>✏️ Tahrirlash:</p>", unsafe_allow_html=True)
                st.session_state.results[idx] = st.text_area(
                    f"Natijani tahrirlash",
                    value=st.session_state.results[idx],
                    height=350,
                    key=f"ed_{idx}",
                    label_visibility="collapsed"
                )

                final_text += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}\n\n{cite}"

                # === CHAT INTERFACE ===
                st.markdown(f"<p style='color:#5d4037; font-weight:bold; margin-top:25px; margin-bottom:12px;'>💬 Savollar va Javoblar:</p>", unsafe_allow_html=True)
                
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>Savol:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>Javob:</b> {ch['a']}</div>", unsafe_allow_html=True)

                q = st.text_input("🤔 Savolingizni yozing:", key=f"q_in_{idx}", placeholder="Matn haqida savol bering...")
                if st.button(f"📤 So'rash", key=f"btn_{idx}"):
                    if q:
                        with st.spinner("🤖 AI javob tayyorlayapti..."):
                            chat_res = model.generate_content([
                                f"Hujjat: {st.session_state.results[idx]}\nQ: {q}",
                                img_to_png_payload(processed[idx])
                            ])
                            st.session_state.chats[idx].append({"q": q, "a": chat_res.text})
                            st.rerun()
                    else:
                        st.warning("⚠️ Iltimos, avval savol yozing!")

        if final_text:
            st.divider()
            doc = Document()
            doc.add_paragraph(final_text)
            bio = io.BytesIO()
            doc.save(bio)

            st.download_button(
                "📥 WORD FORMATDA YUKLAB OLISH",
                bio.getvalue(),
                "manuscript_ai_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

gc.collect()
