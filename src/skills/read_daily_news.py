import requests
import json
import datetime
import subprocess
class ReadDailyNews:
    def __init__(self):
        self.api_url = "https://newsapi.org/v2/top-headlines"
        self.api_key = "YOUR_API_KEY"  # Reemplaza con tu clave de API
    def get_news(self):
        params = {
            'apiKey': self.api_key,
            'country': 'us',
            'pageSize': 5
        }
        response = requests.get(self.api_url, params=params)
        return response.json()
    def read_news(self, articles):
        news_summary = "Aquí están las noticias del día:\n"
        for article in articles:
            news_summary += f"{article['title']}.\n"
        self.speak(news_summary)
    def speak(self, text):
        subprocess.run(['say', text])  # Solo funciona en macOS, usa un método alternativo en otros SO
    def run(self, params):
        news_data = self.get_news()
        if news_data.get('status') == 'ok':
            articles = news_data.get('articles', [])
            self.read_news(articles)
            return {"status": "success", "message": "News read aloud."}
        else:
            return {"status": "error", "message": "Could not fetch news."}