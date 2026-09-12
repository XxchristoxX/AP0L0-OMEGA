import requests
import json
import datetime
import os
import subprocess
def web_search(query):
    # Simulación de búsqueda de noticias, reemplaza esto con una API real si es necesario
    response = {
        "articles": [
            {"title": "Título de noticia 1", "description": "Resumen de noticia 1"},
            {"title": "Título de noticia 2", "description": "Resumen de noticia 2"},
        ]
    }
    return response
def read_aloud(text):
    subprocess.run(['say', text])  # Para macOS; usa 'espeak' en Linux
def get_news_summary(query):
    news_data = web_search(query)
    summaries = []
    for article in news_data["articles"]:
        summaries.append({"title": article["title"], "summary": article["description"]})
    return summaries
def run(params):
    query = params.get("query", "noticias")
    read_news = params.get("read", False)
    news_summaries = get_news_summary(query)
    if read_news:
        for news in news_summaries:
            read_aloud(news["title"])
            read_aloud(news["summary"])
    return news_summaries