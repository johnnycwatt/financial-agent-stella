import logging
import yfinance as yf
import numpy as np
import requests
from cache import get_cached_data, set_cached_data, get_cached_news, set_cached_news, get_cached_highlights, set_cached_highlights
from dotenv import load_dotenv
import os
import time
from typing import Optional

load_dotenv()
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)
logger = logging.getLogger(__name__)

def time_it(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        logger.info(f"{func.__name__} took {time.time() - start:.2f} seconds")
        return result
    return wrapper

@time_it
def get_stock_data(ticker: str) -> dict:
    """Fetch and cache stock data using yfinance."""
    cached = get_cached_data(ticker)
    if cached:
        logger.debug(f"Cache hit for ticker: {ticker}")
        return cached
    
    logger.debug(f"Fetching fresh data for ticker: {ticker}")
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period="5y")
        history["Daily Return"] = history["Close"].pct_change()
        
        metrics = {
            "current_price": info.get("currentPrice"),
            "price_target": info.get("targetMeanPrice"),  # Analyst target
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "beta": info.get("beta"),
            "dividend_yield": info.get("dividendYield"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "market_cap": info.get("marketCap"),
            "institutional_holdings": info.get("heldPercentInstitutions"),
            "insider_holdings": info.get("heldPercentInsiders"),
            "book_value_per_share": info.get("bookValue"),
            "debt_to_capital": info.get("debtToEquity"),
            "return_on_equity": info.get("returnOnEquity"),
            "1y_return": (history["Close"].iloc[-1] / history["Close"].iloc[-252] - 1) if len(history) >= 252 else None,
            "5y_return": (history["Close"].iloc[-1] / history["Close"].iloc[0] - 1) if len(history) > 0 else None,
            "50d_ma": history["Close"].rolling(50).mean().iloc[-1],
            "200d_ma": history["Close"].rolling(200).mean().iloc[-1],
            "volatility_metrics": {
                "annualized_vol": history["Daily Return"].std() * np.sqrt(252),
                "annualized_var": history["Daily Return"].var() * 252,
                "kurtosis": history["Daily Return"].kurtosis(),
                "95_var": history["Daily Return"].quantile(0.05),
                "95_cvar": history["Daily Return"][history["Daily Return"] <= history["Daily Return"].quantile(0.05)].mean(),
            },
            "business_description": info.get("longBusinessSummary"),
        }
        
        set_cached_data(ticker, metrics)
        logger.info(f"Data fetched and cached for {ticker}")
        return metrics
    except Exception as e:
        logger.error(f"Error fetching stock data for {ticker}: {e}")
        return {}

@time_it
def get_news(query: str, num_results: int = 5) -> list:
    """Fetch news using Brave Search API."""
    logger.debug(f"Calling Brave API with query: {query}, num_results: {num_results}")
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY}
        params = {"q": query, "count": num_results, "freshness": "pd"}  # Past day for latest
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise if not 200
        results = response.json().get("web", {}).get("results", [])
        news_list = [r["title"] + ": " + r["description"] for r in results]
        logger.info(f"Fetched {len(news_list)} news items for query: {query}")
        return news_list
    except Exception as e:
        logger.error(f"Error fetching news for query {query}: {e}")
        return []

@time_it
def get_company_news(company: str) -> list:
    return get_news(f"latest news on {company}")

@time_it
def get_general_news(topic: str) -> list:
    return get_news(f"latest news on {topic}")

@time_it
def get_stock_highlights(ticker: str) -> dict:
    """Fetch stock highlights (current price, daily change, MAs) with preference for yfinance, fallback to Alpha Vantage."""
    cached = get_cached_highlights(ticker)
    if cached:
        logger.debug(f"Highlights cache hit for ticker: {ticker}")
        return cached

    logger.debug(f"Fetching fresh highlights for ticker: {ticker}")
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        current = info.get('currentPrice')
        prev_close = info.get('previousClose')
        daily_change = ((current - prev_close) / prev_close * 100) if prev_close and current else None
        history = stock.history(period="1y")
        if len(history) < 200:
            raise ValueError("Not enough history data")
        ma50 = round(float(history['Close'].rolling(50).mean().iloc[-1]), 2) if len(history) >= 50 else None
        ma200 = round(float(history['Close'].rolling(200).mean().iloc[-1]), 2) if len(history) >= 200 else None
        metrics = {
            'current_price': current,
            'daily_change': daily_change,
            '50d_ma': ma50,
            '200d_ma': ma200
        }
        set_cached_highlights(ticker, metrics)
        logger.info(f"Highlights fetched from yfinance and cached for {ticker}")
        return metrics
    except Exception as e:
        logger.debug(f"yfinance failed for highlights {ticker}: {e}, falling back to Alpha Vantage")
    
    try:
        # Global Quote for price and change
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        resp = requests.get(url).json()
        quote = resp.get('Global Quote', {})
        current = float(quote.get('05. price', 0)) if quote else None
        prev_close = float(quote.get('08. previous close', 0)) if quote else None
        daily_change = float(quote.get('10. change percent', '0%')[:-1]) if quote else None

        # Time Series for MAs
        url_ts = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&outputsize=compact&apikey={ALPHA_VANTAGE_API_KEY}"
        resp_ts = requests.get(url_ts).json()
        ts = resp_ts.get('Time Series (Daily)', {})
        dates = sorted(ts.keys(), reverse=True)[:200]
        closes = [float(ts[d]['4. close']) for d in dates if d in ts]
        ma50 = round(sum(closes[:50]) / 50, 2) if len(closes) >= 50 else None
        ma200 = round(sum(closes[:200]) / 200, 2) if len(closes) >= 200 else None
        metrics = {
            'current_price': current,
            'daily_change': daily_change,
            '50d_ma': ma50,
            '200d_ma': ma200
        }
        set_cached_highlights(ticker, metrics)
        logger.info(f"Highlights fetched from Alpha Vantage and cached for {ticker}")
        return metrics
    except Exception as e:
        logger.error(f"Error fetching highlights for {ticker}: {e}")
        return {}

@time_it
def get_recent_news(ticker: str, company: Optional[str] = None) -> list:
    """Fetch recent news with preference for Alpha Vantage, fallback to yfinance then Brave."""
    cached = get_cached_news(ticker)
    if cached:
        logger.debug(f"News cache hit for ticker: {ticker}")
        return cached

    logger.debug(f"Fetching fresh news for ticker: {ticker}")
    try:
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&limit=5&sort=LATEST&apikey={ALPHA_VANTAGE_API_KEY}"
        resp = requests.get(url).json()
        feed = resp.get('feed', [])
        if not feed:
            raise ValueError("No news from Alpha Vantage")
        news_list = [f"{item['title']}: {item['summary']}" for item in feed]
        set_cached_news(ticker, news_list)
        logger.info(f"News fetched from Alpha Vantage and cached for {ticker}")
        return news_list
    except Exception as e:
        logger.debug(f"Alpha Vantage news failed for {ticker}: {e}, falling back")

    try:
        stock = yf.Ticker(ticker)
        ynews = stock.news
        news_list = [f"{n['title']}: {n.get('publisher', '')} - {n.get('link', '')}" for n in ynews[:5]]
        if news_list:
            set_cached_news(ticker, news_list)
            logger.info(f"News fetched from yfinance and cached for {ticker}")
            return news_list
    except Exception as e:
        logger.debug(f"yfinance news failed for {ticker}: {e}, falling back to Brave")

    if company:
        news_list = get_news(f"latest news on {company} stock", num_results=5)
        set_cached_news(ticker, news_list)
        logger.info(f"News fetched from Brave and cached for {ticker}")
        return news_list
    return []