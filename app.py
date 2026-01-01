import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SAHIFA SOZLAMALARI
st.set_page_config(
    page_title="Manuscript AI - Academic Master v7.5", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (KUCHAYTIRILGAN) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;} .stAppDeployButton {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; }
    
    /* TAHRIRLASH OYNASI */
    .stTextArea textarea {
        background-color: #fdfaf1 !important;
        color: #000000 !important; 
        border: 2px solid #c5a059 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 17px !important;
    }

    /* CHAT ELEMENTLARI */
    .chat-container { margin-top: 15px; padding: 10px; border-top: 1px solid #d4af37; }
    .user-box { background-color: #e2e8f0; color: #000; padding: 10px; border-radius: 8px; border-left: 5px solid #1e3a8a; margin: 5px 0; }
    .ai-box { background-color: #ffffff; color: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px solid #d4af37; margin: 5px 0; }

    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important; font-weight: bold !important; width: 100% !important; border-radius: 5px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan!")
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
                st.error("Kod xato!")
    st.stop()

# --- 4. AI MODELI ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

with st.sidebar:
    st.markdown("<h2 style='color:#c5a059;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY QISM ---
st.markdown("<h1>Raqamli Qo'lyozmalar Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Manbani yuklang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

# Session state elementlarini boshlang'ich sozlash
if 'imgs' not in st.session_state: st.session_state['imgs'] = []
if 'res' not in st.session_state: st.session_state['res'] = []
if 'chat_history' not in st.session_state: st.session_state['chat_history'] = {}

if uploaded_file:
    # Fayl yangilansa, xotirani tozalash
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Raqamlashtirilmoqda...'):
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(uploaded_file)
                for i in range(len(pdf)):
                    imgs.append(pdf[i].render(scale=3).to_pil())
            else:
                imgs.append(Image.open(uploaded_file))
            st.session_state['imgs'] = imgs
            st.session_state['last_fn'] = uploaded_file.name
            st.session_state['res'] = []
            st.session_state['chat_history'] = {}

    # Prevyu
    cols = st.columns(min(len(st.session_state['imgs']), 4))
    for idx, img in enumerate(st.session_state['imgs']):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", use_container_width=True)

    if st.button('✨ TAHLILNI BOSHLASH'):
        new_results = []
        prompt = f"Siz matnshunos akademiksiz. {lang} va {era} uslubidagi qo'lyozmani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
        
        for i, img in enumerate(st.session_state['imgs']):
            with st.status(f"Varaq {i+1} o'qilmoqda...") as s:
                try:
                    response = model.generate_content([prompt, img])
                    new_results.append(response.text)
                    s.update(label=f"Varaq {i+1} tayyor!", state="complete")
                except Exception as e:
                    new_results.append(f"Xato: {e}")
        st.session_state['res'] = new_results

    # --- TAHLIL VA CHAT ---
    if st.session_state['res']:
        st.divider()
        final_text_doc = ""
        
        for idx, (img, res_text) in enumerate(zip(st.session_state['imgs'], st.session_state['res'])):
            st.subheader(f"📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            
            with c1:
                st.image(img, use_container_width=True)
            with c2:
                # Tahrirlash oynasi (barqaror matn bilan)
                edited = st.text_area(f"Ilmiy tahrir ({idx+1}):", value=res_text, height=350, key=f"ed_{idx}")
                final_text_doc += f"\n\n--- VARAQ {idx+1} ---\n{edited}"

            # Interaktiv Chat
            chat_id = f"chat_{idx}"
            if chat_id not in st.session_state['chat_history']:
                st.session_state['chat_history'][chat_id] = []

            with st.container():
                st.markdown(f"**💬 Varaq {idx+1} yuzasidan muloqot**")
                # Xabarlarni chiqarish
                for chat in st.session_state['chat_history'][chat_id]:
                    st.markdown(f"<div class='user-box'><b>Savol:</b> {chat['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='ai-box'><b>AI:</b> {chat['a']}</div>", unsafe_allow_html=True)

                # Savol kiritish
                user_q = st.text_input("Savol yozing:", key=f"input_{idx}")
                if st.button(f"So'rash", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("AI tahlil qilmoqda..."):
                            chat_prompt = f"Ushbu qo'lyozma matni asosida savolga javob bering: {user_q}\nMatn: {edited}"
                            chat_res = model.generate_content([chat_prompt, img])
                            st.session_state['chat_history'][chat_id].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
            st.divider()

        if final_text_doc:
            doc = Document()
            doc.add_paragraph(final_text_doc)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLASH", bio.getvalue(), "academic_report.docx")
