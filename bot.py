#!/usr/bin/env python3
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ТВОИ ТОКЕНЫ
TELEGRAM_TOKEN = "8667849263:AAH-2a4GyZEyHBnrjpRoazvawKKOBUG7ADU"
WEATHER_TOKEN = "fa4118cf8d68ff5c1e447687eae720c1"

# Состояние для ConversationHandler (ожидание ввода города)
WAITING_CITY = 1

# Клавиатура главного меню (добавлена кнопка "Сменить город")
main_keyboard = [
    [KeyboardButton("Погода")],
    [KeyboardButton("Сменить город")]
]
main_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)

# Меню выбора периода
weather_keyboard = [
    [KeyboardButton("Сегодня")],
    [KeyboardButton("Завтра")],
    [KeyboardButton("10 дней")],
    [KeyboardButton("Назад")]
]
weather_markup = ReplyKeyboardMarkup(weather_keyboard, resize_keyboard=True)

# Получение прогноза по координатам (или по городу, если координат нет)
def get_weather_data(city_name=None, lat=None, lon=None):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "appid": WEATHER_TOKEN,
        "units": "metric",
        "lang": "ru"
    }
    if lat and lon:
        params["lat"] = lat
        params["lon"] = lon
    elif city_name:
        params["q"] = city_name
    else:
        return None

    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None
    return response.json()

# Получение координат по названию города (через Geocoding API)
def get_coords(city_name):
    url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": city_name,
        "limit": 1,
        "appid": WEATHER_TOKEN
    }
    response = requests.get(url, params=params)
    if response.status_code == 200 and response.json():
        data = response.json()[0]
        return data["lat"], data["lon"], data.get("local_names", {}).get("ru", city_name)
    return None, None, city_name

# Форматирование времени (из "2025-05-21 12:00:00" в "12:00")
def format_time(dt_txt):
    return dt_txt.split()[1][:5]

# Прогноз на сегодня (каждые 3 часа, сгруппируем по времени суток)
def weather_today(data, city_name):
    if not data:
        return "❌ Не удалось получить данные."
    today_date = data["list"][0]["dt_txt"].split()[0]
    forecast = []
    for item in data["list"]:
        if item["dt_txt"].split()[0] != today_date:
            continue
        time = format_time(item["dt_txt"])
        temp = item["main"]["temp"]
        desc = item["weather"][0]["description"]
        forecast.append(f"🕒 {time} — {temp}°C, {desc}")
    if not forecast:
        return "❌ Нет данных на сегодня."
    return f"☀️ <b>Погода сегодня в {city_name}</b>\n" + "\n".join(forecast)

# Прогноз на завтра (та же логика, что и сегодня)
def weather_tomorrow(data, city_name):
    if not data:
        return "❌ Не удалось получить данные."
    today_date = data["list"][0]["dt_txt"].split()[0]
    tomorrow_date = None
    forecast = []
    for item in data["list"]:
        date = item["dt_txt"].split()[0]
        if date == today_date:
            continue
        if tomorrow_date is None:
            tomorrow_date = date
        if date != tomorrow_date:
            break
        time = format_time(item["dt_txt"])
        temp = item["main"]["temp"]
        desc = item["weather"][0]["description"]
        forecast.append(f"🕒 {time} — {temp}°C, {desc}")
    if not forecast:
        return "❌ Нет данных на завтра."
    return f"📅 <b>Погода на завтра ({tomorrow_date}) в {city_name}</b>\n" + "\n".join(forecast)

# Прогноз на 10 дней (макс. дневная и мин. ночная температуры)
def weather_10days(data, city_name):
    if not data:
        return "❌ Не удалось получить данные."
    daily = {}
    for item in data["list"]:
        date = item["dt_txt"].split()[0]
        temp = item["main"]["temp"]
        desc = item["weather"][0]["description"]
        if date not in daily:
            daily[date] = {"temps": [], "descs": []}
        daily[date]["temps"].append(temp)
        daily[date]["descs"].append(desc)

    days = list(daily.items())[:10]
    result = [f"📆 <b>Прогноз на 10 дней ({city_name})</b>\n"]
    for date, info in days:
        max_temp = max(info["temps"])
        min_temp = min(info["temps"])
        main_desc = max(set(info["descs"]), key=info["descs"].count)
        result.append(f"• {date}: ☀️ {max_temp:.0f}°C / 🌙 {min_temp:.0f}°C, {main_desc}")
    return "\n".join(result)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Если город ещё не сохранён, запросим его
    if "city" not in context.user_data:
        await update.message.reply_text("Добро пожаловать! Напиши название города, для которого хочешь узнавать погоду:")
        return WAITING_CITY
    else:
        await update.message.reply_text(
            f"Привет! Текущий город: {context.user_data['city']}. Выбери действие:",
            reply_markup=main_markup
        )

# Обработчик ввода города (когда бот ждёт название)
async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    lat, lon, local_name = get_coords(city)
    if lat is None:
        await update.message.reply_text("Город не найден. Попробуй ещё раз или проверь название:")
        return WAITING_CITY
    context.user_data["city"] = local_name
    context.user_data["lat"] = lat
    context.user_data["lon"] = lon
    await update.message.reply_text(
        f"✅ Город установлен: {local_name}.\nТеперь можешь смотреть погоду!",
        reply_markup=main_markup
    )
    return ConversationHandler.END

# Обработчик кнопок
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Погода":
        if "city" not in context.user_data:
            await update.message.reply_text("Сначала установи город через кнопку «Сменить город».")
            return
        await update.message.reply_text("Какой прогноз показать?", reply_markup=weather_markup)

    elif text == "Сменить город":
        await update.message.reply_text("Напиши название нового города:")
        return WAITING_CITY

    elif text == "Назад":
        await update.message.reply_text("Главное меню:", reply_markup=main_markup)

    elif text in ["Сегодня", "Завтра", "10 дней"]:
        if "city" not in context.user_data:
            await update.message.reply_text("Сначала установи город.")
            return
        city = context.user_data["city"]
        lat = context.user_data["lat"]
        lon = context.user_data["lon"]
        data = get_weather_data(lat=lat, lon=lon)  # Используем координаты
        if text == "Сегодня":
            answer = weather_today(data, city)
        elif text == "Завтра":
            answer = weather_tomorrow(data, city)
        else:
            answer = weather_10days(data, city)
        await update.message.reply_text(answer, reply_markup=weather_markup, parse_mode="HTML")

    else:
        await update.message.reply_text("Используй кнопки меню.", reply_markup=main_markup)

# Точка входа
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # ConversationHandler для смены города
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^Сменить город$"), set_city),
            # Если пользователь уже в режиме ожидания города
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_city)
        ],
        states={
            WAITING_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_city)]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот с выбором города и детальным прогнозом запущен...", flush=True)
    app.run_polling()

if __name__ == "__main__":
    main()
