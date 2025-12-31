import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. Sahifa sozlamalari va Dizayn
st.set_page_config(page_title="Manuscript AI Pro", page_icon="📜", layout="wide")

st.markdown("""
    <style>
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .stButton>button {
        background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%);
        color: white; border-radius: 30px; font-weight: bold; width: 100%;
    }
    .result-card {
        background: white; padding: 15px; border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- MAXFIY MA'LUMOTLAR (Streamlit Secrets orqali) ---
# Diqqat: Bu yerda endi kalit va parol yozilmaydi!
try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("Secrets sozlanmagan! Streamlit sozlamalaridan GEMINI_API_KEY va APP_PASSWORD ni kiriting.")
    st.stop()

model = genai.GenerativeModel('gemini-flash-lite-latest')

# 2. Kirish Tizimi
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Manuscript AI: Kirish")
    pwd = st.text_input("Maxfiy parolni kiriting:", type="password")
    if st.button("Tizimga kirish"):
        if pwd == CORRECT_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Parol noto'g'ri!")
    st.stop()

# 3. Asosiy Dastur (Faqat kirgandan keyin ochiladi)
st.sidebar.title("⚙️ Sozlamalar")
lang = st.sidebar.selectbox("Qo'lyozma tili:", ["Chig'atoy", "Arabcha", "Forscha", "Eski Turkiy"])
if st.sidebar.button("Chiqish"):
    st.session_state["authenticated"] = False
    st.rerun()

st.title("📜 Manuscript AI Pro")
st.write(f"Hozirgi rejim: **{lang} mutaxassisi**")

uploaded_file = st.file_uploader("Qo'lyozma (PDF yoki Rasm) yuklang", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    images = []
    if uploaded_file.type == "application/pdf":
        with st.spinner('PDF o'qilmoqda...'):
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                images.append(pdf[i].render(scale=2).to_pil())
    else:
        images.append(Image.open(uploaded_file))

    cols = st.columns(3)
    for idx, img in enumerate(images):
        cols[idx % 3].image(img, caption=f"{idx+1}-sahifa", use_container_width=True)

    if st.button('✨ Tahlilni boshlash'):
        all_text = ""
        prompt = f"Siz {lang} qo'lyozmalari mutaxassisiz. Matnni lotinchaga o'gir, o'zbekcha tarjima qil va izoh ber."
        
        for i, img in enumerate(images):
            with st.status(f"{i+1}-sahifa tahlil qilinmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    res_text = response.text
                    st.markdown(f"<div class='result-card'><b>{i+1}-sahifa:</b><br>{res_text}</div>", unsafe_allow_html=True)
                    all_text += f"\n\n--- Sahifa {i+1} ---\n{res_text}"
                    status.update(label=f"{i+1}-sahifa tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xato yuz berdi: {e}")
        
        # Word Eksport
        doc = Document()
        doc.add_heading('Manuscript AI: Tahlil Natijalari', 0)
        doc.add_paragraph(all_text)
        bio = io.BytesIO()
        doc.save(bio)
        
        st.divider()
        st.download_button("📥 Natijani Wordda yuklash", bio.getvalue(), "tahlil.docx")
        st.balloons()