import os
import requests

api_key = os.getenv("ombd_api_key")

def search_tmdb(title, api_key):
    """Search TMDB and return basic info including TMDB and IMDb ID."""
    search_url = "https://api.themoviedb.org/3/search/multi"
    search_params = {
        "api_key": api_key,
        "query": title,
    }
    search_resp = requests.get(search_url, params=search_params)
    results = search_resp.json().get("results", [])
    if not results:
        return {"title": title, "tmdb_id": None, "imdb_id": None, "media_type": None}

    best_match = results[0]
    tmdb_id = best_match.get("id")
    media_type = best_match.get("media_type")

    # Now get detailed info to fetch IMDb ID
    detail_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
    detail_params = {"api_key": api_key}
    detail_resp = requests.get(detail_url, params=detail_params)
    detail_json = detail_resp.json()

    return {
        "title": title,
        "tmdb_id": tmdb_id,
        "imdb_id": detail_json.get("imdb_id"),
        "media_type": media_type
    }