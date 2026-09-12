import requests
import json
import datetime
import os

def obtener_curiosidad():
    """
    Obtiene una curiosidad científica desde una API pública.
    """
    try:
        # Nota: Esta API puede no existir realmente, es un ejemplo.
        # Se recomienda reemplazar por una real como 'https://api.api-ninjas.com/v1/facts'
        response = requests.get("https://api.science-curiosities.com/random", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('curiosity', 'No se encontró curiosidad.')
        else:
            return f'Error al obtener curiosidad: Código {response.status_code}'
    except requests.exceptions.RequestException as e:
        return f'Error de conexión: {str(e)}'

def publicar_tweet(curiosidad):
    """
    Simula la publicación de un tweet.
    Para implementación real, usar tweepy o la API de Twitter v2.
    """
    # Simulación de publicación (reemplazar con lógica real si se tienen credenciales)
    print(f"[SIMULACIÓN] Tweet publicado: {curiosidad}")
    
    # Ejemplo de cómo sería con tweepy (comentado):
    # import tweepy
    # auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
    # auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    # api = tweepy.API(auth)
    # api.update_status(curiosidad)
    
    # Retornamos un estado simulado
    return {
        "publicado": True,
        "mensaje": "Tweet simulado correctamente (sin conexión real a Twitter)."
    }

def run(params):
    """
    Skill que obtiene una curiosidad científica y simula su publicación.
    """
    curiosidad = obtener_curiosidad()
    
    # Intentamos publicar el tweet (simulado)
    resultado_publicacion = publicar_tweet(curiosidad)
    
    # Retornamos el resultado completo
    return {
        "status": "success",
        "curiosidad": curiosidad,
        "publicacion": resultado_publicacion,
        "timestamp": datetime.datetime.now().isoformat()
    }

# Si se ejecuta directamente, probamos el skill
if __name__ == "__main__":
    # Prueba rápida del skill
    resultado = run({})
    print(json.dumps(resultado, indent=4, ensure_ascii=False))