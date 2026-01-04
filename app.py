import streamlit as st
import google.generativeai as genai
import pypdfium2 as pdfium
from PIL import Image
import io, gc, asyncio, base64, hashlib
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# --- 1. TIZIM VA DIZAYN ---
st.set_page_config(page_title="Manuscript AI - Academic Master", page_icon="📜", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        min-height: 300px; max-height: 600px; overflow-y: auto; color: black;
    }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; }
    #MainMenu, footer, header {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. XIZMATLAR (Baza va AI) ---
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

db = get_db()
model = init_gemini()

# --- 3. YORDAMCHI FUNKSIYALAR ---
def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def fetch_live_credits(user_id):
    try:
        res = db.table("profiles").select("credits").eq("id", user_id).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

def use_credit_atomic(user_id):
    current = fetch_live_credits(user_id)
    if current > 0:
        db.table("profiles").update({"credits": current - 1}).eq("id", user_id).execute()
        return True
    return False

async def call_ai_async(prompt, img):
    try:
        img_payload = {"mime_type": "image/jpeg", "data": image_to_base64(img)}
        response = await asyncio.to_thread(model.generate_content, [prompt, img_payload])
        return response.text
    except Exception as e: return f"🚨 AI Xatosi: {str(e)}"

def create_word_report(analysis_text, chat_history):
    doc = Document()
    doc.add_heading('Manuscript AI: Akademik Hisobot', 0)
    doc.add_heading('Ekspertiza Xulosasi', level=1)
    doc.add_paragraph(analysis_text)
    if chat_history:
        doc.add_heading('Savol-javoblar tarixi', level=1)
        for msg in chat_history:
            doc.add_paragraph(f"{msg['role'].upper()}: {msg['content']}")
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- 4. ASOSIY ILOVA ---
def main():
    if "authenticated" not in st.session_state: st.session_state.authenticated = False

    if not st.session_state.authenticated:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.title("🏛 Manuscript AI")
            pwd = st.text_input("Parol:", type="password")
            if pwd == "tarix-2026":
                st.session_state.authenticated = True
                class MockUser:
                    id = "72b7208c-6da2-449f-a8dd-a61c7a25a42e"
                    email = "d87809889@gmail.com"
                st.session_state.user = MockUser()
                st.rerun()
        return

    user_id = st.session_state.user.id
    if "ai_store" not in st.session_state: st.session_state.ai_store = {}
    if "chat_store" not in st.session_state: st.session_state.chat_store = {}

    with st.sidebar:
        st.header("📜 Panel")
        st.write(f"👤 {st.session_state.user.email}")
        live_creds = fetch_live_credits(user_id)
        st.metric("💳 Qolgan kredit", f"{live_creds} bet")
        st.divider()
        lang = st.selectbox("Til:", ["Chig'atoy", "Arabcha", "Forscha", "Usmonli"])
        style = st.selectbox("Uslub:", ["Nasta'liq", "Suls", "Kufiy", "Riq'a"])
        if st.button("🚪 Chiqish"):
            st.session_state.clear()
            st.rerun()

    st.title("📜 Qo'lyozmalar Ekspertiza Markazi")
    file = st.file_uploader("Faylni yuklang (PDF/JPG/PNG)", type=['pdf', 'png', 'jpg', 'jpeg'])

    if file:
        file_bytes = file.getvalue()
        file_hash = hashlib.md5(file_bytes).hexdigest()
        img_to_show = None
        page_num = 0
        
        # --- PDF va RASM AJRATISH (XATOSIZ) ---
        if file.type == "application/pdf":
            try:
                pdf = pdfium.PdfDocument(file_bytes)
                total_pages = len(pdf)
                page_num = st.number_input(f"Sahifa (1-{total_pages})", 1, total_pages) - 1
                zoom = st.slider("Kattalashtirish (Zoom):", 1.0, 3.0, 1.5)
                bitmap = pdf[page_num].render(scale=zoom)
                img_to_show = bitmap.to_pil()
                pdf.close()
            except Exception as e:
                st.error(f"PDF yuklashda xato: {e}")
        else:
            try:
                img_to_show = Image.open(io.BytesIO(file_bytes))
                st.info("Rasm formati aniqlandi. Zoom rasmlar uchun original holatda.")
            except Exception as e:
                st.error(f"Rasm ochishda xato: {e}")

        if img_to_show:
            state_key = f"{file_hash}_{page_num}"
            st.session_state.chat_store.setdefault(state_key, [])

            col1, col2 = st.columns([1, 1.2])
            with col1:
                st.image(img_to_show, use_container_width=True)
                if state_key in st.session_state.ai_store:
                    word_data = create_word_report(st.session_state.ai_store[state_key], st.session_state.chat_store[state_key])
                    st.download_button("📥 Wordda yuklash", word_data, f"Report_{state_key}.docx", use_container_width=True)

            with col2:
                tab1, tab2 = st.tabs(["🖋 Akademik Tahlil", "💬 Chat"])
                with tab1:
                    if st.button("✨ Tahlilni boshlash"):
                        if live_creds > 0:
                            with st.spinner("AI tahlil qilmoqda..."):
                                prompt = f"Siz akademiksiz. {lang} tili, {style} uslubidagi ushbu manbani tahlil qiling: 1.Transliteratsiya, 2.Tarjima, 3.Izoh."
                                res = asyncio.run(call_ai_async(prompt, img_to_show))
                                st.session_state.ai_store[state_key] = res
                                use_credit_atomic(user_id)
                                st.rerun()
                        else: st.error("Kredit yetarli emas!")
                    
                    if state_key in st.session_state.ai_store:
                        st.markdown(f"<div class='result-box'>{st.session_state.ai_store[state_key]}</div>", unsafe_allow_html=True)
                        new_txt = st.text_area("📝 Tahrirlash:", value=st.session_state.ai_store[state_key], height=200)
                        st.session_state.ai_store[state_key] = new_txt

                with tab2:
                    chat_box = st.container(height=400)
                    for m in st.session_state.chat_store[state_key]:
                        chat_box.chat_message(m["role"]).write(m["content"])
                    if q := st.chat_input("Savol bering..."):
                        if live_creds > 0:
                            st.session_state.chat_store[state_key].append({"role": "user", "content": q})
                            ans = asyncio.run(call_ai_async(f"Kontekst: {st.session_state.ai_store.get(state_key, '')}\nSavol: {q}", img_to_show))
                            st.session_state.chat_store[state_key].append({"role": "assistant", "content": ans})
                            use_credit_atomic(user_id)
                            st.rerun()
    gc.collect()

if __name__ == "__main__":
    main()
