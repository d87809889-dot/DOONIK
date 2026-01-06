import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Global Academic Master",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN + LUPA EFFEKTI (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    
    /* RAQAMLI LUPA EFFEKTI */
    .magnifier-container {
        overflow: hidden;
        border: 2px solid #c5a059;
        border-radius: 10px;
        cursor: zoom-in;
    }
    .magnifier-container img {
        transition: transform 0.3s ease;
    }
    .magnifier-container:hover img {
        transform: scale(2.5); /* 2.5 baravar kattalashtirish */
    }

    .result-box { 
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 17px; line-height: 1.7;
    }
    
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 10px !important; border: 1px solid #c5a059; }
    .citation-box { font-size: 13px; color: #5d4037; background: #efebe9; padding: 12px; border-radius: 8px; border: 1px dashed #c5a059; margin-top: 15px; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# Google Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

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
    st.error("Secrets sozlanmagan! Settings > Secrets qismini tekshiring.")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni yozing", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop()

# ==========================================
# 3. AI MOTORINI SOZLASH (DAXLSIZ)
# ==========================================
genai.configure(api_key=GEMINI_KEY)

# --- AI SHAXSIYATI (MANUSCRIPT AI BRANDING) ---
system_instruction = f"""
Siz "Manuscript AI" platformasining professional akademik AI mutaxassisiz. 
Ushbu tizim tadqiqotchi d87809889-dot tomonidan qadimiy qo'lyozmalarni tahlil qilish uchun yaratilgan.
Sizdan kimligingizni so'rashsa, "Men Manuscript AI mutaxassisiman" deb javob bering.
Har doim akademik, jiddiy va aniq tilda ma'lumot bering.
"""

# MOTOR: gemini-flash-latest (Qat'iy daxlsiz saqlandi)
model = genai.GenerativeModel(
    model_name='gemini-flash-latest',
    system_instruction=system_instruction
)

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

def use_credit_atomic(email: str, count: int = 1):
    curr = fetch_live_credits(email)
    if curr >= count:
        db.table("profiles").update({"credits": curr - count}).eq("email", email).execute()
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
        else:
            return Image.open(io.BytesIO(file_content))
    except: return None

# ==========================================
# 5. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.markdown("---")
    st.write(f"👤 **{st.session_state.u_email}**")
    st.metric("💳 Qolgan kredit", f"{fetch_live_credits(st.session_state.u_email)} sahifa")
    
    st.divider()
    # 🆕 1-FUNKSIYA: TAHLIL REJIMLARINI TANLASH
    st.markdown("### 🖋 Tahlil darajasi")
    analysis_mode = st.radio(
        "Yo'nalishni tanlang:",
        ["Diplomatik", "Semantik (Ma'noviy)"],
        help="Diplomatik: harfma-harf ko'chirish. Semantik: umumiy ma'no."
    )
    
    st.divider()
    st.markdown("### 🛠 Restavratsiya paneli")
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)
    rotate_angle = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    
    st.divider()
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertiza Markazi")
uploaded_file = st.file_uploader("Ilmiy manbani yuklang (PDF/Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

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
                for i in range(min(len(pdf), 20)):
                    imgs.append(render_page_optimized(file_bytes, i, 2.0, True))
                pdf.close()
            else:
                imgs.append(render_page_optimized(file_bytes, 0, 2.0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    # --- PDF SAHIFALARINI BOSHQARISH ---
    total_pages = len(st.session_state.imgs)
    selected_indices = st.multiselect("Sahifalarni tanlang:", options=range(total_pages), default=[0], format_func=lambda x: f"{x+1}-sahifa")

    # --- TASVIRLARNI QAYTA ISHLASH ---
    processed_imgs = []
    for img in st.session_state.imgs:
        p_img = img.rotate(rotate_angle, expand=True)
        p_img = ImageEnhance.Brightness(p_img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    if not st.session_state.results:
        st.info("💡 Maslahat: Rasmni kattalashtirish uchun sichqonchani uning ustiga olib boring (Raqamli Lupa).")
        cols = st.columns(min(len(selected_indices), 4) if selected_indices else 1)
        for i, idx in enumerate(selected_indices):
            # 🆕 2-FUNKSIYA: RAQAMLI LUPA INTEGRATSIYASI
            with cols[i % 4]:
                st.markdown(f'<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        cred = fetch_live_credits(st.session_state.u_email)
        if cred >= len(selected_indices):
            # Tahlil rejimiga qarab promptni o'zgartiramiz
            prompt_style = "Diplomatik (harfma-harf transliteratsiya va ilmiy aniqlik)" if analysis_mode == "Diplomatik" else "Semantik (ravon badiiy tarjima va umumiy ma'no)"
            
            prompt = f"""
            Siz Manuscript AI mutaxassisiz. Ushbu {lang} tilidagi va {era} uslubidagi manbani {analysis_mode} usulda tahlil qiling:
            1. PALEOGRAFIK TAVSIF.
            2. {analysis_mode.upper()} TRANSLITERATSIYA VA TARJIMA.
            3. AQLLI LUG'AT: Matndagi 5 ta eng muhim arxaik so'zning izohli jadvali.
            4. ILMIY XULOSA.
            Uslub: {prompt_style}.
            """
            for idx in selected_indices:
                with st.status(f"Varaq {idx+1} ekspertizadan o'tmoqda...") as s:
                    try:
                        response = model.generate_content([prompt, img_to_payload(processed_imgs[idx])])
                        st.session_state.results[idx] = response.text
                        use_credit_atomic(st.session_state.u_email)
                        s.update(label=f"Varaq {idx+1} tayyor!", state="complete")
                    except Exception as e:
                        st.error(f"Xato: {e}")
            st.rerun()
        else:
            st.warning("Kredit yetarli emas!")

    # --- NATIJALAR, TAHRIR VA CHAT ---
    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        today_str = datetime.now().strftime("%d.%m.%Y")
        
        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res = st.session_state.results[idx]
            c1, c2 = st.columns([1, 1.2])
            with c1:
                # Natijalar qismida ham lupa ishlaydi
                st.markdown(f'<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi ({analysis_mode}):</b><br><br>{res}</div>", unsafe_allow_html=True)
                
                # AVTOMATIK IQTIBOS
                citation = f"Iqtibos: Manuscript AI (2026). Varaq {idx+1} {analysis_mode} tahlili. Tizim yaratuvchisi: d87809889-dot. Sana: {today_str}."
                st.markdown(f"<div class='citation-box'>{citation}</div>", unsafe_allow_html=True)
                
                st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"edit_{idx}")
                final_doc_text += f"\n\n--- VARAQ {idx+1} ({analysis_mode}) ---\n{st.session_state.results[idx]}\n\n{citation}"

                # Interaktiv Chat
                st.markdown(f"##### 💬 Varaq {idx+1} bo'yicha savol-javob")
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user' style='color:black;'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai' style='color:black;'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("Manuscript AI o'ylanmoqda..."):
                            chat_res = model.generate_content([f"Hujjat: {st.session_state.results[idx]}\nSavol: {user_q}", img_to_payload(processed_imgs[idx])])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report - Pro Edition', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH (HISOBOT VA LUG'AT BILAN)", bio.getvalue(), "academic_report_pro.docx")
