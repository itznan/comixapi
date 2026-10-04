"""
Configuration and constants for Comix.to downloader.
"""

import os

USER_AGENT = os.environ.get(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
)
BASE_URL = "https://comix.to"
API_BASE = "https://comix.to/api/v1"
DEFAULT_CONCURRENCY = 8
DEFAULT_RETRIES = 4

GENRE_MAP = {
    "action": 6,
    "adult": 87264,
    "adventure": 7,
    "boys-love": 8,
    "boys love": 8,
    "comedy": 9,
    "crime": 10,
    "drama": 11,
    "ecchi": 87265,
    "fantasy": 12,
    "girls-love": 13,
    "girls love": 13,
    "harem": 40,
    "hentai": 87266,
    "historical": 14,
    "horror": 15,
    "isekai": 16,
    "magical-girls": 17,
    "magical girls": 17,
    "mature": 87267,
    "mecha": 18,
    "medical": 19,
    "mystery": 20,
    "philosophical": 21,
    "psychological": 22,
    "romance": 23,
    "sci-fi": 24,
    "scifi": 24,
    "sci fi": 24,
    "slice-of-life": 25,
    "slice of life": 25,
    "smut": 87268,
    "sports": 26,
    "superhero": 27,
    "thriller": 28,
    "tragedy": 29,
    "wuxia": 30,
    "martial arts": 30,
    "martial-arts": 30,
}

DEMOGRAPHIC_MAP = {
    "shoujo": 1,
    "shojo": 1,
    "shounen": 2,
    "shonen": 2,
    "josei": 3,
    "seinen": 4,
}
