import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io, gc, time, sqlite3, asyncio, base64, hashlib
from datetime import datetime
from docx import Document
from tenacity import retry, stop_after_attempt, wait_exponential

# --- 1. TIZIM VA SEO SOZLAMALARI ---
st.set_page_config(
    page_title="Manuscript AI - Enterprise Pro",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .main { background-color: #f4ecd8; color: #1a1a1a; font-family: 'Times New Roman', serif; }
    .stApp { max-width: 100%; }
    .result-box { background: #ffffff; padding: 20px; border-radius: 12px; border-left: 8px solid #c5a059; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-bottom: 20px; color: #000; }
    .chat-container { height: 500px; overflow-y: auto; display: flex; flex-direction: column; background: #fdfaf1; padding: 15px; border-radius: 10px; border: 1px solid #d4af37; }
    .stTextArea textarea { background-color: #ffffff !important; color: #000 !important; border: 1px solid #c5a059 !important; font-size: 16px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%); color: #c5a059 !important; font-weight: bold; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 3. MA'LUMOTLAR BAZASI VA LOGIKA ---
class DBManager:
    """SQLite orqali chat va billing ma'lumotlarini doimiy saqlash klassi"""
    def __init__(self):
        self.conn = sqlite3.connect('manuscript_enterprise.db', check_same_thread=False)
        self._setup()

    def _setup(self):
        with self.conn:
            self.conn.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                (id INTEGER PRIMARY KEY, file_id TEXT, page_idx INT, role TEXT, content TEXT, timestamp TEXT)''')
            self.conn.execute('''CREATE TABLE IF NOT EXISTS usage_logs 
                (date TEXT PRIMARY KEY, req_count INTEGER, tokens INTEGER)''')

    def save_chat(self, file_id, page_idx, role, content):
        with self.conn:
            self.conn.execute("INSERT INTO chat_history (file_id, page_idx, role, content, timestamp) VALUES (?,?,?,?,?)",
                            (file_id, page_idx, role, content, datetime.now().isoformat()))

    def fetch_chat(self, file_id, page_idx):
        return self.conn.execute("SELECT role, content FROM chat_history WHERE file_id=? AND page_idx=? ORDER BY timestamp ASC", 
                               (file_id, page_idx)).fetchall()

    def log_billing(self, tokens):
        today = datetime.now().strftime('%Y-%m-%d')
        with self.conn:
            self.conn.execute('''INSERT INTO usage_logs (date, req_count, tokens) VALUES (?, 1, ?) 
                ON CONFLICT(date) DO UPDATE SET req_count = req_count + 1, tokens = tokens + ?''', (today, tokens, tokens))

db = DBManager()

# --- 4. ASYNC AI INTEGRATSIYA VA BATCH PROCESSING ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("API Key topilmadi! Secrets sozlamalarini tekshiring.")
    st.stop()

def prepare_gemini_img(img):
    """Tuzatish 1: Rasmni Gemini API qabul qiladigan base64 formatiga o'tkazish"""
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def analyze_batch_async(prompt, images):
    """Tuzatish 2: Asinxron batch so'rovlar (bloklashsiz)"""
    contents = [prompt] + [prepare_gemini_img(img) for img in images]
    response = await model.generate_content_async(contents)
    return response

# --- 5. PDF LAZY RENDERING VA CACHING ---
def get_pdf_page(file_bytes, page_idx, scale=2):
    """Tuzatish 4: Session_state orqali renderni kesh qilish (Lazy loading)"""
    cache_key = f"img_cache_{hashlib.md5(file_bytes).hexdigest()}_{page_idx}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    pdf = pdfium.PdfDocument(file_bytes)
    page = pdf[page_idx]
    bitmap = page.render(scale=scale)
    pil_img = bitmap.to_pil()
    pdf.close()
    
    st.session_state[cache_key] = pil_img # Keshga saqlash
    return pil_img

# --- 6. WORD EKSPORT (KENGAYTIRILGAN) ---
def export_to_word(analysis, history, filename):
    """Tuzatish 5: Tahlil va barcha chat yozishmalarini Wordga eksport qilish"""
    doc = Document()
    doc.add_heading('Manuscript AI Academic Report', 0)
    doc.add_heading('1. Ekspertiza Xulosasi', level=1)
    doc.add_paragraph(analysis)
    
    if history:
        doc.add_heading('2. Qo\'shimcha Tadqiqot (Chat Tarixi)', level=1)
        for role, msg in history:
            p = doc.add_paragraph()
            p.add_run(f"{role}: ").bold = True
            p.add_run(msg)
            
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- 7. ASOSIY ILOVA LOGIKASI ---
async def main():
    if "authenticated" not in st.session_state: st.session_state.authenticated = False
    
    # Kirish tizimi
    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            st.title("🔐 Enterprise Login")
            pwd = st.text_input("Maxfiy parol", type="password")
            if st.button("Kirish"):
                if pwd == st.secrets["APP_PASSWORD"]:
                    st.session_state.authenticated = True
                    st.rerun()
        return

    # Sidebar
    with st.sidebar:
        st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
        lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
        era = st.selectbox("Xattotlik uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
        st.divider()
        if st.button("🚪 Tizimdan chiqish"):
            st.session_state.authenticated = False
            st.rerun()

    st.title("🏛 Akademik Qo'lyozmalar Ekspertiza Markazi")
    
    # File Uploader (Drag & Drop)
    uploaded_file = st.file_uploader("Faylni yuklang (PDF, JPG, PNG)", type=['pdf', 'png', 'jpg', 'jpeg'])

    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        file_id = hashlib.md5(file_bytes).hexdigest()
        
        if uploaded_file.type == "application/pdf":
            pdf = pdfium.PdfDocument(file_bytes)
            total_pages = len(pdf)
            selected_pages = st.multiselect("Tahlil uchun sahifalarni tanlang:", range(1, total_pages + 1), default=[1])
            pdf.close()
        else:
            selected_pages = [1]

        # Tahlil tugmasi
        if st.button("✨ Akademik Batch Tahlilni Boshlash"):
            with st.status("AI tahlil o'tkazmoqda...", expanded=True) as status:
                batch_imgs = [get_pdf_page(file_bytes, p-1) for p in selected_pages]
                prompt = f"Siz akademiksiz. {lang} va {era} xatidagi matnni tahlil qiling: 1.Transliteratsiya. 2.Tarjima. 3.Izoh."
                
                try:
                    response = await analyze_batch_async(prompt, batch_imgs)
                    st.session_state[f"result_{file_id}"] = response.text
                    db.log_billing(response.usage_metadata.total_token_count)
                    status.update(label="✅ Tahlil muvaffaqiyatli yakunlandi!", state="complete")
                except Exception as e:
                    st.error(f"Xatolik: {e}")

        # --- 8. UI: SPLIT VIEW (IMAGE + CHAT) ---
        if f"result_{file_id}" in st.session_state:
            st.divider()
            col_view, col_analysis = st.columns([1, 1.1])
            
            with col_view:
                current_view_page = st.selectbox("Sahifani ko'rish:", selected_pages)
                main_img = get_pdf_page(file_bytes, current_view_page-1, scale=3)
                zoom = st.slider("Zoom:", 100, 300, 100)
                st.image(main_img, width=int(zoom * 7)) # Dinamik zoom

            with col_analysis:
                tab1, tab2 = st.tabs(["🖋 Tahlil & Tahrir", "💬 Interaktiv Chat"])
                
                with tab1:
                    raw_res = st.session_state[f"result_{file_id}"]
                    edited_res = st.text_area("AI Xulosasini tahrirlash:", value=raw_res, height=400)
                    
                    # Word Eksport
                    history = db.fetch_chat(file_id, current_view_page)
                    word_data = export_to_word(edited_res, history, uploaded_file.name)
                    st.download_button("📥 Word hisobotni yuklash", word_data, f"{uploaded_file.name}_report.docx")

                with tab2:
                    # Tuzatish 3: Chat scroll va update
                    chat_container = st.container(height=450)
                    history = db.fetch_chat(file_id, current_view_page)
                    
                    for role, msg in history:
                        with chat_container.chat_message(role.lower()):
                            st.write(msg)

                    user_q = st.chat_input("Savol bering...")
                    if user_q:
                        db.save_chat(file_id, current_view_page, "User", user_q)
                        with st.spinner("AI o'ylanmoqda..."):
                            # Chat kontekstiga rasm va tahlilni qo'shamiz
                            chat_prompt = f"Matn: {edited_res}\nSavol: {user_q}"
                            response = await model.generate_content_async([chat_prompt, prepare_gemini_img(main_img)])
                            db.save_chat(file_id, current_view_page, "AI", response.text)
                            db.log_billing(response.usage_metadata.total_token_count)
                            st.rerun()

    gc.collect()

if __name__ == "__main__":
    # Tuzatish 2: Streamlit ichida asinxron loopni to'g'ri ishga tushirish
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

