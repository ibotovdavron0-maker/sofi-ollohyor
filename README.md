# Sufiollohyor Neon Glass

## GitHub Pages
1. Repozitoriydagi eski fayllarni zaxiralang.
2. Ushbu ZIP ichidagi fayllarni repo ildiziga yuklang (ichidagi fayllarning o‘zini, papkani emas).
3. `config.js` ichida Supabase URL va publishable keyni sozlang. `sb_secret_...` kalitini brauzer fayllariga yozmang.
4. GitHub Pages `main` branch va root papkadan nashr qilayotganini tekshiring.

## Sahifalar
- `index.html` — ommaviy bosh sahifa
- `admin.html` — administrator dashboard va diagrammalar
- `teacher.html` — o‘qituvchi kabineti
- `dashboard.html` — o‘quvchi kabineti
- `apply.html` — ariza formasi
- `login.html`, `register.html` — kirish va ro‘yxatdan o‘tish

**Muhim:** dashboarddagi raqamlar va diagrammalarning bir qismi namunaviy dizayn ma’lumotlaridir; ular real to‘lov yoki o‘quvchilar hisoboti deb qabul qilinmasin. Admin bo‘limlarining bir qismi navigatsiya/namuna sahifalaridir. Real ma’lumotlar uchun Supabase jadvali va RLS siyosatlarini tekshirish kerak. `config.js` ichida faqat publishable/anon kalit ishlatiladi; secret/service role kalitini hech qachon GitHub Pages’ga qo‘ymang.
