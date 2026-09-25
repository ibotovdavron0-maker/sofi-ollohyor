import asyncio
import os
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    FSInputFile,
)
from aiogram.exceptions import TelegramBadRequest

try:
    from site_sync import sync_site_data
except Exception:
    sync_site_data = None

# =========================================================
# SO'FI OLLOHYOR O'QUV MARKAZI
# BOSS.PY — O'QUVCHI BOTI
# =========================================================

# O'QUVCHI BOT tokeni.
BOT_TOKEN = "8972189009:AAFPKtRJbXeUduUsUn_oC1EQWQguu_Zl8EM"

# ADMIN BOT bilan BIR XIL DATABASE.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "sofi_ollohyor.db"
LOCAL_PREFIX = "LOCALFILE::"
MEDIA_DIR = BASE_DIR / "shared_media"

dp = Dispatcher(storage=MemoryStorage())


# =========================================================
# DATABASE
# =========================================================

def connect():
    con = sqlite3.connect(str(DB_PATH), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def media_input(value):
    """LOCALFILE path bo'lsa FSInputFile, eski Telegram file_id bo'lsa string qaytaradi."""
    if not value:
        return None
    if isinstance(value, str) and value.startswith(LOCAL_PREFIX):
        rel = value[len(LOCAL_PREFIX):]
        path = BASE_DIR / Path(rel)
        if path.exists():
            return FSInputFile(path)
        return None
    return value


def init_db():
    con = connect()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            username TEXT,
            class_name TEXT DEFAULT '',
            score INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL DEFAULT 'document'
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            teacher TEXT DEFAULT '',
            teacher_photo TEXT DEFAULT '',
            price TEXT DEFAULT '',
            certificates TEXT DEFAULT '',
            results TEXT DEFAULT '',
            description TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'Yangi'
        );
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct TEXT NOT NULL DEFAULT '?',
            points INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subject_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER UNIQUE NOT NULL,
            class_name TEXT DEFAULT '',
            schedule TEXT DEFAULT '',
            duration TEXT DEFAULT '',
            room TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS book_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER UNIQUE NOT NULL,
            class_name TEXT DEFAULT '',
            teacher TEXT DEFAULT '',
            author TEXT DEFAULT '',
            description TEXT DEFAULT '',
            photo_file_id TEXT DEFAULT '',
            order_no INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS exam_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER UNIQUE NOT NULL,
            class_name TEXT DEFAULT '',
            teacher TEXT DEFAULT '',
            duration INTEGER DEFAULT 30,
            description TEXT DEFAULT '',
            pdf_file_id TEXT DEFAULT '',
            pdf_path TEXT DEFAULT ''
        );
    """)
    con.commit()
    con.close()


def save_user(message: Message):
    con = connect()
    try:
        con.execute("""
            INSERT INTO users (telegram_id, full_name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name=excluded.full_name,
                username=excluded.username
        """, (message.from_user.id, message.from_user.full_name, message.from_user.username or ""))
        con.commit()
    finally:
        con.close()


# =========================================================
# USER MENU — ADMIN BOTDAGI USER BO'LIMLARI BILAN BIR XIL
# =========================================================

def main_menu():
    # Admin bot bilan umumiy foydalanuvchi tugmalari bir xil.
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Darsliklar"), KeyboardButton(text="📝 Imtihonlar")],
            [KeyboardButton(text="🏆 O'quvchilar reytingi")],
            [KeyboardButton(text="📖 O'quv markaz fanlari")],
            [KeyboardButton(text="📝 Arizalar")],
            [KeyboardButton(text="🏠 Bosh menyu")],
        ],
        resize_keyboard=True,
    )


def back_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Bosh menyu")]],
        resize_keyboard=True,
    )


class RegistrationState(StatesGroup):
    phone = State()


class TakeExam(StatesGroup):
    answering = State()


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    init_db()
    save_user(message)
    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "📚 SO'FI OLLOHYOR O'QUV MARKAZI\n\n"
        "Kerakli bo'limni tanlang:",
        reply_markup=main_menu(),
    )


@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.", reply_markup=main_menu())


@dp.message(F.text == "🏠 Bosh menyu")
async def home(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Bosh menyu:", reply_markup=main_menu())


# =========================================================
# DARSLIKLAR + RASM
# =========================================================

@dp.message(F.text == "📚 Darsliklar")
async def books_menu(message: Message):
    con = connect()
    try:
        rows = con.execute("SELECT DISTINCT subject FROM books ORDER BY subject").fetchall()
    finally:
        con.close()

    if not rows:
        await message.answer("📚 Hozircha darsliklar yo'q.", reply_markup=back_menu())
        return

    buttons = [[InlineKeyboardButton(text=f"📘 {r['subject']}", callback_data=f"book_subject:{r['subject']}")] for r in rows]
    await message.answer("📚 Fanni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("book_subject:"))
async def book_subject(call: CallbackQuery):
    subject = call.data.split(":", 1)[1]
    con = connect()
    try:
        rows = con.execute("""
            SELECT b.id, b.title, p.class_name
            FROM books b LEFT JOIN book_profiles p ON p.book_id=b.id
            WHERE b.subject=?
            ORDER BY COALESCE(p.order_no,0), b.id DESC
        """, (subject,)).fetchall()
    finally:
        con.close()

    buttons = [[InlineKeyboardButton(
        text=f"📕 {r['title']}" + (f" — {r['class_name']}" if r['class_name'] else ""),
        callback_data=f"book:{r['id']}"
    )] for r in rows]

    await call.message.edit_text(f"📚 {subject}\n\nDarslikni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()


@dp.callback_query(F.data.startswith("book:"))
async def send_book(call: CallbackQuery):
    book_id = int(call.data.split(":")[1])
    con = connect()
    try:
        row = con.execute("""
            SELECT b.title, b.file_id, b.file_type,
                   p.photo_file_id, p.description, p.author,
                   p.class_name, p.teacher
            FROM books b LEFT JOIN book_profiles p ON p.book_id=b.id
            WHERE b.id=?
        """, (book_id,)).fetchone()
    finally:
        con.close()

    if not row:
        await call.answer("Darslik topilmadi.", show_alert=True)
        return

    caption = (
        f"📕 <b>{row['title']}</b>\n"
        f"🏫 Sinf: {row['class_name'] or '—'}\n"
        f"👨‍🏫 O'qituvchi: {row['teacher'] or '—'}\n"
        f"✍️ Muallif: {row['author'] or '—'}\n"
        f"ℹ️ {row['description'] or '—'}"
    )

    photo = media_input(row['photo_file_id'])
    if photo:
        try:
            await call.message.answer_photo(photo, caption=caption)
        except TelegramBadRequest:
            # Eski yozuv Telegram file_id ko'rinishida bo'lishi mumkin.
            await call.message.answer(caption + "\n\n⚠️ Eski rasmni qayta yuklash kerak.")

    document = media_input(row['file_id'])
    if document:
        try:
            await call.message.answer_document(
                document,
                caption=f"📎 {row['title']}"
            )
        except TelegramBadRequest:
            await call.message.answer(
                f"📎 {row['title']}\n\n⚠️ Eski faylni qayta yuklash kerak."
            )
    else:
        await call.message.answer("❌ Darslik fayli topilmadi. Admin qayta yuklashi kerak.")

    await call.answer()


# =========================================================
# FANLAR + O'QITUVCHI RASMI
# =========================================================

@dp.message(F.text == "📖 O'quv markaz fanlari")
async def subjects_menu(message: Message):
    con = connect()
    try:
        rows = con.execute("SELECT id, name FROM subjects ORDER BY id").fetchall()
    finally:
        con.close()

    if not rows:
        await message.answer("📖 Hozircha fanlar yo'q.", reply_markup=back_menu())
        return

    buttons = [[InlineKeyboardButton(text=f"📖 {r['name']}", callback_data=f"subject:{r['id']}")] for r in rows]
    await message.answer("📖 O'quv markaz fanlari:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("subject:"))
async def subject_info(call: CallbackQuery):
    subject_id = int(call.data.split(":")[1])
    con = connect()
    try:
        row = con.execute("""
            SELECT s.name, s.teacher, s.teacher_photo, s.price,
                   s.certificates, s.results, s.description,
                   p.class_name, p.schedule, p.duration, p.room
            FROM subjects s
            LEFT JOIN subject_profiles p ON p.subject_id=s.id
            WHERE s.id=?
        """, (subject_id,)).fetchone()
    finally:
        con.close()

    if not row:
        await call.answer("Fan topilmadi.", show_alert=True)
        return

    text = (
        f"📖 <b>{row['name']}</b>\n\n"
        f"👨‍🏫 O'qituvchi: {row['teacher'] or '—'}\n"
        f"🏫 Sinf: {row['class_name'] or '—'}\n"
        f"💰 Narx: {row['price'] or '—'}\n"
        f"🗓 Jadval: {row['schedule'] or '—'}\n"
        f"⏱ Davomiyligi: {row['duration'] or '—'}\n"
        f"🚪 Xona: {row['room'] or '—'}\n"
        f"🏅 Sertifikat: {row['certificates'] or '—'}\n"
        f"📈 Natijalar: {row['results'] or '—'}\n"
        f"ℹ️ {row['description'] or '—'}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📝 Darsga yozilish", callback_data=f"join:{subject_id}")
    ]])

    photo = media_input(row['teacher_photo'])
    if photo:
        try:
            await call.message.answer_photo(
                photo,
                caption=text,
                reply_markup=kb
            )
        except TelegramBadRequest:
            await call.message.answer(
                text + "\n\n⚠️ Eski rasmni qayta yuklash kerak.",
                reply_markup=kb
            )
    else:
        await call.message.answer(
            text,
            reply_markup=kb
        )
    await call.answer()


# =========================================================
# RO'YXATDAN O'TISH
# =========================================================

@dp.callback_query(F.data.startswith("join:"))
async def join(call: CallbackQuery, state: FSMContext):
    subject_id = int(call.data.split(":")[1])
    await state.update_data(subject_id=subject_id)
    await state.set_state(RegistrationState.phone)
    await call.message.answer("📞 Telefon raqamingizni yuboring. Masalan: +998901234567")
    await call.answer()


@dp.message(RegistrationState.phone)
async def register_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    con = connect()
    try:
        con.execute("INSERT INTO registrations(telegram_id, subject_id, phone) VALUES (?, ?, ?)", (message.from_user.id, data['subject_id'], message.text.strip()))
        con.commit()
    finally:
        con.close()
    await state.clear()
    await message.answer("✅ Arizangiz qabul qilindi.", reply_markup=main_menu())


# =========================================================
# MENING ARIZALARIM
# =========================================================

@dp.message(F.text == "📝 Arizalar")
async def my_applications(message: Message):
    con = connect()
    try:
        rows = con.execute("""
            SELECT r.id, r.phone, r.status,
                   s.name AS subject_name
            FROM registrations r
            LEFT JOIN subjects s ON s.id=r.subject_id
            WHERE r.telegram_id=?
            ORDER BY r.id DESC
            LIMIT 20
        """, (message.from_user.id,)).fetchall()
    finally:
        con.close()

    if not rows:
        await message.answer(
            "📝 Sizda hozircha ariza yo'q.",
            reply_markup=main_menu()
        )
        return

    text = "📝 <b>MENING ARIZALARIM</b>\n\n"
    for row in rows:
        status = row["status"] or "Yangi"
        text += (
            f"#{row['id']}\n"
            f"📖 Fan: {row['subject_name'] or "Fan o'chirilgan"}\n"
            f"📞 Telefon: {row['phone']}\n"
            f"📌 Holat: <b>{status}</b>\n\n"
        )

    await message.answer(text, reply_markup=main_menu())


# =========================================================
# IMTIHON — FAQAT ENG YANGI TEST
# =========================================================

@dp.message(F.text == "📝 Imtihonlar")
async def exams_menu(message: Message):
    con = connect()
    try:
        row = con.execute("""
            SELECT e.id, e.subject, e.title,
                   p.class_name, p.teacher, p.duration, p.description
            FROM exams e LEFT JOIN exam_profiles p ON p.exam_id=e.id
            ORDER BY e.id DESC LIMIT 1
        """).fetchone()
        count = con.execute("SELECT COUNT(*) FROM questions WHERE exam_id=(SELECT id FROM exams ORDER BY id DESC LIMIT 1)").fetchone()[0] if row else 0
    finally:
        con.close()

    if not row:
        await message.answer("📝 Hozircha imtihon yo'q.", reply_markup=back_menu())
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Imtihonni boshlash", callback_data=f"exam_start:{row['id']}")
    ]])

    await message.answer(
        f"📝 <b>{row['title']}</b>\n\n"
        f"📖 Fan: {row['subject']}\n"
        f"🏫 Sinf: {row['class_name'] or '—'}\n"
        f"👨‍🏫 O'qituvchi: {row['teacher'] or '—'}\n"
        f"⏱ Vaqt: {row['duration'] or 30} daqiqa\n"
        f"❓ Savollar: {count}\n"
        f"ℹ️ {row['description'] or '—'}",
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith("exam_start:"))
async def exam_start(call: CallbackQuery, state: FSMContext):
    exam_id = int(call.data.split(":")[1])
    con = connect()
    try:
        rows = con.execute("""
            SELECT id, question, option_a, option_b,
                   option_c, option_d, correct, points
            FROM questions WHERE exam_id=? ORDER BY id
        """, (exam_id,)).fetchall()
    finally:
        con.close()

    if not rows:
        await call.answer("Savollar yo'q.", show_alert=True); return

    # Admin javoblarni tugatmagan bo'lsa, test berilmaydi.
    if any((not r['correct']) or r['correct'] == '?' for r in rows):
        await call.answer("Bu test hali administrator tomonidan tayyorlanmoqda.", show_alert=True)
        return

    await state.set_state(TakeExam.answering)
    await state.update_data(exam_id=exam_id, questions=[dict(r) for r in rows], index=0, score=0)
    await call.message.edit_text("🚀 <b>Imtihon boshlandi!</b>\n\nA/B/C/D tugmasini tanlang.")
    await send_question(call.message, state)
    await call.answer()


async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    questions = data['questions']
    index = data['index']
    if index >= len(questions):
        await finish_exam(message, state); return

    q = questions[index]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"A) {q['option_a']}", callback_data=f"answer:{q['id']}:A")],
        [InlineKeyboardButton(text=f"B) {q['option_b']}", callback_data=f"answer:{q['id']}:B")],
        [InlineKeyboardButton(text=f"C) {q['option_c']}", callback_data=f"answer:{q['id']}:C")],
        [InlineKeyboardButton(text=f"D) {q['option_d']}", callback_data=f"answer:{q['id']}:D")],
    ])
    await message.answer(f"📝 <b>{index+1}/{len(questions)}</b>\n\n{q['question']}", reply_markup=kb)


@dp.callback_query(TakeExam.answering, F.data.startswith("answer:"))
async def answer_question(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await call.answer("Test sessiyasi topilmadi.", show_alert=True)
        return

    _, qid_text, selected = call.data.split(":")
    qid = int(qid_text)
    index = data['index']
    questions = data['questions']

    # Eski savolga qayta bosilsa, javobni qabul qilmaymiz.
    if index >= len(questions) or questions[index]['id'] != qid:
        await call.answer("Bu savol allaqachon o'tilgan.")
        return

    q = questions[index]
    score = data['score']
    points = q.get('points', 1) or 1
    is_correct = selected == q['correct']

    if is_correct:
        score += points
        await call.answer("🎉✅ BARAKALLA! To'g'ri javob!", show_alert=False)
    else:
        await call.answer(
            f"❌ Noto'g'ri. To'g'ri javob: {q['correct']}",
            show_alert=False,
        )

    # Birinchi savol va uning tugmalari chatdan o'chiriladi.
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass

    # Natijani holatda saqlab, keyingi savolga o'tamiz.
    await state.update_data(index=index + 1, score=score)

    # To'g'ri javob uchun qisqa bayramona xabar.
    result_message = None
    if is_correct:
        result_message = await call.message.answer(
            "🎉🎊 <b>BARAKALLA!</b> 🎊🎉\n"
            f"✅ {index + 1}-savol to'g'ri!\n"
            f"🏆 +{points} ball"
        )
        await asyncio.sleep(1.0)
    else:
        result_message = await call.message.answer(
            "❌ <b>Noto'g'ri javob</b>\n"
            f"To'g'ri javob: <b>{q['correct']}</b>"
        )
        await asyncio.sleep(0.8)

    # Bayram/xato xabarini ham olib tashlaymiz — ekranda faqat yangi savol qoladi.
    if result_message:
        try:
            await result_message.delete()
        except TelegramBadRequest:
            pass

    await send_question(call.message, state)


async def finish_exam(message: Message, state: FSMContext):
    data = await state.get_data()
    exam_id = data['exam_id']
    score = data['score']
    total = len(data['questions'])

    con = connect()
    try:
        con.execute("INSERT INTO results(telegram_id, exam_id, score, total) VALUES (?, ?, ?, ?)", (message.from_user.id, exam_id, score, total))
        con.execute("UPDATE users SET score=score+? WHERE telegram_id=?", (score, message.from_user.id))
        con.commit()
    finally:
        con.close()

    if sync_site_data:
        await sync_site_data(DB_PATH, BASE_DIR)
    await state.clear()
    await message.answer(
        "🏁 <b>IMTIHON YAKUNLANDI</b>\n\n"
        f"✅ Ball: <b>{score}</b>\n"
        f"❓ Savollar: <b>{total}</b>\n\n"
        "🏆 Natijangiz reytingga qo'shildi.",
        reply_markup=main_menu(),
    )


# =========================================================
# REYTING
# =========================================================

@dp.message(F.text == "🏆 O'quvchilar reytingi")
async def ranking(message: Message):
    con = connect()
    try:
        rows = con.execute("SELECT full_name, class_name, score FROM users ORDER BY score DESC, full_name ASC LIMIT 50").fetchall()
    finally:
        con.close()

    if not rows:
        await message.answer("🏆 Hali reyting yo'q.", reply_markup=back_menu())
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>O'QUVCHILAR REYTINGI</b>\n\n"
    for i, r in enumerate(rows, 1):
        prefix = medals[i-1] if i <= 3 else f"{i}."
        text += f"{prefix} {r['full_name']} — {r['score']} ball | {r["class_name"] or "Sinf ko'rsatilmagan"}\n"
    await message.answer(text, reply_markup=back_menu())


# =========================================================
# FALLBACK / RUN
# =========================================================

@dp.message()
async def fallback(message: Message):
    await message.answer("Menyudan kerakli bo'limni tanlang.", reply_markup=main_menu())


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOSS_BOT_TOKEN muhit o'zgaruvchisini kiriting.")
    init_db()
    print("========================================")
    print("SO'FI OLLOHYOR O'QUVCHI BOT ISHLADI")
    print("DATABASE:", DB_PATH)
    print("MEDIA:", MEDIA_DIR)
    print("========================================")
    bot = Bot(BOT_TOKEN)

    async def periodic_site_sync():
        while True:
            try:
                if sync_site_data:
                    await sync_site_data(DB_PATH, BASE_DIR)
            except Exception:
                import logging
                logging.exception("Periodic site sync xatosi")
            await asyncio.sleep(60)

    sync_task = asyncio.create_task(periodic_site_sync())
    try:
        await dp.start_polling(bot)
    finally:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
