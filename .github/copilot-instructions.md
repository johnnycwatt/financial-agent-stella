# Stella Financial Agent - AI Coding Guidelines

## Architecture Overview

Stella is a Python-based financial analysis agent using LangGraph for stateful query processing. Core components:

- **`agent.py`**: LangGraph state machine with nodes for query routing, data fetching, and response generation. Uses concurrent execution for performance.
- **`app.py`**: FastAPI server exposing `/analyze` and `/batch_analyze` endpoints.
- **`tools.py`**: Data fetching utilities prioritizing yFinance, with Alpha Vantage/Brave Search fallbacks.
- **`cache.py`**: File-based caching with different expiration times (5min for highlights, 24hr for data/news).
- **`pregenerate_data.py`**: Daily pregeneration of reports/overviews to reduce LLM calls and API usage.

Data flows: Query → Router (classify/extract) → Task-specific node (fetch data concurrently) → LLM summarization → Response.

## Key Workflows

### Setup and Development
- Install dependencies: `pip install -r requirements.txt`
- Configure `.env` with API keys: `OPENAI_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `BRAVE_API_KEY`, `DEBUG_MODE`, `USE_OPENAI`
- Start server: `uvicorn app:app --host 127.0.0.1 --port 8001`
- CLI usage: `python cli.py` (interactive) or `python cli.py "5: Give me todays update on Tesla"`
- Web UI: `pip install -r frontend/requirements.txt && streamlit run frontend/stella.py`

### Data Pregeneration
Run `python pregenerate_data.py --all` daily to cache reports/overviews for common companies. Reduces response time and API costs.

### Debugging
Set `DEBUG_MODE=true` in `.env` for detailed logging. Use `@time_it` decorator on functions for performance monitoring.

## Project Conventions

### Query Processing
- Task prefixes (`1:`, `2:`, etc.) bypass LLM classification for efficiency.
- Common companies dict in `agent.py` avoids LLM extraction calls.
- Regex extraction for tickers before LLM fallback.
- Follow-up patterns (`tell me more about`, `explain`, etc.) automatically detected for task type 6.

### Data Fetching Patterns
- Concurrent fetching with `ThreadPoolExecutor` for multi-company highlights.
- Fallback chains: yFinance → Alpha Vantage → Brave Search.
- Cache-first approach with file expiration checks.

### Response Formatting
- CLI source: Markdown summaries with LLM bullet points.
- API source: Raw JSON data structures.
- Pregenerated files loaded directly when available.

### Error Handling
- Graceful API failures with empty dicts/lists returned.
- LLM errors default to safe fallbacks (e.g., general news).
- User-friendly error messages in responses.

## Integration Points

### External APIs
- **yFinance**: Primary for stock data/history (free, reliable).
- **Alpha Vantage**: Fallback for highlights/news (API limits, paid for heavy use).
- **Brave Search**: News fetching (requires API key).
- **OpenAI**: LLM for summarization/classification (use `gpt-5-nano` for cost-efficiency).
- **LM Studio**: Local LLM alternative (set `USE_OPENAI=false` for `qwen/qwen3-4b-2507` at `http://127.0.0.1:1234`).

### Data Storage
- JSON files in `data/` for metrics/highlights/news.
- Markdown files in `reports/` and `overviews/` for pregenerated content.
- CSV history in `data/` for analysis.

### Dependencies
- LangChain/LangGraph for agent orchestration.
- FastAPI for web server.
- Pandas/NumPy for data processing.

## Common Patterns

- Use `concurrent.futures.ThreadPoolExecutor` for parallel data fetching.
- Check cache before API calls using `get_cached_*` functions.
- Strip HTML from news with `re.sub(r'<.*?>', '', text)`.
- Format responses based on `source` parameter ("cli" vs raw).
- Handle missing data gracefully with `.get()` on dicts.
- Maintain chat history for follow-up queries (last 10 interactions).
- Frontend LLM processing enhances responses for Streamlit UI (separate from core API).

## Examples

### Adding New Company
Update `common_companies` dict in `agent.py` and `companies` dict in `pregenerate_data.py`.

### Modifying Response Format
Edit prompts in `agent.py` nodes, ensure CLI vs API differentiation.

### Extending Data Sources
Add fallback logic in `tools.py` functions, maintain cache integration.