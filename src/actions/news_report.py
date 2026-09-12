import requests
import json
import os
from datetime import datetime

class NewsReporter:
    """Servicio de noticias dinámicas usando NewsAPI o fallback a RSS/DDG."""

    def __init__(self):
        self.api_key = self._get_news_api_key()
        self.base_url = "https://newsapi.org/v2/top-headlines"
        self.fallback_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        print("[NewsReporter] Inicializado.")

    def _get_news_api_key(self):
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'api_keys.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('news_api_key', '')
        except:
            return ""

    def get_news(self, category: str = "technology") -> str:
        """
        Obtiene noticias de última hora por categoría.
        Categorías: technology, sports, business, science, health, general.
        """
        # Mapeo de categorías en español/inglés
        category_map = {
            'tecnología': 'technology', 'tech': 'technology', 
            'deportes': 'sports', 'deporte': 'sports',
            'negocios': 'business', 'business': 'business',
            'ciencia': 'science', 'science': 'science',
            'salud': 'health', 'health': 'health',
            'general': 'general'
        }
        cat = category_map.get(category.lower(), category.lower())

        # Intentar con NewsAPI
        if self.api_key:
            try:
                params = {
                    'country': 'us',
                    'category': cat,
                    'apiKey': self.api_key,
                    'pageSize': 8
                }
                response = requests.get(self.base_url, params=params, timeout=10)
                data = response.json()
                
                if data.get('status') == 'ok':
                    articles = data.get('articles', [])
                    if articles:
                        headlines = [f"Últimas noticias de {cat}:"]
                        for i, art in enumerate(articles[:8], 1):
                            title = art.get('title', '').strip()
                            if title:
                                headlines.append(f"{i}. {title}")
                        return "\n".join(headlines)
            except Exception as e:
                print(f"[News] NewsAPI falló: {e}")

        # Fallback: RSS de Google News (sin clave)
        try:
            import feedparser
            feed = feedparser.parse(self.fallback_url)
            if feed.entries:
                headlines = ["Noticias de última hora (RSS):"]
                for i, entry in enumerate(feed.entries[:8], 1):
                    title = entry.get('title', '').strip()
                    if title:
                        headlines.append(f"{i}. {title}")
                return "\n".join(headlines)
        except ImportError:
            pass
        except Exception as e:
            print(f"[News] RSS falló: {e}")

        # Último recurso: mensaje amigable
        return "No se pudieron obtener noticias en este momento. Intenta más tarde."