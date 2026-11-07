import requests
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")


class WeatherAPIError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def _get_weather(endpoint, city, **params):
    if not API_KEY or not API_URL:
        raise WeatherAPIError("Weather API credentials are not configured")

    params.update({"key": API_KEY, "q": city, "lang": "ru"})
    try:
        response = requests.get(f"{API_URL}/{endpoint}.json", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise WeatherAPIError("Could not retrieve weather data") from error

    if "error" in data:
        api_error = data["error"]
        raise WeatherAPIError(api_error.get("message", "Weather API error"), api_error.get("code"))
    return data


def get_weather(city):
    return _get_weather("current", city)


def get_future_weather(city):
    return _get_weather("forecast", city, days=7)