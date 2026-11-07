from datetime import datetime, time, timedelta
from html import escape
import logging
import os
import threading
import time as time_module
from typing import Any

from dotenv import load_dotenv
from telebot import TeleBot

from subscriptions import (
    get_subscription,
    get_subscriptions,
    initialize_database,
    subscribe,
    unsubscribe,
)
from weather_api import WeatherAPIError, get_future_weather, get_weather


load_dotenv()
token = os.getenv("BOT_TOKEN")
if not token:
    raise RuntimeError("BOT_TOKEN is not set")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
bot = TeleBot(token)
DAILY_SEND_TIME = time(hour=9)


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
        "• <code>/future-weather Москва</code> — прогноз на неделю\n"
        "• <code>/subscribe Москва</code> — ежедневная рассылка в 09:00\n"
        "• <code>/unsubscribe</code> — отключить рассылку\n"
        "• <code>/subscription</code> — проверить подписку\n\n"
        "Можно вводить название города на русском или английском. "
        "Время рассылки — локальное время компьютера, на котором запущен бот.",
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


@bot.message_handler(commands=["subscribe"])
def subscribe_to_weather(message: Any) -> None:
    city = _city_from_message(message)
    if not city:
        bot.send_message(
            message.chat.id,
            "Укажите город, например: <code>/subscribe Москва</code>",
            parse_mode="HTML",
        )
        return

    try:
        get_future_weather(city)
    except WeatherAPIError as error:
        _handle_api_error(message.chat.id, error)
        return

    subscribe(message.chat.id, city)
    bot.send_message(
        message.chat.id,
        f"✅ Подписка оформлена. Каждый день в 09:00 буду присылать прогноз для "
        f"<b>{_escape(city)}</b>.\n"
        "Если укажете другой город командой /subscribe, город подписки обновится.",
        parse_mode="HTML",
    )


@bot.message_handler(commands=["unsubscribe"])
def unsubscribe_from_weather(message: Any) -> None:
    if unsubscribe(message.chat.id):
        text = "Рассылка отключена. Чтобы подписаться снова, отправьте /subscribe <город>."
    else:
        text = "У вас нет активной подписки."
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["subscription"])
def show_subscription(message: Any) -> None:
    city = get_subscription(message.chat.id)
    if city:
        bot.send_message(
            message.chat.id,
            f"🔔 Вы подписаны на ежедневный прогноз для <b>{_escape(city)}</b> "
            "в 09:00.",
            parse_mode="HTML",
        )
    else:
        bot.send_message(
            message.chat.id,
            "Активной подписки нет. Чтобы подписаться, отправьте /subscribe <город>.",
        )


def _daily_forecast_text(city: str) -> str:
    weather_data = get_future_weather(city)
    location = weather_data["location"]
    forecast = weather_data["forecast"]["forecastday"][0]
    day = forecast["day"]
    try:
        date = datetime.strptime(forecast["date"], "%Y-%m-%d").strftime("%d.%m")
    except ValueError:
        date = forecast["date"]

    return (
        f"🌅 <b>Прогноз на сегодня для {_escape(location['name'])}, "
        f"{_escape(location['country'])}</b>\n"
        f"📅 {_escape(date)} — {_escape(day['condition']['text'])}\n"
        f"🌡 {_escape(day['mintemp_c'])}° … {_escape(day['maxtemp_c'])}°C"
        f"  ·  средняя {_escape(day['avgtemp_c'])}°C\n"
        f"🌧 Вероятность дождя: {_escape(day['daily_chance_of_rain'])}%"
    )


def send_daily_weather() -> None:
    subscriptions = get_subscriptions()
    forecasts: dict[str, str] = {}
    errors: dict[str, str] = {}

    for _, city in subscriptions:
        city_key = city.casefold()
        if city_key in forecasts or city_key in errors:
            continue
        try:
            forecasts[city_key] = _daily_forecast_text(city)
        except WeatherAPIError:
            logging.exception("Could not fetch daily forecast for %s", city)
            errors[city_key] = city

    for chat_id, city in subscriptions:
        city_key = city.casefold()
        if city_key in errors:
            text = (
                f"Не удалось получить прогноз для <b>{_escape(city)}</b>. "
                "Подписка сохранена, попробую снова завтра."
            )
        else:
            text = forecasts[city_key]
        try:
            bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception:
            logging.exception("Could not send daily forecast to chat %s", chat_id)


def _seconds_until_next_send() -> float:
    now = datetime.now().astimezone()
    next_send = datetime.combine(now.date(), DAILY_SEND_TIME, tzinfo=now.tzinfo)
    if next_send <= now:
        next_send += timedelta(days=1)
    return (next_send - now).total_seconds()


def _daily_scheduler() -> None:
    while True:
        time_module.sleep(_seconds_until_next_send())
        try:
            send_daily_weather()
        except Exception:
            logging.exception("Daily weather broadcast failed")


if __name__ == "__main__":
    initialize_database()
    threading.Thread(target=_daily_scheduler, daemon=True).start()
    bot.polling(none_stop=True)
