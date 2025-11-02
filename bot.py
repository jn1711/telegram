from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
import asyncio
import aiohttp
import logging
import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()
logging.basicConfig(level=logging.INFO)

# --- Вспомогательные функции ---
def _fmt_num(value, decimals=2):
    try:
        v = float(value)
    except Exception:
        return str(value)
    if v.is_integer():
        return f"{int(v):,}".replace(",", " ")
    return f"{v:,.{decimals}f}".replace(",", " ")

def _parse_amount(text: str):
    if text is None:
        return None
    s = str(text).strip().replace('\u00A0', ' ').replace('\u2009', ' ')
    s = s.replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return None

def get_currency_keyboard():
    buttons = [
        [InlineKeyboardButton(text="USD → RUB", callback_data="usd_rub"),
         InlineKeyboardButton(text="RUB → USD", callback_data="rub_usd")],
        [InlineKeyboardButton(text="CNY → KZT", callback_data="cny_kzt"),
         InlineKeyboardButton(text="KZT → CNY", callback_data="kzt_cny")],
        [InlineKeyboardButton(text="USD → KZT", callback_data="usd_kzt"),
         InlineKeyboardButton(text="KZT → USD", callback_data="kzt_usd")],
        [InlineKeyboardButton(text="EUR → KZT", callback_data="eur_kzt"),
         InlineKeyboardButton(text="KZT → EUR", callback_data="kzt_eur")],
        [InlineKeyboardButton(text="Ввести валюту вручную", callback_data="manual")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Инициализация бота ---
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")
bot = Bot(token=TOKEN)
dp = Dispatcher()
user_data = {}  # Хранилище данных пользователей

# --- Старт бота ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    keyboard = get_currency_keyboard()
    await message.answer("Привет! Я бот-конвертер валют 💱\nВыбери направление:", reply_markup=keyboard)

# --- Выбор валюты через кнопки ---
@dp.callback_query()
async def handler_currency_choice(callback: types.CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id

    if data == "manual":
        user_data[user_id] = {"manual_step": 1}
        await callback.message.answer("Введите код валюты, из которой хотите конвертировать (например, USD):")
        await callback.answer()
        return

    from_currency, to_currency = data.split("_")
    user_data[user_id] = {"from": from_currency.upper(), "to": to_currency.upper()}
    await callback.message.answer(f"Введите сумму в {from_currency.upper()}:")
    await callback.answer()

# --- Основная обработка сообщений (ввод суммы или ручного ввода) ---
@dp.message()
async def handle_amount_or_manual(message: types.Message):
    user_id = message.from_user.id
    user_info = user_data.get(user_id)

    if not user_info:
        return  # Пользователь ещё не выбрал направление

    keyboard = get_currency_keyboard()  # Клавиатура для кнопки "Конвертировать ещё"

    try:
        # --- Ручной ввод валют ---
        if user_info.get("manual_step") == 1:
            user_info["from"] = message.text.strip().upper()
            user_info["manual_step"] = 2
            await message.answer("Введите код валюты, в которую хотите конвертировать (например, RUB):")
            return

        if user_info.get("manual_step") == 2:
            user_info["to"] = message.text.strip().upper()
            user_info["manual_step"] = 3
            await message.answer(f"Введите сумму в {user_info['from']}:")
            return

        if user_info.get("manual_step") == 3:
            amount = _parse_amount(message.text)
            if amount is None:
                await message.answer("Введите корректное число 💬", reply_markup=keyboard)
                return
            from_currency = user_info["from"]
            to_currency = user_info["to"]
            user_info.pop("manual_step", None)  # убираем шаг
        else:
            # --- Обычная конвертация по кнопкам ---
            amount = _parse_amount(message.text)
            if amount is None:
                await message.answer("Введите корректное число 💬", reply_markup=keyboard)
                return
            from_currency = user_info["from"]
            to_currency = user_info["to"]

        # --- Запрос к API ---
        async with aiohttp.ClientSession() as session:
            url = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{from_currency}"
            async with session.get(url) as response:
                data = await response.json()

        rates = data.get("conversion_rates", {})
        rate = rates.get(to_currency)

        if rate is None:
            await message.answer(f"Ошибка при получении курса 😔", reply_markup=keyboard)
            return

        converted = amount * rate
        amount_str = _fmt_num(amount)
        converted_str = _fmt_num(converted)

        await message.answer(f"✅ {amount_str} {from_currency} = {converted_str} {to_currency}", reply_markup=keyboard)

    finally:
        # --- Сброс данных пользователя ---
        if user_id in user_data:
            del user_data[user_id]

# --- Запуск бота ---
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
