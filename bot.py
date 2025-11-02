from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
import asyncio
import aiohttp
import logging
import os
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()
logging.basicConfig(level=logging.INFO)

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

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_data = {}

# --- /start ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    keyboard = get_currency_keyboard()
    await message.answer("Привет! Я бот-конвертер валют 💱\nВыбери направление:", reply_markup=keyboard)


# --- Обработка кнопок ---
@dp.callback_query()
async def on_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    # Пользователь выбрал ручной ввод
    if data == "manual":
        user_data[user_id] = {"step": "from"}
        await callback.message.answer("Введите код валюты, из которой хотите конвертировать (например, USD):")
        await callback.answer()
        return

    # Выбор из готовых кнопок
    from_currency, to_currency = data.split("_")
    user_data[user_id] = {"from": from_currency.upper(), "to": to_currency.upper(), "step": "amount"}
    await callback.message.answer(f"Введите сумму в {from_currency.upper()}:")
    await callback.answer()


# --- Обработка текстовых сообщений ---
@dp.message()
async def on_message(message: types.Message):
    user_id = message.from_user.id
    keyboard = get_currency_keyboard()
    info = user_data.get(user_id)

    # Если пользователь ещё не выбрал направление
    if not info:
        await message.answer("Сначала выбери направление через /start 💱", reply_markup=keyboard)
        return

    step = info.get("step")

    # 1️⃣ — ввод исходной валюты (ручной режим)
    if step == "from":
        info["from"] = message.text.strip().upper()
        info["step"] = "to"
        await message.answer("Введите код валюты, в которую хотите конвертировать (например, KZT):")
        return

    # 2️⃣ — ввод целевой валюты
    elif step == "to":
        info["to"] = message.text.strip().upper()
        info["step"] = "amount"
        await message.answer(f"Введите сумму в {info['from']}:")
        return

    # 3️⃣ — ввод суммы
    elif step == "amount":
        amount = _parse_amount(message.text)
        if amount is None:
            await message.answer("Введите корректное число 💬", reply_markup=keyboard)
            return

        from_currency = info["from"]
        to_currency = info["to"]

        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{from_currency}"
                async with session.get(url) as resp:
                    data = await resp.json()

            rate = data.get("conversion_rates", {}).get(to_currency)
            if rate is None:
                raise ValueError("Курс не найден")

            converted = amount * rate
            result = f"✅ { _fmt_num(amount) } {from_currency} = { _fmt_num(converted) } {to_currency}"
            await message.answer(result, reply_markup=keyboard)

        except Exception:
            await message.answer("Ошибка при получении курса 😔", reply_markup=keyboard)

        finally:
            user_data.pop(user_id, None)


async def main():
    print("Бот запущен ✅")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
