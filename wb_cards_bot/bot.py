"""Генератор карточек товаров для маркетплейсов (Wildberries / Ozon).

Демо-режим работает на шаблонном движке: клиент вводит название товара,
категорию и 3–6 ключевых свойств — бот собирает SEO-название, список
ключевых слов, продающее описание и характеристики. Готовая карточка
выгружается в Excel, пригодный для массовой загрузки.

В продакшене шаблонный движок (generate.py) заменяется на вызов LLM
(OpenAI/DeepSeek/GigaChat) — интерфейс функций сохраняется.
"""

import os
import re
import sqlite3
from datetime import datetime
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from generate import build_card
from export_xlsx import card_to_xlsx

load_dotenv()
bot = Bot(os.getenv("BOT_TOKEN"))
dp = Dispatcher()

db = sqlite3.connect("cards.db", check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, product TEXT, category TEXT,
    title TEXT, keywords TEXT, description TEXT,
    created_at TEXT)""")
db.commit()


class Card(StatesGroup):
    product = State()
    category = State()
    features = State()
    tone = State()


TONES = {
    "classic": "Сдержанный, деловой",
    "bright": "Яркий, эмоциональный",
    "minimal": "Минималистичный, лаконичный",
}


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="✨ Сгенерировать карточку", callback_data="new")
    kb.button(text="📁 Мои карточки", callback_data="history")
    kb.button(text="❓ Как это работает", callback_data="help")
    kb.adjust(1)
    return kb.as_markup()


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer(
        "Привет! 👋 Я собираю карточки товаров для Wildberries и Ozon: "
        "SEO-название, ключевые слова, продающее описание и характеристики. "
        "Из готовой карточки делаю Excel для массовой загрузки.\n\n"
        "Давайте попробуем:", reply_markup=main_menu())


@dp.callback_query(F.data == "help")
async def help_(c: CallbackQuery):
    await c.message.edit_text(
        "Как это работает:\n"
        "1️⃣ Вы пишете название товара («термокружка 500 мл»)\n"
        "2️⃣ Выбираете категорию и тон описания\n"
        "3️⃣ Перечисляете 3–6 ключевых свойств через запятую\n"
        "4️⃣ Я собираю карточку и присылаю Excel-файл\n\n"
        "Свойства лучше писать конкретно: материал, объём, цвет, "
        "особенности («не проливается», «держит тепло 12 часов»).",
        reply_markup=back_kb())
    await c.answer()


def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="◀ В меню", callback_data="menu")
    return kb.as_markup()


@dp.callback_query(F.data == "menu")
async def to_menu(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("Что делаем дальше?", reply_markup=main_menu())
    await c.answer()


@dp.callback_query(F.data == "new")
async def new_card(c: CallbackQuery, state: FSMContext):
    await state.set_state(Card.product)
    await c.message.edit_text("Как называется товар? Например: «термокружка 500 мл»")
    await c.answer()


@dp.message(Card.product)
async def got_product(m: Message, state: FSMContext):
    await state.update_data(product=m.text.strip())
    await state.set_state(Card.category)
    await m.answer("Категория товара? Например: «посуда», «электроника», «одежда».")


@dp.message(Card.category)
async def got_category(m: Message, state: FSMContext):
    await state.update_data(category=m.text.strip())
    await state.set_state(Card.features)
    await m.answer(
        "Перечислите 3–6 ключевых свойств через запятую.\n"
        "Пример: «сталь 316, 500 мл, не проливается, держит тепло 12 ч, крышка с поилкой»")


@dp.message(Card.features)
async def got_features(m: Message, state: FSMContext):
    features = [f.strip() for f in re.split(r"[,;\n]", m.text) if f.strip()]
    if len(features) < 3:
        await m.answer("Нужно хотя бы 3 свойства — перечислите через запятую ещё раз.")
        return
    await state.update_data(features=features[:8])
    kb = InlineKeyboardBuilder()
    for key, label in TONES.items():
        kb.button(text=label, callback_data=f"tone:{key}")
    kb.adjust(1)
    await state.set_state(Card.tone)
    await m.answer("Какой тон для описания?", reply_markup=kb.as_markup())


@dp.callback_query(Card.tone, F.data.startswith("tone:"))
async def got_tone(c: CallbackQuery, state: FSMContext):
    await state.update_data(tone=c.data.split(":")[1])
    data = await state.get_data()

    card = build_card(data["product"], data["category"],
                      data["features"], data["tone"])
    db.execute(
        "INSERT INTO cards (user_id, product, category, title, keywords, description, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (c.from_user.id, data["product"], data["category"], card["title"],
         ", ".join(card["keywords"]), card["description"],
         datetime.now().isoformat(timespec="seconds")))
    db.commit()
    await state.clear()

    preview = (
        f"✅ <b>Карточка готова</b>\n\n"
        f"<b>{escape(card['title'])}</b>\n\n"
        f"🔑 <b>Ключевые слова:</b> {escape(', '.join(card['keywords']))}\n\n"
        f"📝 <b>Описание:</b>\n{escape(card['description'])}\n\n"
        f"Выгрузить в Excel?"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 Скачать Excel", callback_data="xlsx:last")
    kb.button(text="✨ Ещё одну", callback_data="new")
    kb.button(text="◀ В меню", callback_data="menu")
    kb.adjust(1)
    await c.message.answer(preview, reply_markup=kb.as_markup(), parse_mode="HTML")
    await c.answer()


@dp.callback_query(F.data == "xlsx:last")
async def export_last(c: CallbackQuery):
    row = db.execute(
        "SELECT id, product, category, title, keywords, description "
        "FROM cards WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (c.from_user.id,)).fetchone()
    if not row:
        await c.answer("Пока нет карточек для выгрузки", show_alert=True)
        return
    cid, product, category, title, keywords, description = row
    path = card_to_xlsx([{
        "product": product, "category": category, "title": title,
        "keywords": keywords, "description": description,
    }], filename=f"card_{cid}.xlsx")
    await c.message.answer_document(
        document=open(path, "rb"),
        caption=f"Готово: карточка «{product}» в формате для массовой загрузки.")
    await c.answer()


@dp.callback_query(F.data == "history")
async def history(c: CallbackQuery):
    rows = db.execute(
        "SELECT id, product, title, created_at FROM cards "
        "WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (c.from_user.id,)).fetchall()
    if not rows:
        await c.message.edit_text("Карточек пока нет. Создадим первую?",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                      InlineKeyboardButton(text="✨ Сгенерировать", callback_data="new")]]))
        await c.answer()
        return
    kb = InlineKeyboardBuilder()
    text = "Ваши последние карточки:\n"
    for cid, product, title, at in rows:
        text += f"\n• <b>{escape(product)}</b> ({at[:10]})"
        kb.button(text=f"📥 Excel: {product[:20]}", callback_data=f"xlsx:{cid}")
    kb.button(text="◀ В меню", callback_data="menu")
    kb.adjust(1)
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await c.answer()


@dp.callback_query(F.data.startswith("xlsx:"))
async def export_one(c: CallbackQuery):
    cid = int(c.data.split(":")[1])
    row = db.execute(
        "SELECT product, category, title, keywords, description FROM cards "
        "WHERE id=? AND user_id=?", (cid, c.from_user.id)).fetchone()
    if not row:
        await c.answer("Карточка не найдена", show_alert=True)
        return
    product, category, title, keywords, description = row
    path = card_to_xlsx([{
        "product": product, "category": category, "title": title,
        "keywords": keywords, "description": description,
    }], filename=f"card_{cid}.xlsx")
    await c.message.answer_document(document=open(path, "rb"),
                                    caption=f"Карточка «{product}»")
    await c.answer()


@dp.message()
async def fallback(m: Message):
    await m.answer("Я понимаю команды меню 👇", reply_markup=main_menu())


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
