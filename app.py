import streamlit as st
import google.generativeai as genai
import pypdfium2 as pdfium
from PIL import Image
import io, gc, asyncio, base64, hashlib, uuid
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# --- 1. TIZIM VA DIZAYN ---
st.set_page_config(
    page_title="Manuscript AI - Academic Master v2",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    .result-box { 
        background-color: #ffffff; padding: 20px; border-radius: 10px; 
        border-left: 8px solid #c5a059; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        min-height: 200px; max-height: 500px; overflow-y: auto;
    }
    .stButton>button { width: 100%; border-radius: 8px; transition: 0.3s; }
    .stTextArea textarea { font-size: 15px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CORE SERVICES ---
@st.cache_resource
def get_db() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

db = get_db()
model = init_gemini()

# --- 3. OPTIMALLASHGAN YORDAMCHI FUNKSIYALAR ---
def get_file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()

def image_to_base64(img: Image.Image) -> str:
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=80) # Sifat va hajm balansi
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

@st.cache_data(show_spinner=False)
def render_page_optimized(file_content: bytes, page_idx: int, scale: float) -> Image.Image:
    try:
        pdf = pdfium.PdfDocument(file_content)
        page = pdf[page_idx]
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil()
        # Resurslarni yopish
        page.close()
        pdf.close()
        gc.collect() 
        return img
    except Exception as e:
        st.error(f"Render xatosi: {str(e)}")
        return None

# --- 4. KREDIT VA AI LOGIKASI ---
def fetch_live_credits(user_id: str):
    try:
        res = db.table("profiles").select("credits").eq("id", user_id).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

def use_credit_atomic(user_id: str):
    current = fetch_live_credits(user_id)
    if current > 0:
        db.table("profiles").update({"credits": current - 1}).eq("id", user_id).execute()
        return True
    return False

async def call_ai_async(prompt: str, img: Image.Image):
    try:
        img_payload = {"mime_type": "image/jpeg", "data": image_to_base64(img)}
        response = await asyncio.to_thread(model.generate_content, [prompt, img_payload])
        return response.text
    except Exception as e:
        return f"🚨 Tahlil xatosi: {str(e)}"

# --- 5. WORD EXPORT ---
def create_word_report(analysis_text, chat_history):
    try:
        doc = Document()
        doc.add_heading('Manuscript AI: Akademik Hisobot', 0)
        doc.add_heading('Ekspertiza Tahlili', level=1)
        doc.add_paragraph(analysis_text if analysis_text else "Tahlil mavjud emas.")
        
        if chat_history:
            doc.add_heading('Savol-javoblar tarixi', level=1)
            for msg in chat_history:
                p = doc.add_paragraph()
                p.add_run(f"{msg['role'].capitalize()}: ").bold = True
                p.add_run(msg['content'])
        
        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue()
    except Exception as e:
        st.error(f"Word yaratishda xato: {e}")
        return None

# --- 6. ASOSIY ILOVA ---
def main():
    # 🔐 AUTH (HARDCODED)
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        _, col_mid, _ = st.columns([1, 1.2, 1])
        with col_mid:
            st.title("🏛 Manuscript Login")
            email_in = st.text_input("Email:", value="admin@manuscript.uz")
            pass_in = st.text_input("Parol:", type="password")
            if st.button("Kirish"):
                if pass_in == "tarix-2026":
                    st.session_state.authenticated = True
                    class MockUser:
                        id = "72b7208c-6da2-449f-a8dd-a61c7a25a42e"
                        email = email_in
                    st.session_state.user = MockUser()
                    st.rerun()
                else: st.error("Parol noto'g'ri!")
        return

    # 📊 STATE INIT
    user_id = st.session_state.user.id
    if "ai_store" not in st.session_state: st.session_state.ai_store = {}
    if "chat_store" not in st.session_state: st.session_state.chat_store = {}

    # 🛠 SIDEBAR
    with st.sidebar:
        st.title("📜 Sozlamalar")
        st.write(f"👤 **{st.session_state.user.email}**")
        live_creds = fetch_live_credits(user_id)
        st.metric("💳 Qolgan kredit", f"{live_creds} sahifa")
        st.divider()
        lang = st.selectbox("Manba tili:", ["Chig'atoy", "Arabcha", "Forscha", "Usmonli"])
        style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Kufiy", "Riq'a"])
        if st.button("🚪 Chiqish"):
            st.session_state.clear()
            st.rerun()

    # 📁 FAYL YUKLASH
    file = st.file_uploader("Faylni tanlang (PDF yoki Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'])
    
    if file:
        file_bytes = file.getvalue()
        file_id = get_file_hash(file_bytes)
        
        # Sahifani aniqlash
        if file.type == "application/pdf":
            try:
                pdf_doc = pdfium.PdfDocument(file_bytes)
                total_pages = len(pdf_doc)
                pdf_doc.close()
                selected_page = st.number_input(f"Sahifa (1-{total_pages}):", 1, total_pages) - 1
            except: 
                st.error("PDF formatida xatolik.")
                return
        else:
            selected_page, total_pages = 0, 1

        state_key = f"{file_id}_{selected_page}"
        st.session_state.chat_store.setdefault(state_key, [])

        col_left, col_right = st.columns([1, 1.3])

        # 🖼 CHAP TOMON: TASVIR
        with col_left:
            zoom = st.slider("Kattalashtirish (Zoom)", 1.0, 3.0, 1.5, step=0.1)
            img_ui = render_page_optimized(file_bytes, selected_page, scale=zoom)
            if img_ui:
                st.image(img_ui, use_container_width=True, caption=f"Sahifa: {selected_page + 1}")
            
            # Export tugmasi
            if state_key in st.session_state.ai_store:
                word_data = create_word_report(st.session_state.ai_store[state_key], st.session_state.chat_store[state_key])
                if word_data:
                    ts = datetime.now().strftime("%H%M%S")
                    st.download_button(
                        f"📥 Hisobotni yuklash (.docx)", 
                        word_data, 
                        f"Manuscript_{state_key}_{ts}.docx",
                        use_container_width=True
                    )

        # 🖋 O'NG TOMON: TAHLIL VA CHAT
        with col_right:
            t1, t2 = st.tabs(["🖋 Akademik Tahlil", "💬 Chat (Savol-javob)"])
            
            with t1:
                if st.button("🚀 Tahlilni boshlash"):
                    if live_creds > 0:
                        with st.spinner("AI tahlil qilmoqda..."):
                            # Tahlil uchun yuqori sifatli rasm (scale=3.0)
                            img_ai = render_page_optimized(file_bytes, selected_page, scale=3.0)
                            prompt = f"Siz matnshunos-akademiksiz. {lang} va {style} uslubidagi ushbu qo'lyozmani tahlil qiling: 1.Transliteratsiya 2.Tarjima 3.Ilmiy izohlar."
                            res = asyncio.run(call_ai_async(prompt, img_ai))
                            st.session_state.ai_store[state_key] = res
                            use_credit_atomic(user_id)
                            st.rerun()
                    else:
                        st.warning("Kreditingiz tugagan! Iltimos, balansni to'ldiring.")

                if state_key in st.session_state.ai_store:
                    st.markdown("### 📋 AI Xulosasi")
                    st.markdown(f"<div class='result-box'>{st.session_state.ai_store[state_key]}</div>", unsafe_allow_html=True)
                    new_val = st.text_area("📝 Tahrirlash:", value=st.session_state.ai_store[state_key], height=200)
                    st.session_state.ai_store[state_key] = new_val

            with t2:
                chat_box = st.container(height=400)
                for m in st.session_state.chat_store[state_key]:
                    chat_box.chat_message(m["role"]).write(m["content"])

                if q := st.chat_input("Ushbu sahifa bo'yicha savol bering..."):
                    if live_creds > 0:
                        st.session_state.chat_store[state_key].append({"role": "user", "content": q})
                        with st.spinner("AI o'ylanmoqda..."):
                            context = st.session_state.ai_store.get(state_key, "Tahlil hali qilinmagan.")
                            chat_prompt = f"Sahifa tahlili: {context}\nSavol: {q}"
                            # Chat uchun tezkor render
                            img_fast = render_page_optimized(file_bytes, selected_page, scale=1.2)
                            ans = asyncio.run(call_ai_async(chat_prompt, img_fast))
                            st.session_state.chat_store[state_key].append({"role": "assistant", "content": ans})
                            use_credit_atomic(user_id)
                            st.rerun()
                    else:
                        st.error("Chat uchun kredit yetarli emas.")

    gc.collect()

if __name__ == "__main__":
    main()
