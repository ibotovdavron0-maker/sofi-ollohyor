import asyncio
import logging
import re
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
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pypdf import PdfReader

try:
    from site_sync import sync_site_data
except Exception:
    sync_site_data = None

try:
    import fitz  # PyMuPDF, optional OCR fallback
except ImportError:
    fitz = None

try:
    import pytesseract  # optional OCR
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

# =========================================================
# SO'FI OLLOHYOR O'QUV MARKAZI
# ADMIN BOT
# =========================================================

# BotFather'dan YANGI admin bot tokenini kiriting.
BOT_TOKEN = "7914377374:AAHeZX9lq8hZQ_M1CgIulT9WltALKz7MzRE"

# O'z Telegram ID'ingizni yozing.
ADMIN_IDS = {5319789884}

# IKKALA BOT HAM SHU BITTA DATABASE'DAN FOYDALANADI.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "sofi_ollohyor.db"
PDF_DIR = BASE_DIR / "admin_pdfs"
PDF_DIR.mkdir(exist_ok=True)

# IKKALA BOT UCHUN UMUMIY MEDIA PAPKA.
MEDIA_DIR = BASE_DIR / "shared_media"
for _folder in ("teachers", "students", "subjects", "books"):
    (MEDIA_DIR / _folder).mkdir(parents=True, exist_ok=True)

LOCAL_PREFIX = "LOCALFILE::"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
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


def init_db():
    con = connect()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            username TEXT,
            class_name TEXT DEFAULT '',
            score INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL DEFAULT 'document'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            teacher TEXT DEFAULT '',
            teacher_photo TEXT DEFAULT '',
            price TEXT DEFAULT '',
            certificates TEXT DEFAULT '',
            results TEXT DEFAULT '',
            description TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'Yangi'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL
        )
    """)

    cur.execute("""
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
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            subject TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            experience TEXT DEFAULT '',
            education TEXT DEFAULT '',
            certificates TEXT DEFAULT '',
            achievements TEXT DEFAULT '',
            results TEXT DEFAULT '',
            description TEXT DEFAULT '',
            photo_file_id TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            full_name TEXT NOT NULL,
            birth_date TEXT DEFAULT '',
            class_name TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            teacher TEXT DEFAULT '',
            group_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            parent_phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            admission_date TEXT DEFAULT '',
            description TEXT DEFAULT '',
            photo_file_id TEXT DEFAULT ''
        )
    """)

    # Eski students jadvalida photo_file_id bo'lmasa, qo'shamiz.
    cols = {row[1] for row in cur.execute("PRAGMA table_info(students)").fetchall()}
    if "photo_file_id" not in cols:
        cur.execute("ALTER TABLE students ADD COLUMN photo_file_id TEXT DEFAULT ''")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subject_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER UNIQUE NOT NULL,
            class_name TEXT DEFAULT '',
            schedule TEXT DEFAULT '',
            duration TEXT DEFAULT '',
            room TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS book_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER UNIQUE NOT NULL,
            class_name TEXT DEFAULT '',
            teacher TEXT DEFAULT '',
            author TEXT DEFAULT '',
            description TEXT DEFAULT '',
            photo_file_id TEXT DEFAULT '',
            order_no INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exam_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER UNIQUE NOT NULL,
            class_name TEXT DEFAULT '',
            teacher TEXT DEFAULT '',
            duration INTEGER DEFAULT 30,
            description TEXT DEFAULT '',
            pdf_file_id TEXT DEFAULT '',
            pdf_path TEXT DEFAULT ''
        )
    """)

    con.commit()
    con.close()


# =========================================================
# HELPERS
# =========================================================

def admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def text_of(message: Message) -> str:
    return (message.text or "").strip()


async def save_shared_file(bot: Bot, file_id: str, folder: str, filename: str) -> str:
    """Telegram faylini admin botning file_id si emas, umumiy disk fayli sifatida saqlaydi.
    Bu kerak, chunki Telegram file_id boshqa bot tokenida qayta ishlatilmaydi.
    """
    target_dir = MEDIA_DIR / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    tg_file = await bot.get_file(file_id)
    await bot.download_file(tg_file.file_path, destination=target)
    rel = target.relative_to(BASE_DIR).as_posix()
    return LOCAL_PREFIX + rel


async def migrate_legacy_media(bot: Bot):
    """Eski yozuvlardagi Telegram file_id larni umumiy disk fayliga o'tkazishga urinadi."""
    migrated = 0
    failed = 0
    con = connect()
    try:
        jobs = [
            ("teachers", "SELECT id, photo_file_id FROM teachers WHERE photo_file_id<>''", "photo_file_id", "teachers", "legacy_teacher_{id}.jpg"),
            ("students", "SELECT id, photo_file_id FROM students WHERE photo_file_id<>''", "photo_file_id", "students", "legacy_student_{id}.jpg"),
            ("subjects", "SELECT id, teacher_photo FROM subjects WHERE teacher_photo<>''", "teacher_photo", "subjects", "legacy_subject_{id}.jpg"),
            ("book_photos", "SELECT id, photo_file_id FROM book_profiles WHERE photo_file_id<>''", "photo_file_id", "books", "legacy_book_photo_{id}.jpg"),
            ("books", "SELECT id, file_id FROM books WHERE file_id<>''", "file_id", "books", "legacy_book_{id}.file"),
        ]
        for label, sql, column, folder, pattern in jobs:
            rows = con.execute(sql).fetchall()
            for row in rows:
                value = row[column]
                if not value or value.startswith(LOCAL_PREFIX):
                    continue
                try:
                    saved = await save_shared_file(
                        bot, value, folder, pattern.format(id=row['id'])
                    )
                    con.execute(
                        f"UPDATE {'book_profiles' if label == 'book_photos' else label} SET {column}=? WHERE id=?",
                        (saved, row['id'])
                    )
                    migrated += 1
                except Exception as exc:
                    failed += 1
                    logging.warning("Legacy media %s #%s: %s", label, row['id'], exc)
        con.commit()
    finally:
        con.close()
    logging.info("Legacy media migration: migrated=%s failed=%s", migrated, failed)


def menu():
    # Boss botdagi asosiy foydalanuvchi tugmalari bilan bir xil.
    # Admin uchun qo'shimcha: Arizalar va Admin boshqaruv.
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Darsliklar"), KeyboardButton(text="📝 Imtihonlar")],
            [KeyboardButton(text="🏆 O'quvchilar reytingi")],
            [KeyboardButton(text="📖 O'quv markaz fanlari")],
            [KeyboardButton(text="📝 Arizalar")],
            [KeyboardButton(text="🔐 Admin boshqaruv")],
            [KeyboardButton(text="🏠 Bosh menyu")],
        ],
        resize_keyboard=True,
    )


def admin_tools_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Darslik qo'shish"), KeyboardButton(text="🗑 Darslik o'chirish")],
            [KeyboardButton(text="➕ Fan qo'shish"), KeyboardButton(text="🗑 Fan o'chirish")],
            [KeyboardButton(text="➕ Test yaratish"), KeyboardButton(text="➕ Savol qo'shish")],
            [KeyboardButton(text="🗑 Test o'chirish")],
            [KeyboardButton(text="👨‍🏫 O'qituvchilar"), KeyboardButton(text="👨‍🎓 O'quvchilar")],
            [KeyboardButton(text="📊 Hisobot")],
            [KeyboardButton(text="⬅️ Asosiy menyu")],
        ],
        resize_keyboard=True,
    )


def confirm_kb(callback_data: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Saqlash", callback_data=callback_data),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_all"),
        ]]
    )


def correct_kb(question_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="A", callback_data=f"correct:{question_id}:A"),
            InlineKeyboardButton(text="B", callback_data=f"correct:{question_id}:B"),
            InlineKeyboardButton(text="C", callback_data=f"correct:{question_id}:C"),
            InlineKeyboardButton(text="D", callback_data=f"correct:{question_id}:D"),
        ]]
    )


# =========================================================
# FSM
# =========================================================

class TeacherAdd(StatesGroup):
    full_name = State(); subject = State(); phone = State(); experience = State()
    education = State(); certificates = State(); achievements = State()
    results = State(); description = State(); photo = State()


class StudentAdd(StatesGroup):
    telegram_id = State(); full_name = State(); birth_date = State(); class_name = State()
    subject = State(); teacher = State(); group_name = State(); phone = State()
    parent_phone = State(); address = State(); admission_date = State()
    description = State(); photo = State()


class SubjectAdd(StatesGroup):
    name = State(); class_name = State(); teacher = State(); photo = State()
    price = State(); certificates = State(); results = State(); description = State()
    schedule = State(); duration = State(); room = State()


class BookAdd(StatesGroup):
    subject = State(); title = State(); class_name = State(); teacher = State()
    author = State(); description = State(); file = State(); photo = State(); order_no = State()


class ExamAdd(StatesGroup):
    title = State(); class_name = State(); subject = State(); teacher = State()
    duration = State(); description = State(); pdf = State()


class MissingAnswers(StatesGroup):
    choosing = State()


# =========================================================
# START / CANCEL
# =========================================================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    if not admin(message.from_user.id):
        await message.answer("⛔ Bu bot faqat administrator uchun.")
        return
    await message.answer(
        "👑 <b>SO'FI OLLOHYOR ADMIN BOT</b>\n\n"
        "Har bir bo'limda bot ma'lumotlarni ketma-ket so'raydi.",
        reply_markup=menu(),
    )


@dp.message(Command("admin"))
async def admin_cmd(message: Message, state: FSMContext):
    if not admin(message.from_user.id):
        await message.answer("⛔ Siz admin emassiz.")
        return
    await state.clear()
    await message.answer("👑 Admin panel:", reply_markup=menu())


@dp.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext):
    if not admin(message.from_user.id):
        return
    data = await state.get_data()
    if data.get("pdf_path"):
        Path(data["pdf_path"]).unlink(missing_ok=True)
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=menu())


@dp.callback_query(F.data == "cancel_all")
async def cancel_all(call: CallbackQuery, state: FSMContext):
    if not admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    data = await state.get_data()
    if data.get("pdf_path"):
        Path(data["pdf_path"]).unlink(missing_ok=True)
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.message.answer("👑 Admin panel:", reply_markup=menu())
    await call.answer()


@dp.message(F.text == "🏠 Bosh menyu")
async def home(message: Message, state: FSMContext):
    if not admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🏠 Asosiy menyu:", reply_markup=menu())


@dp.message(F.text == "🔐 Admin boshqaruv")
async def admin_tools(message: Message, state: FSMContext):
    if not admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "🔐 <b>ADMIN BOSHQARUV</b>\n\n"
        "Ma'lumot qo'shish, o'chirish va hisobot:",
        reply_markup=admin_tools_menu()
    )


@dp.message(F.text == "⬅️ Asosiy menyu")
async def back_to_main(message: Message, state: FSMContext):
    if not admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🏠 Asosiy menyu:", reply_markup=menu())


# =========================================================
# O'QITUVCHI
# =========================================================

@dp.message(F.text == "👨‍🏫 O'qituvchilar")
async def teacher_menu(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.clear()
    await message.answer(
        "👨‍🏫 O'qituvchilar",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Qo'shish", callback_data="teacher_add")],
            [InlineKeyboardButton(text="📋 Ko'rish", callback_data="teacher_list")],
        ])
    )


@dp.callback_query(F.data == "teacher_add")
async def teacher_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(TeacherAdd.full_name)
    await call.message.edit_text("1/10 — O'qituvchi ism-familiyasi:")
    await call.answer()


@dp.message(TeacherAdd.full_name)
async def teacher_name(message: Message, state: FSMContext):
    await state.update_data(full_name=text_of(message)); await state.set_state(TeacherAdd.subject)
    await message.answer("2/10 — Qaysi fandan dars beradi?")


@dp.message(TeacherAdd.subject)
async def teacher_subj(message: Message, state: FSMContext):
    await state.update_data(subject=text_of(message)); await state.set_state(TeacherAdd.phone)
    await message.answer("3/10 — Telefon raqami:")


@dp.message(TeacherAdd.phone)
async def teacher_ph(message: Message, state: FSMContext):
    await state.update_data(phone=text_of(message)); await state.set_state(TeacherAdd.experience)
    await message.answer("4/10 — Tajribasi:")


@dp.message(TeacherAdd.experience)
async def teacher_exp(message: Message, state: FSMContext):
    await state.update_data(experience=text_of(message)); await state.set_state(TeacherAdd.education)
    await message.answer("5/10 — Ma'lumoti / universiteti:")


@dp.message(TeacherAdd.education)
async def teacher_edu(message: Message, state: FSMContext):
    await state.update_data(education=text_of(message)); await state.set_state(TeacherAdd.certificates)
    await message.answer("6/10 — Sertifikatlari:")


@dp.message(TeacherAdd.certificates)
async def teacher_certs(message: Message, state: FSMContext):
    await state.update_data(certificates=text_of(message)); await state.set_state(TeacherAdd.achievements)
    await message.answer("7/10 — Yutuqlari:")


@dp.message(TeacherAdd.achievements)
async def teacher_ach(message: Message, state: FSMContext):
    await state.update_data(achievements=text_of(message)); await state.set_state(TeacherAdd.results)
    await message.answer("8/10 — O'quvchilar natijalari:")


@dp.message(TeacherAdd.results)
async def teacher_results(message: Message, state: FSMContext):
    await state.update_data(results=text_of(message)); await state.set_state(TeacherAdd.description)
    await message.answer("9/10 — O'qituvchi haqida batafsil ma'lumot:")


@dp.message(TeacherAdd.description)
async def teacher_desc(message: Message, state: FSMContext):
    await state.update_data(description=text_of(message)); await state.set_state(TeacherAdd.photo)
    await message.answer("10/10 — O'qituvchi rasmini yuboring. Rasm bo'lmasa /skip:")


async def teacher_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(
        "👨‍🏫 <b>TEKSHIRISH</b>\n\n"
        f"Ism: {data['full_name']}\nFan: {data['subject']}\nTelefon: {data['phone']}\n"
        f"Tajriba: {data['experience']}\nMa'lumoti: {data['education']}\n"
        f"Sertifikat: {data['certificates']}\nYutuq: {data['achievements']}\n"
        f"Natija: {data['results']}\nIzoh: {data['description']}\n"
        f"Rasm: {'✅' if data.get('photo') else '❌'}\n\nSaqlaymizmi?",
        reply_markup=confirm_kb("teacher_save")
    )


@dp.message(TeacherAdd.photo, F.photo)
async def teacher_photo(message: Message, state: FSMContext, bot: Bot):
    try:
        saved = await save_shared_file(
            bot,
            message.photo[-1].file_id,
            "teachers",
            f"{message.from_user.id}_{message.message_id}.jpg"
        )
        await state.update_data(photo=saved)
        await teacher_preview(message, state)
    except Exception as exc:
        logging.exception("O'qituvchi rasmi saqlanmadi: %s", exc)
        await message.answer("❌ Rasmni saqlashda xato. Qayta yuboring.")


@dp.message(TeacherAdd.photo, F.text == "/skip")
async def teacher_no_photo(message: Message, state: FSMContext):
    await state.update_data(photo="")
    await teacher_preview(message, state)


@dp.callback_query(F.data == "teacher_save")
async def teacher_save(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    con = connect()
    try:
        con.execute("""
            INSERT INTO teachers
            (full_name, subject, phone, experience, education, certificates,
             achievements, results, description, photo_file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["full_name"], data["subject"], data["phone"], data["experience"],
            data["education"], data["certificates"], data["achievements"],
            data["results"], data["description"], data.get("photo", "")
        ))
        con.commit()
    finally:
        con.close()
    await state.clear()
    await call.message.edit_text("✅ O'qituvchi saqlandi.")
    await call.message.answer("👑 Admin panel:", reply_markup=menu())
    await call.answer()


@dp.callback_query(F.data == "teacher_list")
async def teacher_list(call: CallbackQuery):
    con = connect()
    try:
        rows = con.execute("SELECT * FROM teachers ORDER BY id DESC LIMIT 100").fetchall()
    finally:
        con.close()
    if not rows:
        await call.message.edit_text("O'qituvchilar yo'q.")
        await call.answer(); return
    text = "👨‍🏫 <b>O'QITUVCHILAR</b>\n\n"
    for r in rows:
        text += f"#{r['id']} — <b>{r['full_name']}</b> | {r['subject'] or '—'}\n📞 {r['phone'] or '—'} | Rasm: {'✅' if r['photo_file_id'] else '❌'}\n\n"
    await call.message.edit_text(text); await call.answer()


# =========================================================
# O'QUVCHI
# =========================================================

@dp.message(F.text == "👨‍🎓 O'quvchilar")
async def student_menu(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.clear()
    await message.answer(
        "👨‍🎓 O'quvchilar",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Qo'shish", callback_data="student_add")],
            [InlineKeyboardButton(text="📋 Ko'rish", callback_data="student_list")],
        ])
    )


@dp.callback_query(F.data == "student_add")
async def student_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(StudentAdd.telegram_id)
    await call.message.edit_text("1/13 — Telegram ID (bilmasangiz -):")
    await call.answer()


@dp.message(StudentAdd.telegram_id)
async def student_tgid(message: Message, state: FSMContext):
    value = text_of(message)
    if value == "-":
        tg = None
    else:
        try: tg = int(value)
        except ValueError:
            await message.answer("❌ Telegram ID raqam bo'lishi kerak yoki -."); return
    await state.update_data(telegram_id=tg); await state.set_state(StudentAdd.full_name)
    await message.answer("2/13 — Ism-familiya:")


@dp.message(StudentAdd.full_name)
async def student_name(message: Message, state: FSMContext):
    await state.update_data(full_name=text_of(message)); await state.set_state(StudentAdd.birth_date)
    await message.answer("3/13 — Tug'ilgan sana:")


@dp.message(StudentAdd.birth_date)
async def student_birth(message: Message, state: FSMContext):
    await state.update_data(birth_date=text_of(message)); await state.set_state(StudentAdd.class_name)
    await message.answer("4/13 — Qaysi sinf?")


@dp.message(StudentAdd.class_name)
async def student_class(message: Message, state: FSMContext):
    await state.update_data(class_name=text_of(message)); await state.set_state(StudentAdd.subject)
    await message.answer("5/13 — Qaysi fan?")


@dp.message(StudentAdd.subject)
async def student_subject(message: Message, state: FSMContext):
    await state.update_data(subject=text_of(message)); await state.set_state(StudentAdd.teacher)
    await message.answer("6/13 — Qaysi o'qituvchi?")


@dp.message(StudentAdd.teacher)
async def student_teacher(message: Message, state: FSMContext):
    await state.update_data(teacher=text_of(message)); await state.set_state(StudentAdd.group_name)
    await message.answer("7/13 — Qaysi guruh?")


@dp.message(StudentAdd.group_name)
async def student_group(message: Message, state: FSMContext):
    await state.update_data(group_name=text_of(message)); await state.set_state(StudentAdd.phone)
    await message.answer("8/13 — O'quvchi telefoni:")


@dp.message(StudentAdd.phone)
async def student_phone(message: Message, state: FSMContext):
    await state.update_data(phone=text_of(message)); await state.set_state(StudentAdd.parent_phone)
    await message.answer("9/13 — Ota-ona telefoni:")


@dp.message(StudentAdd.parent_phone)
async def student_parent(message: Message, state: FSMContext):
    await state.update_data(parent_phone=text_of(message)); await state.set_state(StudentAdd.address)
    await message.answer("10/13 — Manzil:")


@dp.message(StudentAdd.address)
async def student_address(message: Message, state: FSMContext):
    await state.update_data(address=text_of(message)); await state.set_state(StudentAdd.admission_date)
    await message.answer("11/13 — Qabul qilingan sana:")


@dp.message(StudentAdd.admission_date)
async def student_admission(message: Message, state: FSMContext):
    await state.update_data(admission_date=text_of(message)); await state.set_state(StudentAdd.description)
    await message.answer("12/13 — Qo'shimcha ma'lumot (bo'lmasa -):")


@dp.message(StudentAdd.description)
async def student_desc(message: Message, state: FSMContext):
    await state.update_data(description=text_of(message)); await state.set_state(StudentAdd.photo)
    await message.answer("13/13 — O'quvchi rasmini yuboring. Rasm bo'lmasa /skip:")


async def student_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    text = (
        "👨‍🎓 <b>TEKSHIRISH</b>\n\n"
        f"Telegram ID: {data['telegram_id'] or '—'}\nIsm: {data['full_name']}\n"
        f"Tug'ilgan sana: {data['birth_date']}\nSinf: {data['class_name']}\n"
        f"Fan: {data['subject']}\nO'qituvchi: {data['teacher']}\nGuruh: {data['group_name']}\n"
        f"Telefon: {data['phone']}\nOta-ona: {data['parent_phone']}\nManzil: {data['address']}\n"
        f"Qabul: {data['admission_date']}\nIzoh: {data['description']}\n"
        f"Rasm: {'✅' if data.get('photo') else '❌'}\n\nSaqlaymizmi?"
    )
    await message.answer(text, reply_markup=confirm_kb("student_save"))


@dp.message(StudentAdd.photo, F.photo)
async def student_photo(message: Message, state: FSMContext, bot: Bot):
    try:
        saved = await save_shared_file(
            bot,
            message.photo[-1].file_id,
            "students",
            f"{message.from_user.id}_{message.message_id}.jpg"
        )
        await state.update_data(photo=saved)
        await student_preview(message, state)
    except Exception as exc:
        logging.exception("O'quvchi rasmi saqlanmadi: %s", exc)
        await message.answer("❌ Rasmni saqlashda xato. Qayta yuboring.")


@dp.message(StudentAdd.photo, F.text == "/skip")
async def student_no_photo(message: Message, state: FSMContext):
    await state.update_data(photo="")
    await student_preview(message, state)


@dp.callback_query(F.data == "student_save")
async def student_save(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    con = connect()
    try:
        con.execute("""
            INSERT INTO students
            (telegram_id, full_name, birth_date, class_name, subject, teacher,
             group_name, phone, parent_phone, address, admission_date,
             description, photo_file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["telegram_id"], data["full_name"], data["birth_date"], data["class_name"],
            data["subject"], data["teacher"], data["group_name"], data["phone"],
            data["parent_phone"], data["address"], data["admission_date"],
            data["description"], data.get("photo", "")
        ))

        if data["telegram_id"] is not None:
            con.execute("""
                INSERT INTO users (telegram_id, full_name, username, class_name)
                VALUES (?, ?, '', ?)
                ON CONFLICT(telegram_id)
                DO UPDATE SET full_name=excluded.full_name, class_name=excluded.class_name
            """, (data["telegram_id"], data["full_name"], data["class_name"]))

        con.commit()
    finally:
        con.close()
    await state.clear()
    await call.message.edit_text("✅ O'quvchi saqlandi.")
    await call.message.answer("👑 Admin panel:", reply_markup=menu())
    await call.answer()


@dp.callback_query(F.data == "student_list")
async def student_list(call: CallbackQuery):
    con = connect()
    try:
        rows = con.execute("SELECT * FROM students ORDER BY id DESC LIMIT 100").fetchall()
    finally:
        con.close()
    if not rows:
        await call.message.edit_text("O'quvchilar yo'q."); await call.answer(); return
    text = "👨‍🎓 <b>O'QUVCHILAR</b>\n\n"
    for r in rows:
        text += f"#{r['id']} — <b>{r['full_name']}</b> | {r['class_name'] or '—'} | {r['subject'] or '—'} | Rasm: {'✅' if r['photo_file_id'] else '❌'}\n"
    await call.message.edit_text(text); await call.answer()


# =========================================================
# FANLAR
# =========================================================

@dp.message(F.text == "📖 O'quv markaz fanlari")
async def subject_menu(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.clear()
    await message.answer(
        "📖 Fanlar",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Fan qo'shish", callback_data="subject_add")],
            [InlineKeyboardButton(text="📋 Fanlar", callback_data="subject_list")],
        ])
    )


@dp.callback_query(F.data == "subject_add")
async def subject_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(SubjectAdd.name); await call.message.edit_text("1/11 — Fan nomi:"); await call.answer()


@dp.message(SubjectAdd.name)
async def subject_name(message: Message, state: FSMContext):
    await state.update_data(name=text_of(message)); await state.set_state(SubjectAdd.class_name); await message.answer("2/11 — Qaysi sinf/sinflar uchun?")


@dp.message(SubjectAdd.class_name)
async def subject_class(message: Message, state: FSMContext):
    await state.update_data(class_name=text_of(message)); await state.set_state(SubjectAdd.teacher); await message.answer("3/11 — Qaysi o'qituvchi?")


@dp.message(SubjectAdd.teacher)
async def subject_teacher(message: Message, state: FSMContext):
    await state.update_data(teacher=text_of(message)); await state.set_state(SubjectAdd.photo); await message.answer("4/11 — O'qituvchi rasmini yuboring. Rasm bo'lmasa /skip:")


@dp.message(SubjectAdd.photo, F.photo)
async def subject_photo(message: Message, state: FSMContext, bot: Bot):
    try:
        saved = await save_shared_file(
            bot,
            message.photo[-1].file_id,
            "subjects",
            f"{message.from_user.id}_{message.message_id}.jpg"
        )
        await state.update_data(photo=saved)
        await state.set_state(SubjectAdd.price)
        await message.answer("5/11 — Narxi:")
    except Exception as exc:
        logging.exception("Fan rasmi saqlanmadi: %s", exc)
        await message.answer("❌ Rasmni saqlashda xato. Qayta yuboring.")


@dp.message(SubjectAdd.photo, F.text == "/skip")
async def subject_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo=""); await state.set_state(SubjectAdd.price); await message.answer("5/11 — Narxi:")


@dp.message(SubjectAdd.price)
async def subject_price(message: Message, state: FSMContext):
    await state.update_data(price=text_of(message)); await state.set_state(SubjectAdd.certificates); await message.answer("6/11 — Sertifikatlari:")


@dp.message(SubjectAdd.certificates)
async def subject_certificates(message: Message, state: FSMContext):
    await state.update_data(certificates=text_of(message)); await state.set_state(SubjectAdd.results); await message.answer("7/11 — Natijalari:")


@dp.message(SubjectAdd.results)
async def subject_results(message: Message, state: FSMContext):
    await state.update_data(results=text_of(message)); await state.set_state(SubjectAdd.description); await message.answer("8/11 — Fan haqida ma'lumot:")


@dp.message(SubjectAdd.description)
async def subject_description(message: Message, state: FSMContext):
    await state.update_data(description=text_of(message)); await state.set_state(SubjectAdd.schedule); await message.answer("9/11 — Dars kunlari va vaqti:")


@dp.message(SubjectAdd.schedule)
async def subject_schedule(message: Message, state: FSMContext):
    await state.update_data(schedule=text_of(message)); await state.set_state(SubjectAdd.duration); await message.answer("10/11 — Dars davomiyligi:")


@dp.message(SubjectAdd.duration)
async def subject_duration(message: Message, state: FSMContext):
    await state.update_data(duration=text_of(message)); await state.set_state(SubjectAdd.room); await message.answer("11/11 — Xona raqami / nomi:")


@dp.message(SubjectAdd.room)
async def subject_room(message: Message, state: FSMContext):
    await state.update_data(room=text_of(message))
    data = await state.get_data()
    await message.answer(
        "📖 <b>FAN TEKSHIRISH</b>\n\n"
        f"Fan: {data['name']}\nSinf: {data['class_name']}\nO'qituvchi: {data['teacher']}\n"
        f"Narx: {data['price']}\nSertifikat: {data['certificates']}\nNatija: {data['results']}\n"
        f"Tavsif: {data['description']}\nJadval: {data['schedule']}\n"
        f"Davomiyligi: {data['duration']}\nXona: {data['room']}\n"
        f"Rasm: {'✅' if data.get('photo') else '❌'}\n\nSaqlaymizmi?",
        reply_markup=confirm_kb("subject_save")
    )


@dp.callback_query(F.data == "subject_save")
async def subject_save(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    con = connect()
    try:
        cur = con.execute("""
            INSERT INTO subjects
            (name, teacher, teacher_photo, price, certificates, results, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data["name"], data["teacher"], data.get("photo", ""), data["price"],
            data["certificates"], data["results"], data["description"]
        ))
        sid = cur.lastrowid
        con.execute("""
            INSERT INTO subject_profiles
            (subject_id, class_name, schedule, duration, room)
            VALUES (?, ?, ?, ?, ?)
        """, (sid, data["class_name"], data["schedule"], data["duration"], data["room"]))
        con.commit()
    except sqlite3.IntegrityError:
        con.close(); await call.answer("Bu fan allaqachon mavjud.", show_alert=True); return
    finally:
        try: con.close()
        except Exception: pass
    await state.clear(); await call.message.edit_text("✅ Fan saqlandi."); await call.message.answer("👑 Admin panel:", reply_markup=menu()); await call.answer()


@dp.callback_query(F.data == "subject_list")
async def subject_list(call: CallbackQuery):
    con = connect()
    try:
        rows = con.execute("""
            SELECT s.id, s.name, s.teacher, s.price, s.teacher_photo,
                   p.class_name, p.schedule, p.duration, p.room
            FROM subjects s LEFT JOIN subject_profiles p ON p.subject_id=s.id
            ORDER BY s.id DESC LIMIT 100
        """).fetchall()
    finally: con.close()
    if not rows:
        await call.message.edit_text("Fanlar yo'q."); await call.answer(); return
    text = "📖 <b>FANLAR</b>\n\n"
    for r in rows:
        text += f"#{r['id']} — <b>{r['name']}</b> | {r['class_name'] or '—'} | {r['teacher'] or '—'} | {r['price'] or '—'} | Rasm: {'✅' if r['teacher_photo'] else '❌'}\n"
    await call.message.edit_text(text); await call.answer()


# =========================================================
# DARSLIK
# =========================================================

@dp.message(F.text == "📚 Darsliklar")
async def book_menu(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.clear()
    await message.answer(
        "📚 Darsliklar",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Darslik qo'shish", callback_data="book_add")],
            [InlineKeyboardButton(text="📋 Darsliklar", callback_data="book_list")],
        ])
    )


@dp.callback_query(F.data == "book_add")
async def book_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(BookAdd.subject); await call.message.edit_text("1/9 — Qaysi fan?"); await call.answer()


@dp.message(BookAdd.subject)
async def book_subject(message: Message, state: FSMContext):
    await state.update_data(subject=text_of(message)); await state.set_state(BookAdd.title); await message.answer("2/9 — Darslik nomi:")


@dp.message(BookAdd.title)
async def book_title(message: Message, state: FSMContext):
    await state.update_data(title=text_of(message)); await state.set_state(BookAdd.class_name); await message.answer("3/9 — Qaysi sinf uchun?")


@dp.message(BookAdd.class_name)
async def book_class(message: Message, state: FSMContext):
    await state.update_data(class_name=text_of(message)); await state.set_state(BookAdd.teacher); await message.answer("4/9 — Qaysi o'qituvchi uchun?")


@dp.message(BookAdd.teacher)
async def book_teacher(message: Message, state: FSMContext):
    await state.update_data(teacher=text_of(message)); await state.set_state(BookAdd.author); await message.answer("5/9 — Muallifi kim? (bo'lmasa -)")


@dp.message(BookAdd.author)
async def book_author(message: Message, state: FSMContext):
    await state.update_data(author=text_of(message)); await state.set_state(BookAdd.description); await message.answer("6/9 — Darslik haqida ma'lumot:")


@dp.message(BookAdd.description)
async def book_description(message: Message, state: FSMContext):
    await state.update_data(description=text_of(message)); await state.set_state(BookAdd.file); await message.answer("7/9 — Darslik faylini yuboring:")


@dp.message(BookAdd.file, F.document)
async def book_file(message: Message, state: FSMContext, bot: Bot):
    try:
        original = Path(message.document.file_name or "book.bin").name
        filename = f"{message.from_user.id}_{message.message_id}_{original}"
        saved = await save_shared_file(
            bot, message.document.file_id, "books", filename
        )
        await state.update_data(file_id=saved, file_type="document")
        await state.set_state(BookAdd.photo)
        await message.answer("8/9 — Darslik rasmini yuboring. Rasm bo'lmasa /skip:")
    except Exception as exc:
        logging.exception("Darslik fayli saqlanmadi: %s", exc)
        await message.answer("❌ Faylni saqlashda xato. Qayta yuboring.")


@dp.message(BookAdd.photo, F.photo)
async def book_photo(message: Message, state: FSMContext, bot: Bot):
    try:
        saved = await save_shared_file(
            bot,
            message.photo[-1].file_id,
            "books",
            f"{message.from_user.id}_{message.message_id}.jpg"
        )
        await state.update_data(photo=saved)
        await state.set_state(BookAdd.order_no)
        await message.answer("9/9 — Tartib raqami (0 bo'lishi mumkin):")
    except Exception as exc:
        logging.exception("Darslik rasmi saqlanmadi: %s", exc)
        await message.answer("❌ Rasmni saqlashda xato. Qayta yuboring.")


@dp.message(BookAdd.photo, F.text == "/skip")
async def book_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo=""); await state.set_state(BookAdd.order_no); await message.answer("9/9 — Tartib raqami (0 bo'lishi mumkin):")


@dp.message(BookAdd.order_no)
async def book_order(message: Message, state: FSMContext):
    try: n = int(text_of(message))
    except ValueError: await message.answer("❌ Butun son kiriting."); return
    if n < 0: await message.answer("❌ 0 yoki katta son kiriting."); return
    await state.update_data(order_no=n)
    data = await state.get_data()
    await message.answer(
        "📚 <b>DARSLIK TEKSHIRISH</b>\n\n"
        f"Fan: {data['subject']}\nNomi: {data['title']}\nSinf: {data['class_name']}\n"
        f"O'qituvchi: {data['teacher']}\nMuallif: {data['author']}\n"
        f"Izoh: {data['description']}\nFayl: ✅\nRasm: {'✅' if data.get('photo') else '❌'}\n"
        f"Tartib: {n}\n\nSaqlaymizmi?",
        reply_markup=confirm_kb("book_save")
    )


@dp.callback_query(F.data == "book_save")
async def book_save(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    con = connect()
    try:
        cur = con.execute("INSERT INTO books(subject, title, file_id, file_type) VALUES (?, ?, ?, 'document')", (data["subject"], data["title"], data["file_id"]))
        bid = cur.lastrowid
        con.execute("""
            INSERT INTO book_profiles
            (book_id, class_name, teacher, author, description, photo_file_id, order_no)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (bid, data["class_name"], data["teacher"], data["author"], data["description"], data.get("photo", ""), data["order_no"]))
        con.commit()
    finally: con.close()
    await state.clear(); await call.message.edit_text("✅ Darslik saqlandi."); await call.message.answer("👑 Admin panel:", reply_markup=menu()); await call.answer()


@dp.callback_query(F.data == "book_list")
async def book_list(call: CallbackQuery):
    con = connect()
    try:
        rows = con.execute("""
            SELECT b.id, b.subject, b.title, p.class_name, p.teacher,
                   p.author, p.photo_file_id
            FROM books b LEFT JOIN book_profiles p ON p.book_id=b.id
            ORDER BY COALESCE(p.order_no,0), b.id DESC LIMIT 100
        """).fetchall()
    finally: con.close()
    if not rows:
        await call.message.edit_text("Darsliklar yo'q."); await call.answer(); return
    text = "📚 <b>DARSLIKLAR</b>\n\n"
    for r in rows:
        text += f"#{r['id']} — <b>{r['title']}</b> | {r['subject']} | {r['class_name'] or '—'} | Rasm: {'✅' if r['photo_file_id'] else '❌'}\n"
    await call.message.edit_text(text); await call.answer()


# =========================================================
# IMTIHON / PDF
# =========================================================

@dp.message(F.text == "📝 Imtihonlar")
async def exam_menu(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.clear()
    await message.answer(
        "📝 Imtihonlar",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Yangi PDF test", callback_data="exam_add")],
            [InlineKeyboardButton(text="📋 Joriy test", callback_data="exam_list")],
            [InlineKeyboardButton(text="🗑 Testni o'chirish", callback_data="exam_delete_menu")],
        ])
    )


@dp.callback_query(F.data == "exam_add")
async def exam_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(ExamAdd.title); await call.message.edit_text("1/7 — Test nomi:"); await call.answer()


@dp.message(ExamAdd.title)
async def exam_title(message: Message, state: FSMContext):
    await state.update_data(title=text_of(message)); await state.set_state(ExamAdd.class_name); await message.answer("2/7 — Qaysi sinf?")


@dp.message(ExamAdd.class_name)
async def exam_class(message: Message, state: FSMContext):
    await state.update_data(class_name=text_of(message)); await state.set_state(ExamAdd.subject); await message.answer("3/7 — Qaysi fan?")


@dp.message(ExamAdd.subject)
async def exam_subject(message: Message, state: FSMContext):
    await state.update_data(subject=text_of(message)); await state.set_state(ExamAdd.teacher); await message.answer("4/7 — Qaysi o'qituvchi?")


@dp.message(ExamAdd.teacher)
async def exam_teacher(message: Message, state: FSMContext):
    await state.update_data(teacher=text_of(message)); await state.set_state(ExamAdd.duration); await message.answer("5/7 — Necha daqiqa?")


@dp.message(ExamAdd.duration)
async def exam_duration(message: Message, state: FSMContext):
    try: n = int(text_of(message))
    except ValueError: await message.answer("❌ Son kiriting."); return
    if n < 1 or n > 600: await message.answer("❌ 1–600 oralig'ida son kiriting."); return
    await state.update_data(duration=n); await state.set_state(ExamAdd.description); await message.answer("6/7 — Test haqida ma'lumot:")


@dp.message(ExamAdd.description)
async def exam_desc(message: Message, state: FSMContext):
    await state.update_data(description=text_of(message)); await state.set_state(ExamAdd.pdf)
    await message.answer(
        "7/7 — PDF fayl yuboring.\n\n"
        "Tavsiya etiladigan format:\n"
        "1. Savol?\nA) Variant\nB) Variant\nC) Variant\nD) Variant\n"
        "To'g'ri javob: B\n\n"
        "Javoblar bo'lmasa ham, keyin A/B/C/D tugmasi bilan belgilaysiz."
    )


def extract_pdf_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def ocr_pdf_text(pdf_path: str) -> str:
    if fitz is None or pytesseract is None or Image is None:
        return ""
    parts = []
    doc = fitz.open(pdf_path)
    try:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            parts.append(pytesseract.image_to_string(image, lang="eng"))
    finally:
        doc.close()
    return "\n".join(parts)


def normalize_pdf(text: str) -> str:
    text = text.replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # PDF extraction ko'pincha A) B) ni bitta qatorda beradi.
    text = re.sub(r"\s+([ABCD])\s*[\)\.\:\-]\s+", r"\n\1) ", text, flags=re.I)
    return text.strip()


def parse_questions(text: str):
    text = normalize_pdf(text)
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    qstart = re.compile(r"^(\d{1,4})\s*[\.\)]\s*(.*)$")
    ostart = re.compile(r"^([ABCD])\s*[\)\.\:\-]\s*(.*)$", re.I)
    ans = re.compile(r"^(?:to'g'ri\s+javob|to‘g‘ri\s+javob|javob|answer)\s*[:\-]?\s*([ABCD])\b", re.I)

    out = []
    cur = None
    option = None

    def finish():
        nonlocal cur
        if cur and all(cur.get(k) for k in "abcd"):
            cur["question"] = re.sub(r"\s+", " ", cur["question"]).strip()
            for k in "abcd": cur[k] = re.sub(r"\s+", " ", cur[k]).strip()
            out.append(cur)
        cur = None

    for line in lines:
        qm = qstart.match(line)
        if qm:
            finish()
            cur = {
                "number": int(qm.group(1)), "question": qm.group(2),
                "a": "", "b": "", "c": "", "d": "", "correct": "?"
            }
            option = None
            continue
        if cur is None:
            continue
        am = ans.match(line)
        if am:
            cur["correct"] = am.group(1).upper(); option = None; continue
        om = ostart.match(line)
        if om:
            option = om.group(1).lower(); cur[option] = om.group(2).strip(); continue
        if option:
            cur[option] += " " + line
        else:
            cur["question"] += " " + line
    finish()

    # Alohida javoblar kalitini ham tanishga harakat qilamiz.
    key = re.search(r"(?:^|\n)\s*(?:javoblar|answer\s*key|javob\s+kaliti)\s*[:\-]?\s*(.*)$", text, re.I | re.S)
    if key:
        for n, letter in re.findall(r"(?:^|[\s,;])([0-9]{1,4})\s*[-:\.\)]?\s*([ABCD])\b", key.group(1), re.I):
            for q in out:
                if q["number"] == int(n): q["correct"] = letter.upper()
    return out


@dp.message(ExamAdd.pdf, F.document)
async def exam_pdf(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith(".pdf"):
        await message.answer("❌ Faqat PDF yuboring."); return
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await message.answer("❌ PDF 20 MB dan katta bo'lmasin."); return

    path = PDF_DIR / f"{message.from_user.id}_{doc.file_unique_id}.pdf"

    try:
        tg = await bot.get_file(doc.file_id)
        await bot.download_file(tg.file_path, destination=path)
        text = extract_pdf_text(str(path))
        ocr_used = False
        if len(text.strip()) < 40:
            ocr_text = ocr_pdf_text(str(path))
            if ocr_text.strip():
                text = ocr_text
                ocr_used = True
    except Exception as exc:
        logging.exception("PDF read failed")
        path.unlink(missing_ok=True)
        await message.answer(
            "❌ PDFni o'qishda xato bo'ldi.\n"
            f"Sabab: {type(exc).__name__}\n"
            "Matnli PDF yuboring yoki OCR paketlarini o'rnating."
        )
        return

    if len(text.strip()) < 40:
        path.unlink(missing_ok=True)
        await message.answer(
            "❌ PDFdan matn olinmadi.\n\n"
            "Bu skanerlangan/ramsiz PDF bo'lishi mumkin.\n"
            "OCR uchun: pip install pymupdf pytesseract pillow va Windows Tesseract dasturi kerak."
        )
        return

    questions = parse_questions(text)
    if not questions:
        path.unlink(missing_ok=True)
        await message.answer(
            "❌ PDF ichidan A/B/C/D test topilmadi.\n\n"
            "Misol:\n1. Savol?\nA) ...\nB) ...\nC) ...\nD) ..."
        )
        return

    await state.update_data(pdf_file_id=doc.file_id, pdf_path=str(path), questions=questions)
    data = await state.get_data()
    missing = sum(1 for q in questions if q["correct"] == "?")
    await message.answer(
        "✅ <b>PDF TAHLILI TAYYOR</b>\n\n"
        f"Nomi: {data['title']}\nSinf: {data['class_name']}\nFan: {data['subject']}\n"
        f"O'qituvchi: {data['teacher']}\nVaqt: {data['duration']} daqiqa\n"
        f"Savollar: {len(questions)}\nJavobi tayyor: {len(questions)-missing}\n"
        f"Javobi belgilanadi: {missing}\n"
        f"OCR: {'✅' if ocr_used else '❌'}\n\n"
        "Saqlaymizmi?",
        reply_markup=confirm_kb("exam_save")
    )


@dp.message(ExamAdd.pdf)
async def exam_pdf_wrong(message: Message):
    await message.answer("📄 PDFni FILE/DOCUMENT qilib yuboring.")


@dp.callback_query(F.data == "exam_save")
async def exam_save(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    questions = data.get("questions", [])
    if not questions:
        await call.answer("Savollar topilmadi.", show_alert=True); return

    con = connect()
    try:
        # YANGI TEST chiqqanda avvalgi test va uning SAVOLLARI o'chiriladi.
        old_rows = con.execute("SELECT id FROM exams").fetchall()
        old_ids = [r["id"] for r in old_rows]
        if old_ids:
            placeholders = ",".join("?" for _ in old_ids)

            # Eski testning PDF fayllarini ham o'chiramiz. Natijalar/ballar saqlanadi.
            old_profiles = con.execute(
                f"SELECT pdf_path FROM exam_profiles WHERE exam_id IN ({placeholders})",
                old_ids
            ).fetchall()
            for old_profile in old_profiles:
                if old_profile["pdf_path"]:
                    Path(old_profile["pdf_path"]).unlink(missing_ok=True)

            con.execute(
                f"DELETE FROM questions WHERE exam_id IN ({placeholders})",
                old_ids
            )
            con.execute(
                f"DELETE FROM exam_profiles WHERE exam_id IN ({placeholders})",
                old_ids
            )
            con.execute(
                f"DELETE FROM exams WHERE id IN ({placeholders})",
                old_ids
            )

        cur = con.execute("INSERT INTO exams(subject, title) VALUES (?, ?)", (data["subject"], data["title"]))
        exam_id = cur.lastrowid
        con.execute("""
            INSERT INTO exam_profiles
            (exam_id, class_name, teacher, duration, description, pdf_file_id, pdf_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (exam_id, data["class_name"], data["teacher"], data["duration"], data["description"], data["pdf_file_id"], data["pdf_path"]))

        for q in questions:
            con.execute("""
                INSERT INTO questions
                (exam_id, question, option_a, option_b, option_c, option_d, correct, points)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (exam_id, q["question"], q["a"], q["b"], q["c"], q["d"], q["correct"]))
        con.commit()
    except Exception:
        con.rollback()
        con.close()
        Path(data["pdf_path"]).unlink(missing_ok=True)
        logging.exception("Exam save failed")
        await call.answer("Imtihonni saqlashda xato.", show_alert=True); return
    finally:
        try: con.close()
        except Exception: pass

    con = connect()
    try:
        missing = con.execute("""
            SELECT id, question, option_a, option_b, option_c, option_d
            FROM questions WHERE exam_id=? AND correct='?' ORDER BY id
        """, (exam_id,)).fetchall()
    finally:
        con.close()

    if not missing:
        await state.clear()
        await call.message.edit_text(f"✅ Yangi test tayyor.\nSavollar: {len(questions)}\nEski test savollari o'chirildi.")
        await call.message.answer("👑 Admin panel:", reply_markup=menu()); await call.answer(); return

    await state.set_state(MissingAnswers.choosing)
    await state.update_data(missing_ids=[r["id"] for r in missing], missing_index=0)
    q = missing[0]
    await call.message.edit_text(
        f"✅ Yangi test saqlandi. Eski test savollari o'chirildi.\n\n"
        f"⚠️ {len(missing)} ta javobni belgilang.\n\n"
        f"<b>1-savol:</b>\n{q['question']}\n\n"
        f"A) {q['option_a']}\nB) {q['option_b']}\nC) {q['option_c']}\nD) {q['option_d']}\n\n"
        "To'g'ri javob:",
        reply_markup=correct_kb(q["id"])
    )
    await call.answer()


@dp.callback_query(F.data.startswith("correct:"))
async def set_correct(call: CallbackQuery, state: FSMContext):
    _, qid_text, letter = call.data.split(":")
    qid = int(qid_text)

    con = connect()
    try:
        con.execute("UPDATE questions SET correct=? WHERE id=?", (letter, qid)); con.commit()
    finally: con.close()

    data = await state.get_data()
    ids = data.get("missing_ids", [])
    idx = int(data.get("missing_index", 0)) + 1

    if idx >= len(ids):
        await state.clear()
        await call.message.edit_text("✅ Barcha to'g'ri javoblar belgilandi. Test tayyor!")
        await call.message.answer("👑 Admin panel:", reply_markup=menu()); await call.answer(); return

    qid = ids[idx]
    con = connect()
    try:
        q = con.execute("SELECT id, question, option_a, option_b, option_c, option_d FROM questions WHERE id=?", (qid,)).fetchone()
    finally: con.close()

    await state.update_data(missing_index=idx)
    await call.message.edit_text(
        f"<b>{idx+1}-savol</b>\n\n{q['question']}\n\n"
        f"A) {q['option_a']}\nB) {q['option_b']}\nC) {q['option_c']}\nD) {q['option_d']}\n\nTo'g'ri javob:",
        reply_markup=correct_kb(q["id"])
    )
    await call.answer()


@dp.callback_query(F.data == "exam_list")
async def exam_list(call: CallbackQuery):
    con = connect()
    try:
        rows = con.execute("""
            SELECT e.id, e.subject, e.title, p.class_name, p.teacher, p.duration,
                   COUNT(q.id) AS question_count
            FROM exams e
            LEFT JOIN exam_profiles p ON p.exam_id=e.id
            LEFT JOIN questions q ON q.exam_id=e.id
            GROUP BY e.id
            ORDER BY e.id DESC
        """).fetchall()
    finally: con.close()
    if not rows:
        await call.message.edit_text("📝 Imtihon yo'q."); await call.answer(); return
    r = rows[0]
    await call.message.edit_text(
        f"📝 <b>{r['title']}</b>\n\n📖 {r['subject']}\n🏫 {r['class_name'] or '—'}\n"
        f"👨‍🏫 {r['teacher'] or '—'}\n⏱ {r['duration'] or 30} daqiqa\n❓ {r['question_count']} ta savol"
    )
    await call.answer()


@dp.callback_query(F.data == "exam_delete_menu")
async def exam_delete_menu(call: CallbackQuery):
    con = connect()
    try: rows = con.execute("SELECT id, subject, title FROM exams ORDER BY id DESC").fetchall()
    finally: con.close()
    if not rows:
        await call.message.edit_text("Imtihon yo'q."); await call.answer(); return
    kb = InlineKeyboardBuilder()
    for r in rows: kb.button(text=f"🗑 {r['subject']} — {r['title']}", callback_data=f"exam_delete:{r['id']}")
    kb.adjust(1)
    await call.message.edit_text("Qaysi testni o'chiramiz?", reply_markup=kb.as_markup()); await call.answer()


@dp.callback_query(F.data.startswith("exam_delete:"))
async def exam_delete(call: CallbackQuery):
    exam_id = int(call.data.split(":")[1])
    con = connect()
    try:
        p = con.execute("SELECT pdf_path FROM exam_profiles WHERE exam_id=?", (exam_id,)).fetchone()
        if p and p["pdf_path"]: Path(p["pdf_path"]).unlink(missing_ok=True)
        con.execute("DELETE FROM questions WHERE exam_id=?", (exam_id,))
        con.execute("DELETE FROM exam_profiles WHERE exam_id=?", (exam_id,))
        con.execute("DELETE FROM exams WHERE id=?", (exam_id,))
        con.commit()
    finally: con.close()
    await call.message.edit_text("✅ Test o'chirildi."); await call.answer()


# =========================================================
# ARIZALAR
# =========================================================

async def application_view():
    con = connect()
    try:
        rows = con.execute("""
            SELECT
                r.id,
                r.telegram_id,
                r.phone,
                r.status,
                s.name AS subject_name,
                u.full_name,
                u.username
            FROM registrations r
            LEFT JOIN subjects s ON s.id=r.subject_id
            LEFT JOIN users u ON u.telegram_id=r.telegram_id
            ORDER BY r.id DESC
            LIMIT 100
        """).fetchall()
    finally:
        con.close()

    if not rows:
        return "📝 Hozircha arizalar yo'q.", None

    text = "📝 <b>DARSga YOZILGANLAR</b>\n\n"
    kb = InlineKeyboardBuilder()
    pending_count = 0

    for row in rows:
        status = row["status"] or "Yangi"
        username = f"@{row['username']}" if row["username"] else "username yo'q"

        text += (
            f"<b>#{row['id']}</b>\n"
            f"👤 {row["full_name"] or "Noma’lum"}\n"
            f"📖 {row["subject_name"] or "Fan o'chirilgan"}\n"
            f"📞 {row['phone']}\n"
            f"🔗 {username}\n"
            f"📌 Holat: <b>{status}</b>\n\n"
        )

        if status == "Yangi":
            pending_count += 1
            kb.button(text=f"✅ Qabul #{row['id']}", callback_data=f"reg_accept:{row['id']}")
            kb.button(text=f"❌ Rad #{row['id']}", callback_data=f"reg_reject:{row['id']}")

    kb.adjust(2)
    return text, (kb.as_markup() if pending_count else None)


@dp.message(F.text == "📝 Arizalar")
async def applications(message: Message):
    if not admin(message.from_user.id):
        return

    text, markup = await application_view()
    await message.answer(text, reply_markup=markup)


@dp.callback_query(F.data.startswith("reg_accept:"))
async def reg_accept(call: CallbackQuery):
    if not admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return

    reg_id = int(call.data.split(":")[1])
    con = connect()
    try:
        cur = con.execute(
            "UPDATE registrations SET status='Qabul qilindi' WHERE id=?",
            (reg_id,)
        )
        con.commit()
        changed = cur.rowcount
    finally:
        con.close()

    if not changed:
        await call.answer("Ariza topilmadi.", show_alert=True)
        return

    text, markup = await application_view()
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer("✅ Ariza qabul qilindi")


@dp.callback_query(F.data.startswith("reg_reject:"))
async def reg_reject(call: CallbackQuery):
    if not admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return

    reg_id = int(call.data.split(":")[1])
    con = connect()
    try:
        cur = con.execute(
            "UPDATE registrations SET status='Rad etildi' WHERE id=?",
            (reg_id,)
        )
        con.commit()
        changed = cur.rowcount
    finally:
        con.close()

    if not changed:
        await call.answer("Ariza topilmadi.", show_alert=True)
        return

    text, markup = await application_view()
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer("❌ Ariza rad etildi")


# =========================================================
# O'QUVCHILAR REYTINGI
# =========================================================

@dp.message(F.text == "🏆 O'quvchilar reytingi")
async def admin_ranking(message: Message):
    if not admin(message.from_user.id):
        return

    con = connect()
    try:
        rows = con.execute("""
            SELECT full_name, class_name, score
            FROM users
            ORDER BY score DESC, full_name ASC
            LIMIT 50
        """).fetchall()
    finally:
        con.close()

    if not rows:
        await message.answer("🏆 Hozircha reyting mavjud emas.", reply_markup=menu())
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>O'QUVCHILAR REYTINGI</b>\n\n"
    for i, row in enumerate(rows, 1):
        prefix = medals[i - 1] if i <= 3 else f"{i}."
        text += f"{prefix} {row['full_name']} — {row['score']} ball | {row["class_name"] or "Sinf ko'rsatilmagan"}\n"

    await message.answer(text, reply_markup=menu())


# =========================================================
# HISOBOT
# =========================================================

@dp.message(F.text == "📊 Hisobot")
async def report(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.clear()
    con = connect()
    try:
        counts = {
            "users": con.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "students": con.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "teachers": con.execute("SELECT COUNT(*) FROM teachers").fetchone()[0],
            "subjects": con.execute("SELECT COUNT(*) FROM subjects").fetchone()[0],
            "books": con.execute("SELECT COUNT(*) FROM books").fetchone()[0],
            "exams": con.execute("SELECT COUNT(*) FROM exams").fetchone()[0],
            "questions": con.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
            "registrations": con.execute("SELECT COUNT(*) FROM registrations").fetchone()[0],
        }
    finally: con.close()
    await message.answer(
        "📊 <b>HISOBOT</b>\n\n"
        f"👤 Foydalanuvchilar: {counts['users']}\n👨‍🎓 O'quvchilar: {counts['students']}\n"
        f"👨‍🏫 O'qituvchilar: {counts['teachers']}\n📖 Fanlar: {counts['subjects']}\n"
        f"📚 Darsliklar: {counts['books']}\n📝 Imtihonlar: {counts['exams']}\n"
        f"❓ Savollar: {counts['questions']}\n📋 Arizalar: {counts['registrations']}",
        reply_markup=menu()
    )


# =========================================================
# FALLBACK / RUN
# =========================================================

@dp.message()
async def fallback(message: Message):
    if not admin(message.from_user.id):
        await message.answer("⛔ Bu bot faqat administrator uchun.")
        return
    await message.answer("👑 Menyudan kerakli bo'limni tanlang.", reply_markup=menu())


async def main():
    init_db()
    if sync_site_data:
        await sync_site_data(DB_PATH, BASE_DIR)  # Initial admin site sync
    bot = Bot(BOT_TOKEN)

    async def periodic_site_sync():
        while True:
            try:
                if sync_site_data:
                    await sync_site_data(DB_PATH, BASE_DIR)
            except Exception:
                logging.exception("Periodic site sync xatosi")
            await asyncio.sleep(60)

    sync_task = asyncio.create_task(periodic_site_sync())

    # Oldingi versiyada file_id bo'lib qolgan rasmlar/fayllarni
    # umumiy papkaga ko'chirishga urinadi.
    await migrate_legacy_media(bot)

    print("========================================")
    print("SO'FI OLLOHYOR ADMIN BOT ISHLADI")
    print("DATABASE:", DB_PATH)
    print("MEDIA:", MEDIA_DIR)
    print("========================================")
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
