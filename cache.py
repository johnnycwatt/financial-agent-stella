import time
import os
import json
from typing import Dict, Any, Optional, List

CACHE_EXPIRATION_SECONDS = 86400  # 24 hours for general data and news
CACHE_HIGHLIGHTS_SECONDS = 300  # 5 minutes for highlights (live prices)

def get_cached_data(ticker: str) -> Optional[Dict[str, Any]]:
    file = f"data/{ticker}_metrics.json"
    if os.path.exists(file):
        mtime = os.path.getmtime(file)
        if time.time() - mtime < CACHE_EXPIRATION_SECONDS:
            with open(file, 'r') as f:
                return json.load(f)
    return None

def set_cached_data(ticker: str, data: Dict[str, Any]):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{ticker}_metrics.json", 'w') as f:
        json.dump(data, f, indent=4)

def get_cached_news(ticker: str) -> Optional[List[str]]:
    file = f"data/{ticker}_news.json"
    if os.path.exists(file):
        mtime = os.path.getmtime(file)
        if time.time() - mtime < CACHE_EXPIRATION_SECONDS:
            with open(file, 'r') as f:
                return json.load(f)
    return None

def set_cached_news(ticker: str, news: List[str]):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{ticker}_news.json", 'w') as f:
        json.dump(news, f)

def get_cached_highlights(ticker: str) -> Optional[Dict[str, Any]]:
    file = f"data/{ticker}_highlights.json"
    if os.path.exists(file):
        mtime = os.path.getmtime(file)
        if time.time() - mtime < CACHE_HIGHLIGHTS_SECONDS:
            with open(file, 'r') as f:
                return json.load(f)
    return None

def set_cached_highlights(ticker: str, data: Dict[str, Any]):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{ticker}_highlights.json", 'w') as f:
        json.dump(data, f)