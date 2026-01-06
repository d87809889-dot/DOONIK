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
    page_title="Manuscript AI - Global Academic v23.0",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- KO'P TILLI INTERFEYS LUG'ATI ---
translations = {
    "uz": {
        "title": "📜 Raqamli Qo'lyozmalar Ekspertiza Markazi",
        "sidebar_title": "📜 MS AI PRO",
        "login_title": "🏛 AKADEMIK KIRISH",
        "credits": "💳 Qolgan kredit",
        "lang_label": "Hujjat tili:",
        "style_label": "Xat uslubi:",
        "upload_label": "Ilmiy manbani yuklang",
        "analyze_btn": "✨ AKADEMIK TAHLILNI BOSHLASH",
        "results_title": "🖋 Ekspertiza Natijalari va Muloqot",
        "comparison_table": "📊 Solishtirish jadvali",
        "chat_label": "💬 Varaq yuzasidan muloqot",
        "citation": "Iqtibos uchun havola",
        "exit_btn": "🚪 TIZIMDAN CHIQISH",
        "table_headers": ["Asl matn", "Transliteratsiya", "Semantik tarjima"]
    },
    "en": {
        "title": "📜 Digital Manuscript Expertise Center",
        "sidebar_title": "📜 MS AI PRO",
        "login_title": "🏛 ACADEMIC LOGIN",
        "credits": "💳 Remaining Credits",
        "lang_label": "Document Language:",
        "style_label": "Script Style:",
        "upload_label": "Upload Scientific Source",
        "analyze_btn": "✨ START ACADEMIC ANALYSIS",
        "results_title": "🖋 Expertise Results & Dialogue",
        "comparison_table": "📊 Comparison Table",
        "chat_label": "💬 Page Discussion",
        "citation": "Academic Citation",
        "exit_btn": "🚪 EXIT SYSTEM",
        "table_headers": ["Original text", "Transliteration", "Semantic translation"]
    },
    "ru": {
        "title": "📜 Центр Цифровой Экспертизы Рукописей",
        "sidebar_title": "📜 MS AI PRO",
        "login_title": "🏛 АКАДЕМИЧЕСКИЙ ВХОД",
        "credits": "💳 Оставшиеся кредиты",
        "lang_label": "Язык документа:",
        "style_label": "Стиль письма:",
        "upload_label": "Загрузить научный источник",
        "analyze_btn": "✨ НАЧАТЬ АКАДЕМИЧЕСКИЙ АНАЛИЗ",
        "results_title": "🖋 Результаты экспертизы и диалог",
        "comparison_table": "📊 Таблица сравнения",
        "chat_label": "💬 Обсуждение страницы",
        "citation": "Академическая цитата",
        "exit_btn": "🚪 ВЫХОД ИЗ СИСТЕМЫ",
        "table_headers": ["Оригинал", "Транслитерация", "Семантический перевод"]
    }
}

# --- PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }
    .result-box { background-color: #ffffff !important; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a; font-size: 17px; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; width: 100%; padding: 10px; border: 1px solid #c5a059; }
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 10px; cursor: zoom-in; }
    .magnifier-container img { transition: transform 0.3s ease; }
    .magnifier-container:hover img { transform: scale(2.5); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. XAVFSIZLIK VA BAZA (SUPABASE)
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""
if "ui_lang" not in st.session_state: st.session_state.ui_lang = "uz"

# Tilni tanlash funksiyasi
def set_lang(lang_code):
    st.session_state.ui_lang = lang_code

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

# Tilni aniqlash
T = translations[st.session_state.ui_lang]

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown(f"<br><br><h2>{T['login_title']}</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Email")
        pwd_in = st.text_input("Password / Parol", type="password")
        if st.button("LOGIN / KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Error! Xato!")
    st.stop()

# ==========================================
# 3. AI MOTORINI SOZLASH (DAXLSIZ!)
# ==========================================
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(model_name='gemini-flash-latest')

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
    st.markdown(f"<h2 style='color:#c5a059; text-align:center;'>{T['sidebar_title']}</h2>", unsafe_allow_html=True)
    
    # TILNI ALMASHTIRISH TUGMALARI
    col_l1, col_l2, col_l3 = st.columns(3)
    if col_l1.button("🇺🇿 UZ"): set_lang("uz"); st.rerun()
    if col_l2.button("🇺🇸 EN"): set_lang("en"); st.rerun()
    if col_l3.button("🇷🇺 RU"): set_lang("ru"); st.rerun()

    st.markdown("---")
    st.write(f"👤 **{st.session_state.u_email}**")
    live_credits = fetch_live_credits(st.session_state.u_email)
    st.metric(T['credits'], f"{live_credits}")
    
    st.divider()
    lang_sel = st.selectbox(T['lang_label'], ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era_sel = st.selectbox(T['style_label'], ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    
    st.divider()
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)
    
    if st.button(T['exit_btn']):
        st.session_state.auth = False
        st.rerun()

st.title(T['title'])
uploaded_file = st.file_uploader(T['upload_label'], type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('...'):
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

    processed_imgs = []
    for img in st.session_state.imgs:
        p_img = ImageEnhance.Brightness(img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    if not st.session_state.results:
        cols = st.columns(min(len(processed_imgs), 4))
        for idx, img in enumerate(processed_imgs):
            with cols[idx % 4]:
                st.markdown(f'<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(img, caption=f"Varaq {idx+1}", width='stretch')
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button(T['analyze_btn']):
        if live_credits >= len(processed_imgs):
            # 🆕 YANGI PROMPT: JADVAL VA TILNI HISOBGA OLGAN HOLDA
            prompt = f"""
            Siz Manuscript AI mutaxassisiz. Hujjat tili: {lang_sel}, uslub: {era_sel}.
            Tahlil natijasini quyidagi tartibda bering:
            1. PALEOGRAFIK TAVSIF.
            2. SOLISHTIRISH JADVALI: Matnni uchta ustunli Markdown jadvalga soling:
               | {T['table_headers'][0]} | {T['table_headers'][1]} | {T['table_headers'][2]} |
            3. ARXAIK LUG'AT JADVALI.
            4. ILMIY XULOSA.
            Javob tili: {st.session_state.ui_lang} (agar tahlil matni bo'lsa, o'zbek tilida).
            """
            for i, img in enumerate(processed_imgs):
                with st.status(f"{i+1}...") as s:
                    try:
                        response = model.generate_content([prompt, img_to_payload(img)])
                        st.session_state.results[i] = response.text
                        use_credit_atomic(st.session_state.u_email)
                        s.update(label="OK!", state="complete")
                    except Exception as e: st.error(f"Error: {e}")
            st.rerun()
        else: st.warning("Credit Error!")

    # --- NATIJALAR ---
    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        today = datetime.now().strftime("%d.%m.%Y")
        
        for idx, img in enumerate(processed_imgs):
            if idx in st.session_state.results:
                st.markdown(f"#### 📖 Varaq {idx+1}")
                res = st.session_state.results[idx]
                c1, c2 = st.columns([1, 1.2])
                with c1:
                    st.markdown(f'<div class="magnifier-container">', unsafe_allow_html=True)
                    st.image(img, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
                    
                    citation = f"{T['citation']}: Manuscript AI (2026). Page {idx+1}. Expert: d87809889-dot. Date: {today}."
                    st.markdown(f"<div class='citation-box'>{citation}</div>", unsafe_allow_html=True)
                    
                    st.session_state.results[idx] = st.text_area(f"Edit ({idx+1}):", value=res, height=350, key=f"ed_{idx}")
                    final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}\n\n{citation}"

                    st.markdown(f"##### {T['chat_label']}")
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                    user_q = st.text_input("?", key=f"q_in_{idx}", label_visibility="collapsed")
                    if st.button(f"Go {idx+1}", key=f"btn_{idx}"):
                        if user_q:
                            with st.spinner("..."):
                                chat_res = model.generate_content([f"Context: {st.session_state.results[idx]}\nQ: {user_q}", img_to_payload(img)])
                                st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                                st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report v23.0', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORD DOWNLOAD", bio.getvalue(), "report.docx")
