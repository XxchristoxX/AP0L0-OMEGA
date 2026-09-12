import requests
import json
import os
import subprocess
def get_spotify_access_token(client_id, client_secret):
    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }
    response = requests.post(url, headers=headers, data=data, auth=(client_id, client_secret))
    return response.json().get("access_token")
def search_playlist(access_token, mood):
    url = f"https://api.spotify.com/v1/search?q={mood}&type=playlist"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    playlists = response.json().get("playlists", {}).get("items", [])
    if playlists:
        return playlists[0]["external_urls"]["spotify"]
    return None
def play_music(playlist_url):
    subprocess.run(["xdg-open", playlist_url])
def run(params):
    client_id = params.get('client_id')
    client_secret = params.get('client_secret')
    mood = params.get('mood')
    access_token = get_spotify_access_token(client_id, client_secret)
    playlist_url = search_playlist(access_token, mood)
    if playlist_url:
        play_music(playlist_url)
        return {"status": "success", "playlist_url": playlist_url}
    return {"status": "error", "message": "No se encontró una lista de reproducción para el estado de ánimo."}