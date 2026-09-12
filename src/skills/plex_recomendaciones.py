import requests
import json
def connect_to_plex(server_url, token):
    headers = {
        'X-Plex-Token': token
    }
    response = requests.get(f"{server_url}/library/sections/1/all", headers=headers)
    return response.json()
def recommend_movies(data):
    movies = []
    for item in data['MediaContainer']['Metadata']:
        if item['type'] == 'movie':
            movies.append({
                'title': item['title'],
                'year': item['year'],
                'rating': item.get('rating', 'N/A')
            })
    return movies
def run(params):
    server_url = params.get('server_url')
    token = params.get('token')
    if not server_url or not token:
        return {'error': 'server_url and token are required'}
    data = connect_to_plex(server_url, token)
    recommended_movies = recommend_movies(data)
    return recommended_movies