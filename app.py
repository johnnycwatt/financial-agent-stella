import logging
import time
from fastapi import FastAPI, Body
from models import QueryRequest, AnalysisResponse
from agent import run_agent
from dotenv import load_dotenv
import os
from typing import List
import concurrent.futures

load_dotenv()
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.post("/analyze", response_model=AnalysisResponse)
def analyze(query: QueryRequest):
    logger.info(f"Incoming query: {query.query}")
    start_time = time.time()
    try:
        result = run_agent(query.query, source=query.source)
        end_time = time.time()
        logger.info(f"Time taken to process query: {end_time - start_time:.2f}s")
        logger.info(f"Response sent (length: {len(result)} characters)")
        if DEBUG_MODE:
            logger.debug(f"Response preview: {result[:200]}...")
        return AnalysisResponse(result=result)
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        end_time = time.time()
        logger.info(f"Time taken (error): {end_time - start_time:.2f}s")
        return AnalysisResponse(result="An error occurred during processing.")

@app.post("/batch_analyze", response_model=List[AnalysisResponse])
def batch_analyze(queries: List[QueryRequest] = Body(...)):
    logger.info(f"Incoming batch queries: {len(queries)}")
    start_time = time.time()
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(run_agent, q.query, source=q.source) for q in queries]
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(AnalysisResponse(result=future.result()))
        end_time = time.time()
        logger.info(f"Time taken to process batch: {end_time - start_time:.2f}s")
        return results
    except Exception as e:
        logger.error(f"Error processing batch: {e}")
        end_time = time.time()
        logger.info(f"Time taken (error): {end_time - start_time:.2f}s")
        return [AnalysisResponse(result="An error occurred during processing.") for _ in queries]