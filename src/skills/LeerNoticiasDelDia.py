import requests
import json
from datetime import datetime
def fetch_news(api_key):
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None
def read_news(news_data):
    headlines = []
    for article in news_data['articles']:
        headlines.append(article['title'])
    return headlines
def run(params):
    api_key = params.get('api_key')
    news_data = fetch_news(api_key)
    if news_data and 'articles' in news_data:
        headlines = read_news(news_data)
        return headlines
    else:
        return "No se pudieron obtener las noticias."