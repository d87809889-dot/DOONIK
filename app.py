import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document
import gc
import time

# 1. SEO VA SAHIFA SOZLAMALARI
st.set_page_config(page_title="Manuscript AI - Ultra Eco Master", page_icon="📜", layout="wide")

# --- 2. ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; }
    .result-box { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 5px 15px rgba(0,0,0,0.05); color: #000000 !important; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-size: 16px !important; }
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 10px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #d4af37; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%); color: #c5a059 !important; font-weight: bold; width: 100%; padding: 10px; border: none; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK VA AI SOZLAMALARI ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets topilmadi!")
    st.stop()

if not st.session_state["authenticated"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("Kod", type="password")
        if st.button("KIRISH"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else: st.error("Xato!")
    st.stop()

# --- 4. TEJAMKOR AI MODELI ---
genai.configure(api_key=GEMINI_KEY)
# Tejamkorlik uchun maxsus konfiguratsiya
eco_config = genai.types.GenerationConfig(
    max_output_tokens=1000, # Javob uzunligini cheklash (token tejash)
    temperature=0.3 # Aniqlikni oshirish
)
model = genai.GenerativeModel(model_name='gemini-flash-latest', generation_config=eco_config)

# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.markdown("---")
    st.caption("♻️ Ultra-Eco Mode: Active")
    if st.button("🚪 CHIQISH"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- 5. ASOSIY INTERFEYS ---
st.markdown("<h1>Raqamli Qo'lyozmalar Markazi</h1>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Faylni tanlang", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state['imgs'] = []
if 'academic_results' not in st.session_state: st.session_state['academic_results'] = []
if 'chat_history' not in st.session_state: st.session_state['chat_history'] = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Fayl optimallashmoqda...'):
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(uploaded_file)
                # Max 15 sahifa (tejamkorlik uchun)
                for i in range(min(len(pdf), 15)):
                    imgs.append(pdf[i].render(scale=2).to_pil()) # DPI 200 (Optimal)
                pdf.close()
            else:
                imgs.append(Image.open(uploaded_file))
            st.session_state['imgs'] = imgs
            st.session_state['last_fn'] = uploaded_file.name
            st.session_state['academic_results'] = []
            st.session_state['chat_history'] = {}
            gc.collect()

    cols = st.columns(min(len(st.session_state['imgs']), 4))
    for idx, img in enumerate(st.session_state['imgs']):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width='stretch')

    if st.button('✨ TAHLILNI BOSHLASH'):
        new_results = []
        # Tejamkor prompt
        prompt = f"Siz matnshunos akademiksiz. {lang} va {era} xatidagi ushbu qo'lyozmani qisqa va aniq tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
        
        for i, img in enumerate(st.session_state['imgs']):
            with st.status(f"Varaq {i+1} o'qilmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    new_results.append(response.text)
                    # 3 soniya kutish (Rate Limit himoyasi)
                    time.sleep(3)
                    status.update(label=f"Varaq {i+1} tayyor!", state="complete")
                except Exception as e:
                    new_results.append(f"Xato: {e}")
        st.session_state['academic_results'] = new_results

    # --- 6. TAHLIL, TAHRIR VA TEJAMKOR CHAT ---
    if st.session_state['academic_results']:
        st.divider()
        final_doc_text = ""
        for idx, (img, res) in enumerate(zip(st.session_state['imgs'], st.session_state['academic_results'])):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(img, width='stretch')
            with c2: st.markdown(f"<div class='result-box'><b>AI Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
            
            ed = st.text_area(f"Tahrir {idx+1}:", value=res, height=350, key=f"ed_{idx}")
            final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{ed}"

            # Interaktiv Chat (TEJAMKOR VERSION)
            st.markdown(f"##### 💬 Varaq {idx+1} muloqoti")
            cid = f"chat_{idx}"
            if cid not in st.session_state['chat_history']: st.session_state['chat_history'][cid] = []

            for chat in st.session_state['chat_history'][cid]:
                st.markdown(f"<div class='chat-bubble-user'><b>S:</b> {chat['q']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='chat-bubble-ai'><b>AI:</b> {chat['a']}</div>", unsafe_allow_html=True)

            user_q = st.text_input("Savol yozing:", key=f"q_in_{idx}")
            if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                if user_q:
                    with st.spinner("O'ylanmoqda..."):
                        try:
                            # TEJAMKORLIK: Rasmni qayta yubormaymiz, faqat matnni yuboramiz (agar savol matnga oid bo'lsa)
                            # Agar rasm vizualiga oid savol bo'lsa, rasmni qo'shish kerak. Hozircha matn tahlilini yuboramiz.
                            chat_res = model.generate_content(f"Qo'lyozma tahlili: {ed}\n\nSavol: {user_q}\nJavobni qisqa va akademik bering.")
                            st.session_state['chat_history'][cid].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                        except: st.error("Biroz kuting (Limit).")
            st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")

