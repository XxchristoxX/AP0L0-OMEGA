# src/actions/recommendation_engine.py
import json
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # src/
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PREFERENCES_FILE = Path("data/preferences.json")


class RecommendationEngine:
    def __init__(self):
        self.prefs = self._load_prefs()
        self.tmdb_key = None
        self.spotify_client_id = None
        self.spotify_client_secret = None
        self.google_books_api_key = None
        self._load_api_keys()

    def _load_api_keys(self):
        try:
            if API_CONFIG_PATH.exists():
                with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.tmdb_key = config.get("tmdb_api_key", "")
                    self.spotify_client_id = config.get("spotify_client_id", "")
                    self.spotify_client_secret = config.get("spotify_client_secret", "")
                    self.google_books_api_key = config.get("google_books_api_key", "")
        except Exception:
            pass

    def _load_prefs(self):
        try:
            if PREFERENCES_FILE.exists():
                return json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"movies": [], "music": [], "books": []}

    def _save_prefs(self):
        PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
        PREFERENCES_FILE.write_text(json.dumps(self.prefs, indent=2), encoding="utf-8")

    # ------------------- PELÍCULAS (TMDB) -------------------
    def recommend_movie(self, genre: str = "") -> str:
        if not self.tmdb_key:
            return "TMDB API key no configurada. Agrega 'tmdb_api_key' en config/api_keys.json."

        url = "https://api.themoviedb.org/3/movie/popular"
        params = {"api_key": self.tmdb_key, "language": "es-ES", "page": 1}
        if genre:
            params["with_genres"] = genre
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            movies = data.get("results", [])[:5]
            if not movies:
                return "No se encontraron películas."
            lines = ["Recomendaciones de películas:"]
            for m in movies:
                lines.append(f"  {m['title']} ({m.get('release_date', '')[:4]})")
            return "\n".join(lines)
        except Exception as e:
            return f"Error al obtener recomendaciones de películas: {e}"

    # ------------------- MÚSICA (SPOTIFY) -------------------
    def _get_spotify_token(self) -> str | None:
        """Obtiene un token de acceso de Spotify usando client credentials."""
        if not self.spotify_client_id or not self.spotify_client_secret:
            return None
        auth_url = "https://accounts.spotify.com/api/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials"}
        try:
            resp = requests.post(
                auth_url,
                headers=headers,
                data=data,
                auth=(self.spotify_client_id, self.spotify_client_secret),
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
            else:
                return None
        except Exception:
            return None

    def recommend_music(self, genre: str = "") -> str:
        """
        Recomienda listas de reproducción de Spotify según el género.
        Si no se proporciona género, devuelve listas populares.
        """
        if not self.spotify_client_id or not self.spotify_client_secret:
            return ("Spotify no configurado. Agrega 'spotify_client_id' y "
                    "'spotify_client_secret' en config/api_keys.json.")

        token = self._get_spotify_token()
        if not token:
            return "No se pudo obtener token de Spotify. Verifica tus credenciales."

        search_term = genre if genre else "pop"
        url = "https://api.spotify.com/v1/search"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "q": search_term,
            "type": "playlist",
            "limit": 5,
            "market": "US"
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            data = resp.json()
            playlists = data.get("playlists", {}).get("items", [])
            if not playlists:
                return f"No se encontraron listas de reproducción para '{search_term}'."
            lines = [f"Listas de reproducción para '{search_term}':"]
            for p in playlists:
                name = p.get("name", "Sin título")
                owner = p.get("owner", {}).get("display_name", "Desconocido")
                tracks = p.get("tracks", {}).get("total", 0)
                url_external = p.get("external_urls", {}).get("spotify", "")
                lines.append(f"  {name} por {owner} ({tracks} canciones)")
                if url_external:
                    lines.append(f"    {url_external}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error al obtener recomendaciones de música: {e}"

    # ------------------- LIBROS (GOOGLE BOOKS) -------------------
    def recommend_book(self, genre: str = "") -> str:
        """
        Recomienda libros usando Google Books API según el género.
        """
        if not self.google_books_api_key:
            return "Google Books API key no configurada. Agrega 'google_books_api_key' en config/api_keys.json."

        query = genre if genre else "fiction"
        url = "https://www.googleapis.com/books/v1/volumes"
        params = {
            "q": query,
            "maxResults": 5,
            "key": self.google_books_api_key,
            "langRestrict": "es",
            "orderBy": "relevance"
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return f"No se encontraron libros para '{query}'."
            lines = [f"Recomendaciones de libros sobre '{query}':"]
            for item in items:
                info = item.get("volumeInfo", {})
                title = info.get("title", "Sin título")
                authors = ", ".join(info.get("authors", ["Desconocido"]))
                publisher = info.get("publisher", "")
                year = info.get("publishedDate", "")[:4]
                lines.append(f"  {title} — {authors} ({publisher} {year})")
            return "\n".join(lines)
        except Exception as e:
            return f"Error al obtener recomendaciones de libros: {e}"