import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SAHIFA SOZLAMALARI
st.set_page_config(page_title="Manuscript AI Pro", page_icon="📜", layout="wide")

# --- PROFESSIONAL DIZAYN (CSS) ---
st.markdown("""
    <style>
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .stButton>button {
        background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%);
        color: white; border-radius: 30px; font-weight: bold; width: 100%;
        border: none; padding: 10px; transition: 0.3s;
    }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
    .result-box {
        background-color: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 20px;
        border-left: 5px solid #4facfe;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. XAVFSIZLIK VA PAROL TIZIMI ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Secrets'dan ma'lumotlarni olish
try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Xatolik: Streamlit Secrets sozlanmagan! (GEMINI_API_KEY va APP_PASSWORD kiriting)")
    st.stop()

# Parol tekshiruvi (Agar kirmagan bo'lsa, hamma narsani to'xtatadi)
if not st.session_state["authenticated"]:
    st.container()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135783.png", width=100)
        st.title("Tizimga kirish")
        pwd_input = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("Kirish"):
            if pwd_input == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop() # PAROL TO'G'RI BO'LMAGUNCHA PASTGA O'TMAYDI

# --- 3. ASOSIY DASTUR QISMI (KIRGANDAN KEYIN) ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-flash-lite-latest')

# Sidebar sozlamalari
st.sidebar.title("💎 Manuscript Pro")
lang = st.sidebar.selectbox("Qo'lyozma tili:", ["Chig'atoy", "Arabcha", "Forscha", "Eski Turkiy"])
st.sidebar.divider()
if st.sidebar.button("Tizimdan chiqish"):
    st.session_state["authenticated"] = False
    st.rerun()

st.title("📜 Manuscript AI: Tarixiy qo'lyozmalar tahlili")
st.info(f"Hozirgi rejim: **{lang}** mutaxassisi yordamida tahlil qilish.")

# Fayl yuklash
uploaded_file = st.file_uploader("Faylni yuklang (PDF, PNG, JPG, JPEG)", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file is not None:
    images = []
    # PDF bo'lsa, sahifalarga ajratish
    if uploaded_file.type == "application/pdf":
        with st.spinner('PDF o'qilmoqda...'):
            pdf = pdfium.PdfDocument(uploaded_file)
            for i in range(len(pdf)):
                images.append(pdf[i].render(scale=2).to_pil())
    else:
        images.append(Image.open(uploaded_file))

    # Rasmlarni prevyu qilish
    st.subheader("🖼 Yuklangan sahifalar")
    cols = st.columns(3)
    for idx, img in enumerate(images):
        cols[idx % 3].image(img, caption=f"{idx+1}-sahifa", use_container_width=True)

    # TAHLIL BOSHQARUVI
    if st.button('✨ Tahlilni boshlash'):
        all_text_results = ""
        prompt = f"Siz {lang} tili va qadimiy matnlar bo'yicha mutaxassisiz. Ushbu qo'lyozmani tahlil qiling: 1. Transliteratsiya (Lotin). 2. Zamonaviy o'zbekcha tarjima. 3. Tarixiy izoh."

        for i, img in enumerate(images):
            with st.status(f"{i+1}-sahifa tahlil qilinmoqda...") as status:
                try:
                    response = model.generate_content([prompt, img])
                    res_text = response.text
                    
                    st.markdown(f"### 📄 {i+1}-sahifa natijasi:")
                    st.markdown(f"<div class='result-box'>{res_text}</div>", unsafe_allow_html=True)
                    
                    all_text_results += f"\n\n--- SAHIFA {i+1} ---\n{res_text}"
                    status.update(label=f"{i+1}-sahifa tayyor!", state="complete")
                except Exception as e:
                    st.error(f"Xatolik yuz berdi: {e}")

        # 4. WORD FORMATIDA EKSPORT
        if all_text_results:
            doc = Document()
            doc.add_heading('Manuscript AI: Tahlil Hisoboti', 0)
            doc.add_paragraph(f"Asl til: {lang}")
            doc.add_paragraph(all_text_results)
            
            bio = io.BytesIO()
            doc.save(bio)
            
            st.divider()
            st.download_button(
                label="📥 Natijani Word formatida yuklab olish",
                data=bio.getvalue(),
                file_name="manuscript_tahlil.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.balloons()
