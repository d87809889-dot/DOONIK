import streamlit as st
import google.generativeai as genai
import pypdfium2 as pdfium
from PIL import Image
import io, gc, asyncio, base64, hashlib
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# --- 1. SAHIFA SOZLAMALARI VA DIZAYN ---
st.set_page_config(
    page_title="Manuscript AI - Pro Academic v3",
    page_icon="📜",
    layout="wide"
)

st.markdown("""
    <style>
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        color: #1a1a1a; line-height: 1.6; min-height: 300px; max-height: 600px; overflow-y: auto;
    }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; border: none; padding: 12px; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; }
    #MainMenu, footer, header {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. MA'LUMOTLAR BAZASI VA AI ULANISHI ---
@st.cache_resource
def get_db() -> Client:
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Baza ulanish xatosi: {e}")
        st.stop()

def init_gemini():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"AI konfiguratsiya xatosi: {e}")
        st.stop()

db = get_db()
model = init_gemini()

# --- 3. YORDAMCHI FUNKSIYALAR ---

def get_file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()

def image_to_base64(img: Image.Image) -> str:
    """Rasmni AI tahlili uchun optimallashtirilgan holda Base64-ga o'tkazish"""
    try:
        # Rasmni o'lchamini optimallashtirish (agar juda katta bo'lsa)
        max_size = 2000
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
        
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        st.error(f"Tasvirni qayta ishlashda xatolik: {e}")
        return ""

def render_page_optimized(file_content: bytes, page_idx: int, scale: float) -> Image.Image:
    """PDF sahifasini yuqori sifatda render qilish"""
    try:
        pdf = pdfium.PdfDocument(file_content)
        page = pdf[page_idx]
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil()
        page.close()
        pdf.close()
        gc.collect()
        return img
    except Exception as e:
        st.error(f"PDF sahifasini yuklashda xatolik: {e}")
        return None

# --- 4. KREDIT TIZIMI ---

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

# --- 5. MUKAMMAL PROMPT VA AI LOGIKASI ---

async def call_ai_async(prompt: str, img: Image.Image):
    try:
        b64_img = image_to_base64(img)
        if not b64_img: return "Tasvirni tayyorlashda xatolik."
        
        img_payload = {"mime_type": "image/jpeg", "data": b64_img}
        response = await asyncio.to_thread(model.generate_content, [prompt, img_payload])
        return response.text
    except Exception as e:
        return f"🚨 AI Tahlil xatosi: {str(e)}"

def get_academic_prompt(lang, style):
    return f"""
Siz qo'lyozmalar bo'yicha mutaxassis akademiksiz. Berilgan manbani (Til: {lang}, Uslub: {style}) qunt bilan tahlil qiling.
Natijani quyidagi tartibda bering:

1. **Transliteratsiya**: Matnni asl imlosidan hozirgi o'zbek lotin alifbosiga so'zma-so'z o'giring.
2. **Tarjima**: Matnning mazmunini tushunarli va ravon akademik o'zbek tilida bayon qiling.
3. **Ilmiy izohlar**: Matndagi tarixiy shaxslar, joy nomlari yoki o'sha davrga xos atamalarga ilmiy izoh bering.

Akademik aniqlikka va imlo qoidalariga rioya qiling.
"""

# --- 6. WORD EKSPORT ---

def create_word_report(analysis_text, chat_history):
    doc = Document()
    doc.add_heading('Manuscript AI: Akademik Hisobot', 0)
    doc.add_heading('Ekspertiza Xulosasi', level=1)
    doc.add_paragraph(analysis_text)
    
    if chat_history:
        doc.add_heading('Savol-javoblar tarixi', level=1)
        for msg in chat_history:
            p = doc.add_paragraph()
            p.add_run(f"{msg['role'].upper()}: ").bold = True
            p.add_run(msg['content'])
            
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- 7. ASOSIY ILOVA LOGIKASI ---

def main():
    # 🔐 PAROL TIZIMI
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        _, col_mid, _ = st.columns([1, 1.2, 1])
        with col_mid:
            st.title("🏛 Manuscript AI")
            pwd = st.text_input("Maxfiy parolni kiriting:", type="password")
            if pwd == "tarix-2026":
                st.session_state.authenticated = True
                class MockUser:
                    id = "72b7208c-6da2-449f-a8dd-a61c7a25a42e"
                    email = "d87809889@gmail.com"
                st.session_state.user = MockUser()
                st.rerun()
            elif pwd != "":
                st.error("Xato parol!")
        return

    # 📊 STATE INIT
    user_id = st.session_state.user.id
    if "ai_store" not in st.session_state: st.session_state.ai_store = {}
    if "chat_store" not in st.session_state: st.session_state.chat_store = {}

    # 🛠 SIDEBAR
    with st.sidebar:
        st.header("📜 Boshqaruv Paneli")
        st.write(f"👤 **Foydalanuvchi:** {st.session_state.user.email}")
        live_creds = fetch_live_credits(user_id)
        st.metric("💳 Qolgan kredit", f"{live_creds} bet")
        st.divider()
        lang = st.selectbox("Asl til:", ["Chig'atoy", "Arabcha", "Forscha", "Usmonli Turk"])
        style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Kufiy", "Riq'a", "Noma'lum"])
        if st.button("🚪 Chiqish"):
            st.session_state.clear()
            st.rerun()

    st.title("📜 Qo'lyozmalar Ekspertiza Markazi")
    file = st.file_uploader("Faylni yuklang (PDF/JPG/PNG)", type=['pdf', 'png', 'jpg', 'jpeg'])

    if file:
        file_bytes = file.getvalue()
        file_id = get_file_hash(file_bytes)
        
        # Fayl turini aniqlash va yuklash
        if file.type == "application/pdf":
            try:
                pdf_doc = pdfium.PdfDocument(file_bytes)
                total_pages = len(pdf_doc)
                pdf_doc.close()
                selected_page = st.number_input(f"Sahifa (1-{total_pages}):", 1, total_pages) - 1
                
                zoom = st.slider("Tasvir sifati (Kattalashtirish):", 1.0, 3.0, 1.5)
                img_ui = render_page_optimized(file_bytes, selected_page, scale=zoom)
            except Exception as e:
                st.error(f"PDF faylni o'qishda xatolik: {e}")
                return
        else:
            # Rasm fayllari uchun
            selected_page, total_pages = 0, 1
            try:
                img_ui = Image.open(io.BytesIO(file_bytes))
                st.info("Rasm yuklandi. Zoom PDF uchun xos, rasmlar original sifatda ko'rinadi.")
            except Exception as e:
                st.error(f"Rasm faylini ochishda xatolik: {e}")
                return

        state_key = f"{file_id}_{selected_page}"
        st.session_state.chat_store.setdefault(state_key, [])

        col_img, col_info = st.columns([1, 1.2])

        with col_img:
            if img_ui:
                st.subheader("🖼 Manba Tasviri")
                st.image(img_ui, use_container_width=True)
                
                if state_key in st.session_state.ai_store:
                    word_data = create_word_report(st.session_state.ai_store[state_key], st.session_state.chat_store[state_key])
                    st.download_button("📥 Wordda yuklab olish", word_data, f"Tahlil_{state_key}.docx", use_container_width=True)

        with col_info:
            tab_anal, tab_chat = st.tabs(["🖋 Akademik Tahlil", "💬 Ilmiy Muloqot"])
            
            with tab_anal:
                if st.button("✨ Tahlilni boshlash"):
                    if live_creds > 0:
                        with st.spinner("AI tahlil qilmoqda, iltimos kuting..."):
                            # Tahlil uchun yuqori sifatli rasm (PDF bo'lsa scale=3.0)
                            img_ai = img_ui if file.type != "application/pdf" else render_page_optimized(file_bytes, selected_page, scale=3.0)
                            
                            academic_prompt = get_academic_prompt(lang, style)
                            result = asyncio.run(call_ai_async(academic_prompt, img_ai))
                            
                            st.session_state.ai_store[state_key] = result
                            use_credit_atomic(user_id)
                            st.rerun()
                    else:
                        st.error("Kreditlar tugagan! Iltimos, balansni to'ldiring.")

                if state_key in st.session_state.ai_store:
                    st.markdown(f"<div class='result-box'>{st.session_state.ai_store[state_key]}</div>", unsafe_allow_html=True)
                    new_val = st.text_area("📝 Natijani tahrirlash:", value=st.session_state.ai_store[state_key], height=250, key=f"edit_{state_key}")
                    st.session_state.ai_store[state_key] = new_val

            with tab_chat:
                chat_container = st.container(height=450)
                for msg in st.session_state.chat_store[state_key]:
                    chat_container.chat_message(msg["role"]).write(msg["content"])

                if user_q := st.chat_input("Tahlil yuzasidan savol bering...", key=f"in_{state_key}"):
                    if live_creds > 0:
                        st.session_state.chat_store[state_key].append({"role": "user", "content": user_q})
                        with st.spinner("AI javob bermoqda..."):
                            context = st.session_state.ai_store.get(state_key, "Tahlil hali yakunlanmagan.")
                            chat_prompt = f"Matn tahlili: {context}\nSavol: {user_q}\nAkademik javob bering."
                            response = asyncio.run(call_ai_async(chat_prompt, img_ui))
                            st.session_state.chat_store[state_key].append({"role": "assistant", "content": response})
                            use_credit_atomic(user_id)
                            st.rerun()
                    else:
                        st.error("Kredit yetarli emas.")

    gc.collect()

if __name__ == "__main__":
    main()
