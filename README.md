# 📜 Manuscript AI — Tarixiy Qo'lyozmalar Tahlili va Tarjimoni
**Pro Academic & Enterprise v2.5**

Bu loyiha eski o'zbek (chig'atoy), fors, arab va eski turkiy tillardagi qo'lyozma hamda tarixiy hujjatlarni o'qish, ularni lotin alifbosiga o'girish va zamonaviy o'zbek tiliga tarjima qilish uchun mo'ljallangan professional intellektual tizimdir.

🚀 **Live Demo:** [https://doonik.streamlit.app](https://doonik.streamlit.app)

---

## ✨ Asosiy Imkoniyatlar
- **Vision AI Texnologiyasi:** Google Gemini 1.5/2.0 modellari yordamida qadimiy xattotlik namunalarini (Nasta'liq, Suls, Kufiy) vizual tahlil qilish.
- **Async Batch Analysis:** Bir vaqtning o'zida bir nechta sahifani parallel tahlil qilish (UI bloklanmaydi).
- **Interaktiv Akademik Chat:** Har bir sahifa bo'yicha AI bilan ilmiy muloqot qilish va tahlilni chuqurlashtirish imkoniyati.
- **Smart Caching & Lazy Loading:** PDF sahifalari xotirani tejash uchun keshlanadi, bu esa og'ir fayllarda ham barqaror ishlashni ta'minlaydi.
- **Credit-Based SaaS:** Supabase integratsiyasi orqali foydalanuvchi limitlari va rollarini professional boshqarish.
- **Eksport:** Tahlil natijalari va chat tarixini professional Word (.docx) formatida yuklab olish.

---

## 🛠 Texnologiyalar (Stack)
- **Frontend:** Streamlit 1.28+
- **AI Miyasi:** Google Gemini 1.5 Flash
- **Backend/Database:** Supabase (PostgreSQL)
- **PDF Engine:** pypdfium2 (DPI 300 tahlil sifati)
- **Dasturlash tili:** Python 3.10+

---

## 🚀 O'rnatish va Ishga Tushirish (Local Setup)

1. Loyihani yuklab oling:
   ```bash
   git clone https://github.com/d87809889-dot/DOONIK.git
   cd DOONIK
   Kerakli kutubxonalarni o'rnating:
kod
Bash
pip install -r requirements.txt
.streamlit/secrets.toml faylini yarating va API kalitlarni kiriting:
kod
Toml
GEMINI_API_KEY = "SIZNING_API_KALITINGIZ"
SUPABASE_URL = "SIZNING_SUPABASE_URLINGIZ"
SUPABASE_KEY = "SIZNING_SUPABASE_ANON_KEYINGIZ"
APP_PASSWORD = "SAYTGA_KIRISH_PAROLI"
Dasturni ishga tushiring:
kod
Bash
streamlit run app.py
🔒 Xavfsizlik va Maxfiylik
Loyiha maxfiy parol bilan himoyalangan. Barcha maxfiy ma'lumotlar Streamlit Secrets ichida shifrlangan holda saqlanadi. Ma'lumotlar bazasi Supabase orqali xavfsiz boshqariladi.
📬 Aloqa
Agar loyiha bo'yicha takliflaringiz yoki ilmiy hamkorlik rejalaringiz bo'lsa, ushbu repository orqali bog'lanishingiz mumkin.
Keywords: #AI #Manuscript #History #Uzbekistan #Chagatay #Persian #Arabic #Translation #OCR #DigitalHumanities #SaaS
kod
Kod
