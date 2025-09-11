import logging
import re
import yfinance as yf
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from typing import TypedDict, Optional, List
from tools import get_stock_data, get_company_news, get_general_news, get_stock_highlights, get_recent_news
from datetime import datetime
import os
from dotenv import load_dotenv
import concurrent.futures
import time
import json

load_dotenv()
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)
logger = logging.getLogger(__name__)

llm = ChatOpenAI(model="gpt-5-nano", api_key=os.getenv("OPENAI_API_KEY"))

class AgentState(TypedDict):
    query: str
    task_type: str
    company: Optional[str]
    companies: Optional[List[dict]]
    data: Optional[dict]
    response: str
    source: Optional[str]  # cli or other

common_companies = {
    "apple": ("Apple", "AAPL"),
    "nvidia": ("Nvidia", "NVDA"),
    "tesla": ("Tesla", "TSLA"),
    "samsung": ("Samsung", "005930.KS"),
    "mcdonalds": ("McDonalds", "MCD"),
    "microsoft": ("Microsoft", "MSFT"),
    "alibaba": ("Alibaba", "BABA"),
    "hyundai": ("Hyundai", "005380.KS"),
    "bank of america": ("Bank of America", "BAC"),
    "jpmorgan": ("JPMorgan", "JPM"),
}

def time_it(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        logger.info(f"{func.__name__} took {time.time() - start:.2f} seconds")
        return result
    return wrapper

# Router: Classify query into task type
router_prompt = PromptTemplate.from_template(
    """Classify the query into one of: 
    1 - Stock Report
    2 - Company Overview
    3 - Company News
    4 - General News
    5 - Highlights
    Query: {query}
    Output only the number."""
)

@time_it
def router_node(state: AgentState) -> AgentState:
    logger.info(f"Processing query: {state['query']}")
    # Check for prefix like "1: "
    match = re.match(r'^(\d+):\s*(.*)', state["query"])
    if match:
        task_type = match.group(1)
        if task_type in ["1", "2", "3", "4", "5"]:
            state["task_type"] = task_type
            state["query"] = match.group(2).strip()
            logger.info(f"Extracted task type from prefix: {task_type}")
        else:
            task_type = None
    else:
        task_type = None

    if not task_type:
        try:
            task_type = llm.invoke(router_prompt.format(query=state["query"])).content.strip()
            state["task_type"] = task_type
            logger.info(f"Classified task type: {task_type}")
        except Exception as e:
            logger.error(f"Error in router classification: {e}")
            state["task_type"] = "4"  # Default to general news on error

    # Extract company/ticker if relevant
    if state["task_type"] in ["1", "2", "3"]:
        query_lower = state["query"].lower()
        extracted = False
        for comp in common_companies:
            if re.search(r'\b' + re.escape(comp) + r'\b', query_lower):
                state["company"] = common_companies[comp][0]
                state["ticker"] = common_companies[comp][1]
                logger.debug(f"Extracted company via regex: {state['company']}, ticker: {state['ticker']}")
                extracted = True
                break
        if not extracted:
            try:
                extract_prompt = PromptTemplate.from_template("Extract company name and ticker from: {query}. Output as 'Company: X, Ticker: Y' or 'None'.")
                extract = llm.invoke(extract_prompt.format(query=state["query"])).content
                if "None" not in extract:
                    parts = extract.split(", ")
                    state["company"] = parts[0].split(": ")[1]
                    state["ticker"] = parts[1].split(": ")[1] if len(parts) > 1 else state["company"].upper()
                    logger.debug(f"Extracted company via LLM: {state['company']}, ticker: {state['ticker']}")
            except Exception as e:
                logger.error(f"Error extracting company/ticker: {e}")
    elif state["task_type"] == "5":
        query_lower = state["query"].lower()
        seen_tickers = set()
        companies_list = []
        # Regex extraction for common companies (case-insensitive)
        for comp in common_companies:
            if re.search(r'\b' + re.escape(comp) + r'\b', query_lower):
                ticker = common_companies[comp][1]
                if ticker not in seen_tickers:
                    companies_list.append({"company": common_companies[comp][0], "ticker": ticker})
                    seen_tickers.add(ticker)
        # Find potential tickers (uppercase 2-5 letters)
        potential_tickers = re.findall(r'\b[A-Z]{2,5}\b', state["query"])
        for pt in potential_tickers:
            if pt not in seen_tickers:
                found = False
                for comp, (name, tick) in common_companies.items():
                    if tick == pt:
                        companies_list.append({"company": name, "ticker": pt})
                        seen_tickers.add(pt)
                        found = True
                        break
                if not found:
                    companies_list.append({"company": pt, "ticker": pt})
                    seen_tickers.add(pt)
        if companies_list:
            # Validate each entry
            valid_companies = []
            for cd in companies_list:
                if 'company' in cd and 'ticker' in cd:
                    valid_companies.append(cd)
                else:
                    logger.error(f"Invalid company entry missing keys: {cd}")
            state["companies"] = valid_companies
            logger.debug(f"Extracted companies via regex for highlights: {state['companies']}")
            if not state["companies"]:
                state["response"] = "No valid companies found in the query."
        else:
            # Fallback to LLM if regex finds nothing
            try:
                extract_prompt = PromptTemplate.from_template(
                    """Extract list of companies and their stock tickers from the query: {query}.
                    Output only valid JSON: [{"company": "Full Name", "ticker": "SYMBOL"}, ...]
                    If a term looks like a ticker (uppercase letters), use it as ticker and infer company if possible.
                    If no companies, output []
                    Examples:
                    Query: Give me update on TSLA
                    Output: [{"company": "Tesla", "ticker": "TSLA"}]
                    Query: update on tesla and apple
                    Output: [{"company": "Tesla", "ticker": "TSLA"}, {"company": "Apple", "ticker": "AAPL"}]
                    Query: MSFT
                    Output: [{"company": "Microsoft", "ticker": "MSFT"}]
                    Query: something else
                    Output: []"""
                )
                extract = llm.invoke(extract_prompt.format(query=state["query"])).content.strip()
                logger.debug(f"Raw LLM extract output: {extract}")
                companies_list = json.loads(extract)
                # Validate LLM output
                valid_companies = []
                for cd in companies_list:
                    if isinstance(cd, dict) and 'company' in cd and 'ticker' in cd:
                        ticker = cd['ticker'].upper()
                        if ticker not in seen_tickers:
                            valid_companies.append(cd)
                            seen_tickers.add(ticker)
                    else:
                        logger.error(f"Invalid LLM company entry: {cd}")
                if valid_companies:
                    state["companies"] = valid_companies
                    logger.debug(f"Extracted companies via LLM for highlights: {state['companies']}")
                else:
                    state["response"] = "No companies found in the query."
                    logger.info("No companies extracted for highlights")
            except json.JSONDecodeError as je:
                logger.error(f"JSON decode error in LLM extract: {je} - Raw output: {extract}")
                state["companies"] = []
                state["response"] = "No companies found in the query."
            except Exception as e:
                logger.error(f"Error extracting companies for highlights: {e}")
                state["response"] = "Error extracting companies."
    return state

# Task 1: Generate Full Report
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

@time_it
def generate_report_node(state: AgentState) -> AgentState:
    if state["ticker"]:
        logger.debug(f"Generating report for ticker: {state['ticker']}")
        try:
            date = datetime.now().strftime("%Y-%m-%d")
            filename = f"reports/{state['ticker']}_{date}.md"
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    state["response"] = f.read()
                logger.info(f"Loaded pre-generated report for {state['ticker']}")
            else:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future_data = executor.submit(get_stock_data, state["ticker"])
                    future_news = executor.submit(get_company_news, state["company"])
                    state["data"] = future_data.result()
                    state["news"] = future_news.result()
                clean_news = [re.sub(r'<.*?>', '', item) for item in state["news"]]
                response = llm.invoke(report_prompt.format(data=state["data"], news="\n".join(clean_news))).content
                os.makedirs("reports", exist_ok=True)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(response)
                state["response"] = response
                logger.info(f"Report generated and saved for {state['ticker']}")
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            state["response"] = "Error generating report."
    return state

# Task 2: Generate Overview (use cached report if recent, else generate simple)
@time_it
def generate_overview_node(state: AgentState) -> AgentState:
    if state["ticker"]:
        logger.debug(f"Generating overview for ticker: {state['ticker']}")
        try:
            date = datetime.now().strftime("%Y-%m-%d")
            overview_file = f"overviews/{state['ticker']}_{date}.md"
            if os.path.exists(overview_file):
                with open(overview_file, "r", encoding="utf-8") as f:
                    response = f.read()
                # Append live current price
                try:
                    live_price = yf.Ticker(state['ticker']).info.get('currentPrice')
                    if live_price:
                        response += f"\n\n**Live Current Price:** {live_price}"
                except Exception as e:
                    logger.debug(f"Failed to fetch live price: {e}")
                state["response"] = response
                logger.info(f"Loaded pre-generated overview for {state['ticker']}")
            else:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future_data = executor.submit(get_stock_data, state["ticker"])
                    future_news = executor.submit(get_company_news, state["company"])
                    state["data"] = future_data.result()
                    state["news"] = future_news.result()
                clean_news = [re.sub(r'<.*?>', '', item) for item in state["news"]]
                # Check for recent report as fallback
                report_file = f"reports/{state['ticker']}_{date}.md"
                if os.path.exists(report_file):
                    with open(report_file, "r", encoding="utf-8") as f:
                        report = f.read()
                    overview_prompt = PromptTemplate.from_template("Extract quick overview from report: {report}. Include current price, key highlights, latest news.")
                    state["response"] = llm.invoke(overview_prompt.format(report=report)).content
                    logger.debug("Used existing report for overview")
                else:
                    overview_prompt = PromptTemplate.from_template("Generate quick overview: Company {company}, Price: {price}, Highlights: {data}, News: {news}")
                    state["response"] = llm.invoke(overview_prompt.format(company=state["company"], price=state["data"]["current_price"], data=state["data"], news="\n".join(clean_news))).content
                    logger.debug("Generated new overview")
                # Save overview for future
                os.makedirs("overviews", exist_ok=True)
                with open(overview_file, "w", encoding="utf-8") as f:
                    f.write(state["response"])
                # Save full report after
                generate_report_node(state)
        except Exception as e:
            logger.error(f"Error generating overview: {e}")
            state["response"] = "Error generating overview."
    return state

# Task 3: Company News
@time_it
def get_company_news_node(state: AgentState) -> AgentState:
    try:
        state["news"] = get_company_news(state["company"])
        clean_news = [re.sub(r'<.*?>', '', item) for item in state["news"]]
        if state.get("source") == "cli":
            summary_prompt = PromptTemplate.from_template(
                """Summarize the following news items into key bullet points in a user-friendly way:
{news}"""
            )
            state["response"] = llm.invoke(summary_prompt.format(news="\n\n".join(clean_news))).content
            logger.info(f"Fetched and summarized company news for {state['company']}")
        else:
            state["response"] = "\n\n".join(clean_news)
            logger.info(f"Fetched raw company news for {state['company']}")
    except Exception as e:
        logger.error(f"Error fetching company news: {e}")
        state["response"] = "Error fetching news."
    return state

# Task 4: General News
@time_it
def get_general_news_node(state: AgentState) -> AgentState:
    topic = state["query"].replace("What is the latest news on", "").strip()  # Simple extraction
    try:
        state["news"] = get_general_news(topic)
        clean_news = [re.sub(r'<.*?>', '', item) for item in state["news"]]
        if state.get("source") == "cli":
            summary_prompt = PromptTemplate.from_template(
                """Summarize the following news items into key bullet points in a user-friendly way:
{news}"""
            )
            state["response"] = llm.invoke(summary_prompt.format(news="\n\n".join(clean_news))).content
            logger.info(f"Fetched and summarized general news for topic: {topic}")
        else:
            state["response"] = "\n\n".join(clean_news)
            logger.info(f"Fetched raw general news for topic: {topic}")
    except Exception as e:
        logger.error(f"Error fetching general news: {e}")
        state["response"] = "Error fetching news."
    return state

# Task 5: Highlights
@time_it
def generate_highlights_node(state: AgentState) -> AgentState:
    if not state.get("companies"):
        state["response"] = "No companies to generate highlights for."
        return state

    try:
        def fetch_highlights(cd):
            company = cd['company']
            ticker = cd['ticker']
            # Infer company name if it's just the ticker
            if company == ticker:
                try:
                    company = yf.Ticker(ticker).info.get('shortName', company)
                except Exception as e:
                    logger.debug(f"Failed to infer company for {ticker}: {e}")
            return {
                'company': company,
                'ticker': ticker,
                'stock': get_stock_highlights(ticker),
                'news': get_recent_news(ticker, company)
            }

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(fetch_highlights, cd) for cd in state["companies"]]
            highlights = []
            for f in concurrent.futures.as_completed(futures):
                try:
                    highlights.append(f.result())
                except Exception as exc:
                    logger.error(f"Future raised exception: {exc}")

        if state.get("source") == "cli":
            response_parts = []
            for h in highlights:
                logger.debug(f"Processing highlights for {h.get('company', 'Unknown')} ({h.get('ticker', 'Unknown')})")
                stock = h['stock']
                news = h['news']
                if not news:
                    news_summary = "No recent news available."
                else:
                    clean_news = "\n\n".join(news)
                    summary_prompt = PromptTemplate.from_template(
                        """Summarize the following news items into exactly 5 concise bullet points, 
                        focusing only on news directly related to {company}. 
                        Merge related news points into a single bullet where appropriate to avoid redundancy. 
                        Output only the bullet points, with no additional comments, suggestions, or text. 
                        Each bullet should be clear, user-friendly, and relevant to {company}.
                        {news}"""
                    )
                    news_summary = llm.invoke(summary_prompt.format(company=h['company'], news=clean_news)).content
                part = f"**{h['company']} ({h['ticker']})**\n"
                part += f"Current Price: {stock.get('current_price', 'N/A')}\n"
                daily_change = stock.get('daily_change')
                part += f"Daily Change: {daily_change:.2f}% \n" if daily_change is not None else "Daily Change: N/A\n"
                part += f"50 Day MA: {stock.get('50d_ma', 'N/A')}\n"
                part += f"200 Day MA: {stock.get('200d_ma', 'N/A')}\n"
                part += "Recent News:\n" + news_summary + "\n"
                response_parts.append(part)
            state["response"] = "\n\n".join(response_parts)
            logger.info("Generated summarized highlights for CLI")
        else:
            data = [{
                'company': h['company'],
                'ticker': h['ticker'],
                'current_price': h['stock'].get('current_price'),
                'daily_change': h['stock'].get('daily_change'),
                '50_day_ma': h['stock'].get('50d_ma'),
                '200_day_ma': h['stock'].get('200d_ma'),
                'news': h['news']
            } for h in highlights]
            state["response"] = json.dumps(data if len(data) > 1 else data[0])
            logger.info("Generated raw JSON highlights")
    except Exception as e:
        logger.error(f"Error generating highlights: {e}")
        state["response"] = "Error generating highlights."
    return state

# Build Graph
graph = StateGraph(AgentState)
graph.add_node("router", router_node)
graph.add_node("report", generate_report_node)
graph.add_node("overview", generate_overview_node)
graph.add_node("company_news", get_company_news_node)
graph.add_node("general_news", get_general_news_node)
graph.add_node("highlights", generate_highlights_node)

# Edges
graph.set_entry_point("router")
graph.add_conditional_edges(
    "router",
    lambda state: state["task_type"],
    {
        "1": "report",
        "2": "overview",
        "3": "company_news",
        "4": "general_news",
        "5": "highlights",
    }
)
graph.add_edge("report", END)
graph.add_edge("overview", END)
graph.add_edge("company_news", END)
graph.add_edge("general_news", END)
graph.add_edge("highlights", END)

agent = graph.compile()

@time_it
def run_agent(query: str, source: Optional[str] = None) -> str:
    state = {"query": query, "source": source}
    result = agent.invoke(state)
    return result["response"]