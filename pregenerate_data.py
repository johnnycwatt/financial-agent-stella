import os
import json
import re
import argparse
from datetime import datetime
from dotenv import load_dotenv
import yfinance as yf
import numpy as np
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from tools import get_news, get_stock_highlights, get_recent_news

load_dotenv()
llm = ChatOpenAI(model="gpt-5-nano", api_key=os.getenv("OPENAI_API_KEY"))

# Define frequent companies and tickers
companies = {
    "Tesla": "TSLA",
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Nvidia": "NVDA",
    "Samsung": "005930.KS",
    "Raytheon": "RTX",
    "Hyundai": "005380.KS",
    "Alibaba": "BABA"
}

# Prompts (matched to agent)
report_prompt = PromptTemplate.from_template(
    """Generate a detailed stock report in Markdown using this data: {data}
    Structure:
    - Company Name, Ticker, Date, Current Price, Price Target
    - Business Description: ...
    - Market Profile (Table): ...
    - Industry Overview and Competitive Positioning: ...
    - Recent News: {news}
    - Volatility and Risk Metrics: ...
    Infer missing parts like industry overview, etc.
    """
)

overview_prompt = PromptTemplate.from_template(
    "Generate quick overview: Company {company}, Price: {price}, Highlights: {data}, News: {news}"
)

date = datetime.now().strftime("%Y-%m-%d")

def fetch_metrics_and_history(ticker):
    """
    Fetch metrics and history for a ticker, similar to get_stock_data in tools.py.
    Returns metrics dict and history DataFrame.
    """
    stock = yf.Ticker(ticker)
    info = stock.info
    history = stock.history(period="5y")
    history["Daily Return"] = history["Close"].pct_change()

    metrics = {
        "current_price": info.get("currentPrice"),
        "price_target": info.get("targetMeanPrice"),
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
        "50d_ma": round(float(history["Close"].rolling(50).mean().iloc[-1]), 2) if len(history) >= 50 else None,
        "200d_ma": round(float(history["Close"].rolling(200).mean().iloc[-1]), 2) if len(history) >= 200 else None,
        "volatility_metrics": {
            "annualized_vol": history["Daily Return"].std() * np.sqrt(252),
            "annualized_var": history["Daily Return"].var() * 252,
            "kurtosis": history["Daily Return"].kurtosis(),
            "95_var": history["Daily Return"].quantile(0.05),
            "95_cvar": history["Daily Return"][history["Daily Return"] <= history["Daily Return"].quantile(0.05)].mean(),
        },
        "business_description": info.get("longBusinessSummary"),
    }
    return metrics, history

def generate_reports(selected_companies=None):
    """Generate and save reports for the selected companies."""
    if selected_companies is None:
        selected_companies = companies
    for company, ticker in selected_companies.items():
        print(f"Generating report for {company} ({ticker})...")
        metrics, _ = fetch_metrics_and_history(ticker)
        # Save metrics JSON (overwrites)
        os.makedirs("data", exist_ok=True)
        with open(f"data/{ticker}_metrics.json", 'w') as f:
            json.dump(metrics, f, indent=4)
        # Fetch and clean news
        news = get_news(f"latest news on {company}", num_results=5)
        clean_news = [re.sub(r'<.*?>', '', item) for item in news]
        news_str = "\n".join(clean_news)
        # Generate and save report
        report = llm.invoke(report_prompt.format(data=metrics, news=news_str)).content
        os.makedirs("reports", exist_ok=True)
        with open(f"reports/{ticker}_{date}.md", 'w', encoding="utf-8") as f:
            f.write(report)
        print(f"Report completed for {company} ({ticker}).")

def generate_overviews(selected_companies=None):
    """Generate and save overviews for the selected companies."""
    if selected_companies is None:
        selected_companies = companies
    for company, ticker in selected_companies.items():
        print(f"Generating overview for {company} ({ticker})...")
        metrics, _ = fetch_metrics_and_history(ticker)
        # Save metrics JSON (overwrites)
        os.makedirs("data", exist_ok=True)
        with open(f"data/{ticker}_metrics.json", 'w') as f:
            json.dump(metrics, f, indent=4)
        # Fetch and clean news
        news = get_news(f"latest news on {company}", num_results=5)
        clean_news = [re.sub(r'<.*?>', '', item) for item in news]
        news_str = "\n".join(clean_news)
        # Generate and save overview
        overview = llm.invoke(overview_prompt.format(company=company, price=metrics["current_price"], data=metrics, news=news_str)).content
        os.makedirs("overviews", exist_ok=True)
        with open(f"overviews/{ticker}_{date}.md", 'w', encoding="utf-8") as f:
            f.write(overview)
        print(f"Overview completed for {company} ({ticker}).")

def download_stock_history(selected_companies=None):
    """Download and save stock history CSV for the selected companies."""
    if selected_companies is None:
        selected_companies = companies
    for company, ticker in selected_companies.items():
        print(f"Downloading history for {company} ({ticker})...")
        _, history = fetch_metrics_and_history(ticker)
        # Save history CSV (overwrites)
        os.makedirs("data", exist_ok=True)
        history.to_csv(f"data/{ticker}_history.csv")
        print(f"History download completed for {company} ({ticker}).")

def warmup_cache(selected_companies=None):
    """Pre-fetch and cache highlights and news for the selected companies (top tickers)."""
    if selected_companies is None:
        selected_companies = companies
    for company, ticker in selected_companies.items():
        print(f"Warming up cache for {company} ({ticker})...")
        # This will fetch and cache if not present
        get_stock_highlights(ticker)
        get_recent_news(ticker, company)
        print(f"Cache warmup completed for {company} ({ticker}).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pregenerate data for stock companies.")
    parser.add_argument("--reports", action="store_true", help="Generate reports")
    parser.add_argument("--overviews", action="store_true", help="Generate overviews")
    parser.add_argument("--history", action="store_true", help="Download stock history")
    parser.add_argument("--warmup", action="store_true", help="Warm up cache for highlights and news")
    parser.add_argument("--all", action="store_true", help="Run all tasks")
    parser.add_argument("--companies", nargs="+", help="Specify companies to process (e.g., Tesla Apple), default all")

    args = parser.parse_args()

    # Filter companies if specified
    if args.companies:
        selected_companies = {comp: companies.get(comp) for comp in args.companies if comp in companies}
        if not selected_companies:
            print("No valid companies specified. Exiting.")
            exit(1)
    else:
        selected_companies = companies

    if args.all or args.reports:
        generate_reports(selected_companies)
    if args.all or args.overviews:
        generate_overviews(selected_companies)
    if args.all or args.history:
        download_stock_history(selected_companies)
    if args.all or args.warmup:
        warmup_cache(selected_companies)

    if not (args.all or args.reports or args.overviews or args.history or args.warmup):
        parser.print_help()