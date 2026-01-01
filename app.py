import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document
import gc
import time

# 1. TIZIM VA SEO SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Enterprise Academic 2026", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.05); color: #000000 !important; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-size: 16px !important; }
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 8px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-bubble-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 8px; border: 1px solid #d4af37; margin-bottom: 15px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%); color: #c5a059 !important; font-weight: bold; width: 100%; padding: 10px; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK VA SECRETS ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Settings > Secrets qismini tekshiring.")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Maxfiy kod", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Xato kod!")
    st.stop()

# --- 4. AI MODELINI MAJBURIY BARQAROR SOZLASH (FIX 404 & 429) ---
genai.configure(api_key=GEMINI_KEY)

# Risk-free model tanlovi: Faqat 1.5 Flash
# models/ prefiksi orqali v1 barqaror tizimga ulanadi
model = genai.GenerativeModel(model_name='models/gemini-1.5-flash')

with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Hujjat tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Paleografik uslub:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.markdown("---")
    st.caption("🚀 Rejim: Barqaror (1500 RPD)")
    st.caption("♻️ Sifat: DPI 200 (Optimallashgan)")
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar bo'yicha Ilmiy Markaz</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Ilmiy manbani yuklang (PDF/Rasm)", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

# Session state xotirasini xavfsiz boshqarish
if 'imgs' not in st.session_state: st.session_state['imgs'] = []
if 'academic_results' not in st.session_state: st.session_state['academic_results'] = []
if 'chat_histories' not in st.session_state: st.session_state['chat_histories'] = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Manba qayta ishlanmoqda (DPI 200)...'):
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(uploaded_file)
                # Xotira xavfsizligi uchun max 15 sahifa
                for i in range(min(len(pdf), 15)):
                    # DPI 200 (scale=2) - Token va RAM tejash uchun eng ma'quli
                    imgs.append(pdf[i].render(scale=2).to_pil())
                    gc.collect()
                pdf.close()
            else:
                imgs.append(Image.open(uploaded_file))
            st.session_state['imgs'] = imgs
            st.session_state['last_fn'] = uploaded_file.name
            st.session_state['academic_results'] = []
            st.session_state['chat_histories'] = {}

    cols = st.columns(min(len(st.session_state['imgs']), 4))
    for idx, img in enumerate(st.session_state['imgs']):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width='stretch')

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        new_results = []
        prompt = f"""
        Siz qadimgi matnshunos va paleograf akademiksiz. 
        Ushbu {lang} tilidagi va {era} uslubidagi manbani quyidagi mezonlar asosida tahlil qiling:
        1. PALEOGRAFIK TAVSIF. 2. TRANSLITERATSIYA. 3. SEMANTIK TARJIMA. 4. ILMIY IZOH.
        """
        for i, img in enumerate(st.session_state['imgs']):
            with st.status(f"Varaq {i+1} ekspertizadan o'tmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    new_results.append(response.text)
                    status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                    # RPM (Daqiqalik limit) himoyasi
                    time.sleep(4) 
                except Exception as e:
                    new_results.append(f"Xato: {e}")
        st.session_state['academic_results'] = new_results

    # --- 6. TAHLIL, TAHRIR VA SAVOL-JAVOB ---
    if st.session_state['academic_results']:
        st.divider()
        final_doc_text = ""
        for idx, (img, res) in enumerate(zip(st.session_state['imgs'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, width='stretch')
            with c2: st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            ed_val = st.text_area(f"Varaq {idx+1} bo'yicha tahrir:", value=res, height=400, key=f"ed_final_{idx}")
            final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

            # Interaktiv Chat (Har bir sahifa uchun maxfiy key bilan)
            st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan muloqot")
            chat_id = f"chat_{idx}"
            if chat_id not in st.session_state['chat_histories']: st.session_state['chat_histories'][chat_id] = []

            for ch in st.session_state['chat_histories'][chat_id]:
                st.markdown(f"""<div class='chat-bubble-user'><b>Savol:</b> {ch['q']}</div>""", unsafe_allow_html=True)
                st.markdown(f"""<div class='chat-bubble-ai'><b>AI Javobi:</b> {ch['a']}</div>""", unsafe_allow_html=True)

            user_q = st.text_input("Savol yozing:", key=f"q_input_fixed_{idx}")
            if st.button(f"So'rash {idx+1}", key=f"btn_fixed_{idx}"):
                if user_q:
                    try:
                        # Chat tejamkorligi: faqat matnli tahlilni yuboramiz
                        chat_res = model.generate_content(f"Hujjat tahlili: {ed_val}\nSavol: {user_q}\nAkademik javob ber.")
                        st.session_state['chat_histories'][chat_id].append({"q": user_q, "a": chat_res.text})
                        st.rerun()
                    except:
                        st.error("Limit oshdi. 60 soniya kuting.")
            st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")
