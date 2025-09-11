# Stella: Financial Data and News Analysis Tool
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


Stella is a Python-based application that provides financial data and news analysis for stocks and general topics. It supports generating detailed stock reports, company overviews, company news, general news, and stock highlights using data from yFinance, Alpha Vantage, and Brave Search APIs. The application can be interacted with via a command-line interface (CLI) or an API endpoint.

## Features

- **Stock Report**: Generate comprehensive stock reports including price, market profile, business description, news, and risk metrics.
- **Company Overview**: Fetch concise overviews of companies with key metrics and recent news.
- **Company News**: Retrieve and summarize the latest news for a specific company.
- **General News**: Fetch news on general topics like technology or markets.
- **Highlights**: Get quick updates on stock prices, daily changes, moving averages, and summarized news for one or more companies.
- **Caching**: Efficiently cache data and news to reduce API calls and improve performance.
- **Concurrent Processing**: Fetch data and news in parallel for faster responses.

## Prerequisites

- Python 3.8+
- Required Python packages (install via `pip install -r requirements.txt`):
  - `requests`
  - `yfinance`
  - `numpy`
  - `pandas`
  - `langchain-openai`
  - `langgraph`
  - `python-dotenv`
- API keys:
  - OpenAI API key (for LLM based summarization and classification)
  - Alpha Vantage API key (for stock data and news) - free API available with limits. 
  - Brave Search API key (news fetching)
- A running server for API usage (see Setup section)

## Setup

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd stella
   ```

2. **Install Dependencies**:
   Create a virtual environment and install required packages:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the project root with the following:
   ```plaintext
   OPENAI_API_KEY=your_openai_api_key
   ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key
   BRAVE_API_KEY=your_brave_api_key
   DEBUG_MODE=false #True for detailed logs during debugging. 
   ```

4. **Start the Server** (for API usage):
   Ensure the server (FastAPI) is running to handle API requests:
   ```bash
   uvicorn app:app --host 127.0.0.1 --port 8001
   ```
   Replace `app:app` with the actual FastAPI application module if different. Replace port number with a port number of your choosing. 

## Usage

### Command Line Interface (CLI)

Run `cli.py` to interact with Stella via the command line. The CLI supports both single query execution and an interactive mode.

#### Single Query
Execute a single query directly from the command line:
```bash
python cli.py "5: Give me todays update on Tesla"
```
This will fetch and display highlights for Tesla, including stock metrics and summarized news.

#### Interactive Mode
Run without arguments to enter interactive mode:
```bash
python cli.py
```
You'll see a welcome message with example queries:
```
Welcome to Stella!
Enter a query below or type 'exit' to quit.
Examples:
1. Stock Report: '1: Generate a stock report for Tesla'
2. Company Overview: '2: Give me an overview of Microsoft'
3. Company News: '3: What is the latest news on Apple'
4. General News: '4: Latest news on artificial intelligence'
5. Highlights: '5: Give me todays update on Tesla, Apple, and Microsoft'
--------------------------------------------------

Enter your query:
```
Enter a query (Example: `5: Give me todays update on Tesla, Apple`) or type `exit` to quit. Use the task number prefix (1-5) to specify the query type.

### API Usage

Stella provides an API endpoint at `http://localhost:8001/analyze` for programmatic access. Send a POST request with a JSON payload containing the query and source.

#### Example Request
```bash
curl -X POST "http://localhost:8001/analyze" \
-H "Content-Type: application/json" \
-d '{"query": "5: Give me todays update on Tesla", "source": "cli"}'
```

#### Payload Format
- `query`: The query string, optionally prefixed with a task number (1-5).
- `source`: Set to `"cli"` for summarized, human-readable output (Markdown format), or omit for raw JSON output.

#### Example Response (CLI source)
```json
{
  "result": "**Tesla (TSLA)**\nCurrent Price: 347.79\nDaily Change: 0.24%\n50 Day MA: 325.56\n200 Day MA: 330.38\nRecent News:\n- Tesla's US EV market share falls below 40%...\n..."
}
```

#### Example Response (non-CLI source)
```json
{
  "result": {
    "company": "Tesla",
    "ticker": "TSLA",
    "current_price": 347.79,
    "daily_change": 0.24,
    "50_day_ma": 325.56,
    "200_day_ma": 330.38,
    "news": ["Tesla's US EV market share falls below 40%...", "..."]
  }
}
```

#### Notes
- Ensure the server is running before sending API requests.
- The `source: "cli"` option formats output as Markdown for readability; without it, raw JSON data is returned.
- Invalid queries or server errors return an error message in the `result` field.

## Project Structure

- `agent.py`: Core logic for query routing, data processing, and response generation using LangGraph and LangChain.
- `cli.py`: Command-line interface for interactive and single-query usage.
- `tools.py`: Utilities for fetching stock data (yFinance, Alpha Vantage) and news (Brave, Alpha Vantage, yFinance).
- `cache.py`: Caching logic for stock data and news to optimize performance (not shown but referenced in `tools.py`).
- `.env`: Environment variables for API keys and configuration.

## Task Types

1. **Stock Report**: Detailed report with company metrics, news, and risk analysis (Example:  `1: Generate a stock report for Tesla`).
2. **Company Overview**: Concise summary of a company’s key metrics and news (Example:  `2: Give me an overview of Microsoft`).
3. **Company News**: Latest news for a specific company (Example:  `3: What is the latest news on Apple`).
4. **General News**: News on a general topic (Example:  `4: Latest news on artificial intelligence`).
5. **Highlights**: Quick stock metrics and up to 5 news summaries for one or more companies (Example:  `5: Give me todays update on Tesla, Apple`).

* Please Note: The number (for example `4: ...`) isn't strictly necessary. It is just a way to reduce a LLM call for intent classification. In addition, I have listed some common companies and their tickers in agent.py to reduce the amount of LLM calls needed to extract the intent and ticker. A query such as `Generate a report for me on Tesla` will work, it will just trigger a additional LLM call for intent classification. 

## Notes

- **Caching**: Stock data and news are cached to reduce API calls. Cache duration is managed in `cache.py` (not shown).
- **Error Handling**: The application handles API failures, invalid tickers, and network issues gracefully, returning user-friendly error messages. This includes handling API Limits from Alpha Vantage API. 
- **Performance**: Concurrent data fetching is used for highlights to improve response times for multiple companies.
- **Debugging**: Set `DEBUG_MODE=true` in `.env` to enable detailed logging for troubleshooting.

- The Business Report generated may include price targets. These price targets are analysts recommendations retrieved from yfinance. This is not intended to be financial advice. 

- I found that `gpt-5-nano` works well for my needs and is relatively cost-effective. Alternative OpenAI Models may be better suited for your needs.

## Contributing

Contributions are welcome! Please submit pull requests or open issues for bugs, feature requests, or improvements.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.