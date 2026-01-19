import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, base64
from docx import Document
from supabase import create_client

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================
# THEME SWITCH (ALTERNATIV)
# =========================
THEME = "DARK_GOLD"  # "DARK_GOLD" | "PARCHMENT" | "MIDNIGHT"

THEMES = {
    "DARK_GOLD": {
        "app_bg": "#0b1220",
        "surface": "#111a2e",
        "sidebar_bg": "#0c1421",
        "text": "#e9eefb",
        "muted": "#b9c2d4",
        "gold": "#c5a059",
        "gold2": "#d4af37",
        "card": "#ffffff",
        "card_text": "#111827",
    },
    "PARCHMENT": {
        "app_bg": "#f4ecd8",
        "surface": "#fff7e6",
        "sidebar_bg": "#0c1421",
        "text": "#0c1421",
        "muted": "#3b4252",
        "gold": "#b98a2c",
        "gold2": "#c5a059",
        "card": "#ffffff",
        "card_text": "#111827",
    },
    "MIDNIGHT": {
        "app_bg": "#070b16",
        "surface": "#0e1630",
        "sidebar_bg": "#0b1020",
        "text": "#e6ecff",
        "muted": "#aab6d6",
        "gold": "#5aa6ff",
        "gold2": "#7cc4ff",
        "card": "#ffffff",
        "card_text": "#111827",
    },
}

C = THEMES.get(THEME, THEMES["DARK_GOLD"])

# ==========================================
# 1.1 PROFESSIONAL UI (contrast + no white gap + scrollable result + mobile tabs)
# ==========================================
st.markdown(f"""
<style>
:root {{
  --app-bg: {C["app_bg"]};
  --surface: {C["surface"]};
  --sidebar-bg: {C["sidebar_bg"]};
  --text: {C["text"]};
  --muted: {C["muted"]};
  --gold: {C["gold"]};
  --gold2: {C["gold2"]};
  --card: {C["card"]};
  --card-text: {C["card_text"]};
}}

html, body {{
  background: var(--app-bg) !important;
  margin: 0 !important;
  padding: 0 !important;
}}
.stApp, div[data-testid="stAppViewContainer"] {{
  background: var(--app-bg) !important;
  min-height: 100vh !important;
}}
div[data-testid="stAppViewContainer"] .main .block-container {{
  padding-top: 3.25rem !important;
  padding-bottom: 1.25rem !important;
}}

footer {{visibility: hidden !important;}}
.stAppDeployButton {{display:none !important;}}
#stDecoration {{display:none !important;}}
header[data-testid="stHeader"] {{ background: rgba(0,0,0,0) !important; }}

section[data-testid="stSidebar"] {{
  background: var(--sidebar-bg) !important;
  border-right: 2px solid var(--gold) !important;
}}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span {{
  color: var(--text) !important;
}}
section[data-testid="stSidebar"] .stCaption {{
  color: var(--muted) !important;
}}

h1, h2, h3, h4 {{
  color: var(--gold) !important;
  font-family: 'Georgia', serif;
  border-bottom: 2px solid var(--gold) !important;
  padding-bottom: 8px !important;
  text-align: center !important;
}}
.stMarkdown p {{ color: var(--muted) !important; }}

.stButton>button {{
  background: linear-gradient(135deg, var(--sidebar-bg) 0%, #1e3a8a 100%) !important;
  color: var(--gold) !important;
  font-weight: 800 !important;
  width: 100% !important;
  padding: 11px 12px !important;
  border: 1px solid var(--gold) !important;
  border-radius: 12px !important;
  box-shadow: 0 10px 22px rgba(0,0,0,0.25) !important;
}}
.stButton>button:hover {{
  transform: translateY(-1px);
  filter: brightness(1.05);
}}

.stTextInput input, .stSelectbox select, .stTextArea textarea {{
  background-color: rgba(255,255,255,0.06) !important;
  color: var(--text) !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}

.result-box {{
  background-color: var(--card) !important;
  padding: 18px !important;
  border-radius: 16px !important;
  border-left: 10px solid var(--gold) !important;
  box-shadow: 0 10px 30px rgba(0,0,0,0.18) !important;
  color: var(--card-text) !important;
  font-size: 16px;
  line-height: 1.75;

  /* ✅ SCROLL: matn uzun bo'lsa faqat shu joy scroll bo'ladi */
  max-height: 520px;
  overflow-y: auto;
}}

.premium-alert {{
  background: rgba(255,243,224,1);
  border: 1px solid #ffb74d;
  padding: 12px;
  border-radius: 12px;
  text-align: center;
  color: #e65100;
  font-weight: 800;
  margin-bottom: 12px;
}}

.chat-user {{
  background-color: #e2e8f0; color: #000; padding: 10px; border-radius: 10px;
  border-left: 5px solid #1e3a8a; margin-bottom: 6px;
}}
.chat-ai {{
  background-color: #ffffff; color: #1a1a1a; padding: 10px; border-radius: 10px;
  border: 1px solid #d4af37; margin-bottom: 14px;
}}

/* ✅ IMAGE: cho'zilmasin, proportsiya saqlansin */
.sticky-preview {{
  position: sticky;
  top: 4.6rem;
  border-radius: 14px;
  border: 2px solid var(--gold);
  overflow: hidden;
  box-shadow: 0 14px 35px rgba(0,0,0,0.22);
  background: rgba(0,0,0,0.15);

  max-height: 520px;
}}
.sticky-preview img {{
  width: 100%;
  height: 520px;           /* rasm blok balandligi bir xil */
  object-fit: contain;     /* ✅ cho'zilmaydi */
  display: block;
  transition: transform .25s ease;
}}
.sticky-preview:hover img {{
  transform: scale(1.6);
  transform-origin: center;
  cursor: zoom-in;
}}

/* ✅ Desktop/Mobile layout toggles */
.desktop-only {{ display: block; }}
.mobile-only {{ display: none; }}

/* Mobil optimizatsiya */
@media (max-width: 768px) {{
  .desktop-only {{ display: none; }}
  .mobile-only {{ display: block; }}

  div[data-testid="stAppViewContainer"] .main .block-container {{
    padding-top: 3.5rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }}

  .result-box {{
    max-height: 58vh;   /* telefonda qulay */
  }}

  .sticky-preview {{
    position: relative;
    top: 0;
    max-height: 48vh;
  }}
  .sticky-preview img {{
    height: 48vh;
  }}
}}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CORE SERVICES (SUPABASE & AI MOTOR)
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

# ✅ MODELNI O'ZGARTIRMAYMIZ (sizning talabingiz)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(model_name='gemini-flash-latest')

# --- SESSYA HOLATI ---
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = "Mehmon"

# ==========================================
# 3. SIDEBAR (LOGIN + PARAMETRLAR)
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)

    if not st.session_state.auth:
        st.markdown("### 🔑 Tizimga kirish")
        st.caption("Kreditlaringizdan foydalanish uchun kiring.")
        email_in = st.text_input("Email", placeholder="example@mail.com")
        pwd_in = st.text_input("Parol", type="password", placeholder="****")
        if st.button("KIRISH"):
            if pwd_in == st.secrets["APP_PASSWORD"]:
                st.session_state.auth = True
                st.session_state.u_email = email_in
                st.rerun()
            else:
                st.error("Xato!")
    else:
        st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
        try:
            res = db.table("profiles").select("credits").eq("email", st.session_state.u_email).single().execute()
            live_credits = res.data["credits"] if res.data else 0
        except:
            live_credits = 0
        st.metric("💳 Kreditlar", f"{live_credits} sahifa")
        if st.button("🚪 TIZIMDAN CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = "Mehmon"
            st.rerun()

    st.divider()
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)

# ==========================================
# 4. ASOSIY INTERFEYS
# ==========================================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qadimiy hujjatlarni yuklang va AI yordamida tahlil qiling.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Faylni yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

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
                for i in range(min(len(pdf), 20)):
                    imgs.append(pdf[i].render(scale=2.0).to_pil())
                pdf.close()
            else:
                imgs.append(Image.open(io.BytesIO(file_bytes)))

            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    processed_imgs = []
    for img in st.session_state.imgs:
        img = ImageOps.exif_transpose(img)  # ✅ rotation/exif fix
        p_img = ImageEnhance.Brightness(img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    selected_indices = st.multiselect(
        "Sahifalarni tanlang:",
        options=range(len(processed_imgs)),
        default=[0],
        format_func=lambda x: f"{x+1}-sahifa"
    )

    if not st.session_state.results and selected_indices:
        cols = st.columns(min(len(selected_indices), 4))
        for i, idx in enumerate(selected_indices):
            with cols[i % min(len(cols), 4)]:
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        prompt = f"Siz Manuscript AI mutaxassisiz. {lang} va {era} uslubidagi manbani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Arxaik lug'at. 5.Izoh."
        for idx in selected_indices:
            with st.status(f"Sahifa {idx+1}...") as s:
                try:
                    buf = io.BytesIO()
                    processed_imgs[idx].save(buf, format="JPEG", quality=90)
                    payload = {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode("utf-8")}
                    response = model.generate_content([prompt, payload])
                    st.session_state.results[idx] = response.text

                    if st.session_state.auth:
                        try:
                            res = db.table("profiles").select("credits").eq("email", st.session_state.u_email).single().execute()
                            live_credits = res.data["credits"] if res.data else 0
                        except:
                            live_credits = 0
                        db.table("profiles").update({"credits": max(live_credits - 1, 0)}).eq("email", st.session_state.u_email).execute()

                    s.update(label="Tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato: {e}")
        st.rerun()

    # --- NATIJALAR (✅ ko'p sahifali PDF uchun expander) ---
    if st.session_state.results:
        st.divider()
        final_doc = ""

        for idx in sorted(st.session_state.results.keys()):
            with st.expander(f"📖 Varaq {idx+1}", expanded=(idx == sorted(st.session_state.results.keys())[0])):
                res = st.session_state.results[idx]

                # image to base64 (1 marta)
                b = io.BytesIO()
                processed_imgs[idx].save(b, format="JPEG", quality=90)
                b64 = base64.b64encode(b.getvalue()).decode("utf-8")

                # -------- DESKTOP: side-by-side
                st.markdown("<div class='desktop-only'>", unsafe_allow_html=True)
                c1, c2 = st.columns([1, 1.35], gap="large")

                with c1:
                    st.markdown(
                        f"""
                        <div class="sticky-preview">
                            <img src="data:image/jpeg;base64,{b64}" alt="page {idx+1}" />
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with c2:
                    st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)

                    if not st.session_state.auth:
                        st.markdown("<div class='premium-alert'>🔒 Word hisobotni yuklab olish va AI Chat uchun tizimga kiring!</div>", unsafe_allow_html=True)
                    else:
                        st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=260, key=f"ed_{idx}")
                        final_doc += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}"

                        st.session_state.chats.setdefault(idx, [])
                        for ch in st.session_state.chats[idx]:
                            st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                            st.markdown(f"<div class='chat-ai' style='color:black;'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                        user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                        if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                            if user_q:
                                with st.spinner("..."):
                                    chat_res = model.generate_content([f"Doc: {st.session_state.results[idx]}\nQ: {user_q}"])
                                    st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

                # -------- MOBILE: Tabs (Rasm | Natija | Chat)
                st.markdown("<div class='mobile-only'>", unsafe_allow_html=True)
                tabs = st.tabs(["📷 Rasm", "📝 Natija", "💬 Chat"])

                with tabs[0]:
                    st.markdown(
                        f"""
                        <div class="sticky-preview">
                            <img src="data:image/jpeg;base64,{b64}" alt="page {idx+1}" />
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with tabs[1]:
                    st.markdown(f"<div class='result-box'>{st.session_state.results.get(idx, res)}</div>", unsafe_allow_html=True)

                    if st.session_state.auth:
                        st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=st.session_state.results.get(idx, res), height=240, key=f"ed_m_{idx}")
                        final_doc += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}"

                with tabs[2]:
                    if not st.session_state.auth:
                        st.markdown("<div class='premium-alert'>🔒 Chat uchun tizimga kiring!</div>", unsafe_allow_html=True)
                    else:
                        st.session_state.chats.setdefault(idx, [])
                        for ch in st.session_state.chats[idx]:
                            st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                            st.markdown(f"<div class='chat-ai' style='color:black;'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                        user_q_m = st.text_input("Savol bering:", key=f"q_in_m_{idx}")
                        if st.button(f"So'rash {idx+1}", key=f"btn_m_{idx}"):
                            if user_q_m:
                                with st.spinner("..."):
                                    chat_res = model.generate_content([f"Doc: {st.session_state.results[idx]}\nQ: {user_q_m}"])
                                    st.session_state.chats[idx].append({"q": user_q_m, "a": chat_res.text})
                                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.auth and final_doc:
            doc = Document()
            doc.add_paragraph(final_doc)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 DOWNLOAD REPORT", bio.getvalue(), "report.docx")

gc.collect()
