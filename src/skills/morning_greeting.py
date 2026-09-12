import requests
import json
from datetime import datetime
def get_weather(api_key, city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        weather_description = data['weather'][0]['description']
        temperature = data['main']['temp']
        return f"El clima actual en {city} es de {temperature}°C con {weather_description}."
    else:
        return "No se pudo obtener el estado del clima."
def greet_user(name, api_key, city):
    current_time = datetime.now().strftime("%H:%M")
    weather_info = get_weather(api_key, city)
    return f"¡Hola, {name}! Son las {current_time}. {weather_info}"
def run(params):
    name = params.get('name', 'amigo')
    api_key = params.get('api_key')
    city = params.get('city', 'Madrid')
    if not api_key:
        return "Por favor, proporciona una clave de API válida."
    return greet_user(name, api_key, city)