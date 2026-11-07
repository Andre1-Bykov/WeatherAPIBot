from datetime import datetime
from html import escape
import os
from typing import Any

from telebot import TeleBot

from weather_api import WeatherAPIError, get_future_weather, get_weather


token = os.getenv("BOT_TOKEN")
if not token:
    raise RuntimeError("BOT_TOKEN is not set")

bot = TeleBot(token)


def _city_from_message(message: Any) -> str:
    parts = (message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _escape(value: Any) -> str:
    return escape(str(value))


def _handle_api_error(chat_id: int, error: WeatherAPIError) -> None:
    if error.code == 1006:
        text = "Не удалось найти такой город. Проверьте название и попробуйте ещё раз."
    else:
        text = "Не удалось получить данные о погоде. Попробуйте позже."
    bot.send_message(chat_id, text)


@bot.message_handler(commands=["start", "help"])
def start(message: Any) -> None:
    bot.send_message(
        message.chat.id,
        "👋 <b>Привет! Я бот прогноза погоды.</b>\n\n"
        "Узнайте погоду в любом городе:\n"
        "• <code>/weather Москва</code> — сейчас\n"
        "• <code>/future-weather Москва</code> — прогноз на неделю\n\n"
        "Можно вводить название города на русском или английском.",
        parse_mode="HTML",
    )


@bot.message_handler(commands=["weather"])
def weather(message: Any) -> None:
    city = _city_from_message(message)
    if not city:
        bot.send_message(
            message.chat.id,
            "Напишите город после команды, например: <code>/weather Москва</code>",
            parse_mode="HTML",
        )
        return

    try:
        weather_data = get_weather(city)
    except WeatherAPIError as error:
        _handle_api_error(message.chat.id, error)
        return

    location = weather_data["location"]
    current = weather_data["current"]
    condition = current["condition"]
    text = (
        f"🌍 <b>Погода в {_escape(location['name'])}, "
        f"{_escape(location['country'])}</b>\n"
        f"🕒 Местное время: {_escape(location['localtime'])}\n\n"
        f"🌤 {_escape(condition['text'])}\n"
        f"🌡 Температура: <b>{_escape(current['temp_c'])} °C</b>\n"
        f"🤗 Ощущается как: {_escape(current['feelslike_c'])} °C\n"
        f"💧 Влажность: {_escape(current['humidity'])}%\n"
        f"💨 Ветер: {_escape(current['wind_kph'])} км/ч"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["future-weather"])
def future_weather(message: Any) -> None:
    city = _city_from_message(message)
    if not city:
        bot.send_message(
            message.chat.id,
            "Напишите город после команды, например: <code>/future-weather Москва</code>",
            parse_mode="HTML",
        )
        return

    try:
        weather_data = get_future_weather(city)
    except WeatherAPIError as error:
        _handle_api_error(message.chat.id, error)
        return

    location = weather_data["location"]
    forecast_days = weather_data["forecast"]["forecastday"]
    lines = [
        f"🗓 <b>Прогноз погоды в {_escape(location['name'])}, "
        f"{_escape(location['country'])}</b>"
    ]

    for forecast_day in forecast_days:
        day = forecast_day["day"]
        condition = day["condition"]["text"]
        try:
            date = datetime.strptime(forecast_day["date"], "%Y-%m-%d").strftime("%d.%m")
        except ValueError:
            date = forecast_day["date"]
        lines.extend(
            [
                "",
                f"📅 <b>{_escape(date)}</b> — {_escape(condition)}",
                f"🌡 {_escape(day['mintemp_c'])}° … {_escape(day['maxtemp_c'])}°C"
                f"  ·  средняя {_escape(day['avgtemp_c'])}°C",
                f"🌧 Вероятность дождя: {_escape(day['daily_chance_of_rain'])}%",
            ]
        )

    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML")


if __name__ == "__main__":
    bot.polling(none_stop=True)
