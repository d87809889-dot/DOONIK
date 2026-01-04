import streamlit as st
import google.generativeai as genai
import pypdfium2 as pdfium
from PIL import Image
import io, gc, asyncio, base64, hashlib
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# --- 1. TIZIM VA DIZAYN ---
st.set_page_config(page_title="Manuscript AI", page_icon="📜", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4ecd8 !important; }
    .result-box { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 8px solid #c5a059; color: black; min-height: 250px; }
    #MainMenu, footer, header {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. XIZMATLAR ---
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # 404 xatosini oldini olish uchun 'latest' versiya ishlatamiz
    return genai.GenerativeModel('gemini-1.5-flash-latest')

db = get_db()
model = init_gemini()

# --- 3. FUNKSIYALAR ---
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
    except Exception as e:
        return f"🚨 AI Xatosi: {str(e)}"

# --- 4. ASOSIY ILOVA ---
def main():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

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
    with st.sidebar:
        st.header("📜 Panel")
        st.write(f"👤 {st.session_state.user.email}")
        live_creds = fetch_live_credits(user_id)
        st.metric("💳 Qolgan kredit", f"{live_creds} bet")
        lang = st.selectbox("Til:", ["Chig'atoy", "Arabcha", "Forscha", "Usmonli"])
        style = st.selectbox("Uslub:", ["Nasta'liq", "Suls", "Kufiy", "Riq'a"])
        if st.button("🔄 Tizimni yangilash"):
            st.cache_data.clear()
            st.rerun()

    st.title("📜 Qo'lyozmalar Ekspertiza Markazi")
    file = st.file_uploader("Faylni yuklang", type=['pdf', 'png', 'jpg', 'jpeg'])

    if file:
        file_bytes = file.getvalue()
        file_hash = hashlib.md5(file_bytes).hexdigest()
        img_to_show = None
        page_num = 0

        # --- RASM VA PDF NI ABSOLYUT AJRATISH ---
        if file.type == "application/pdf" or file.name.lower().endswith(".pdf"):
            try:
                pdf = pdfium.PdfDocument(file_bytes)
                total_pages = len(pdf)
                page_num = st.number_input(f"Sahifa (1-{total_pages})", 1, total_pages) - 1
                zoom = st.slider("Kattalashtirish (Zoom):", 1.0, 3.0, 1.5)
                
                # Faqat PDF bo'lsagina Render funksiyasi ishlaydi
                page = pdf[page_num]
                bitmap = page.render(scale=zoom)
                img_to_show = bitmap.to_pil()
                pdf.close()
            except Exception as e:
                st.error(f"PDF Render xatosi: {e}")
        else:
            # Fayl rasm bo'lsa PDF kutubxonasi umuman chaqirilmaydi
            try:
                img_to_show = Image.open(io.BytesIO(file_bytes))
            except Exception as e:
                st.error(f"Rasm ochishda xato: {e}")

        if img_to_show:
            state_key = f"{file_hash}_{page_num}"
            if "ai_store" not in st.session_state: st.session_state.ai_store = {}
            if "chat_store" not in st.session_state: st.session_state.chat_store = {}
            st.session_state.chat_store.setdefault(state_key, [])

            col1, col2 = st.columns([1, 1.2])
            with col1:
                st.image(img_to_show, use_container_width=True)

            with col2:
                tab1, tab2 = st.tabs(["🖋 Tahlil", "💬 Chat"])
                with tab1:
                    if st.button("✨ Tahlilni boshlash"):
                        if live_creds > 0:
                            with st.spinner("AI tahlil qilmoqda..."):
                                prompt = f"Siz akademiksiz. {lang} tili, {style} uslubidagi ushbu manbani tahlil qiling: 1.Transliteratsiya, 2.Tarjima, 3.Izoh."
                                res = asyncio.run(call_ai_async(prompt, img_to_show))
                                if "🚨" not in res: # Agar xato bo'lmasa kredit ayiramiz
                                    st.session_state.ai_store[state_key] = res
                                    use_credit_atomic(user_id)
                                    st.rerun()
                                else:
                                    st.error(res)
                        else: st.error("Kredit yetarli emas!")
                    
                    if state_key in st.session_state.ai_store:
                        st.markdown(f"<div class='result-box'>{st.session_state.ai_store[state_key]}</div>", unsafe_allow_html=True)

                with tab2:
                    for m in st.session_state.chat_store[state_key]:
                        st.chat_message(m["role"]).write(m["content"])
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
