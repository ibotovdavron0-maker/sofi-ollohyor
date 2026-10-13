# SO‘FI OLLOHYOR — GitHub Pages website

## ZIP tarkibi
- `index.html` — bosh sahifa, modal ariza formasi
- `style.css` — qora shisha/rangli yorug‘liklar dizayni va moslashuv
- `app.js` — menyu, ariza yuborish va bosh sahifa ma’lumotlari
- `logo.svg` — logotip aktiv fayl
- `login.html`, `register.html`, `dashboard.html`, `teacher.html`, `admin.html` — kirish va kabinet sahifalari
- `live-app.js` — Supabase auth/kabinet funksiyalari
- `config.js` — Supabase sozlamasi uchun fayl (pastdagi muhim eslatmaga qarang)
- `database.sql` — Supabase jadval va RLS siyosatlari
- `CNAME` — sufiollohyor.uz domeni

## MUHIM — mavjud Supabase sozlamasini saqlash
ZIP ichidagi `config.js`da public/anon kalit ataylab to‘ldirilmagan. GitHub’dagi hozirgi `config.js` faylingizni avval alohida yuklab oling va ZIP ichidagi `config.js` o‘rniga qo‘ying. U yerga faqat Supabase Project URL va publishable/anon key kiradi. `service_role` yoki Google Client Secret kalitini hech qachon saytga qo‘ymang.

Project URL: `https://oteokizwakceztwrocol.supabase.co`

## GitHub’ga joylash (Android)
1. ZIP faylni telefonga yuklab olib, arxivni oching.
2. GitHub repo `ibotovdavron0-maker/sofi-ollohyor`ni oching.
3. Hozirgi `config.js`ni ochib, uning nusxasini telefonga saqlang. `CNAME` faylida `sufiollohyor.uz` bo‘lsa, uni ham saqlang.
4. GitHub’da `Add file` → `Upload files` orqali arxivdan ochilgan fayllarni tanlang (ZIP faylining o‘zini emas).
5. Agar GitHub mavjud nomli faylni almashtirishga ruxsat bermasa, o‘sha faylni ochib qalamcha bilan tahrirlash yoki `Delete file` orqali o‘chirib, qayta yuklash kerak bo‘ladi. Bunda `config.js` va `CNAME`ni tasodifan o‘chirmang.
6. `Commit changes` bosing va `Actions` bo‘limida Pages build tugashini kuting.
7. Saytni Chrome’da ochib, yangilash uchun sahifani qayta yuklang; zarur bo‘lsa inkognito rejimida tekshiring.

## Ariza va ma’lumotlar
Bosh sahifa arizani Supabase `applications` jadvaliga yuboradi. Jadval va `public application insert` RLS siyosati `database.sql`da mavjud. Supabase SQL Editor’da avval ishlatilgan sxemani qayta yaratishdan oldin ehtiyot bo‘ling; ayniqsa mavjud bazaga SQL faylni ko‘r-ko‘rona qayta ishlatmang.

`data.json` ixtiyoriy bo‘lib, ustozlar, reyting va darsliklar uchun statik ko‘rinish ma’lumotlari saqlashi mumkin. Fayl bo‘lmasa, sayt bo‘sh holat xabarlarini ko‘rsatadi.

## Xavfsizlik va tekshiruv
GitHub Pages statik hostingdir. Admin sahifasidagi har bir boshqaruv bo‘limi va diagramma real bazaga ulangan deb hisoblamang: grafiklarning bir qismi namuna ma’lumotidir, ayrim modullar alohida ulashni talab qiladi. `config.js` ichida faqat public/anon kalit ishlating; ma’lumotlarni himoya qilish Supabase RLS siyosatlariga bog‘liq.
