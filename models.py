from pydantic import BaseModel
from typing import Optional, List

class QueryRequest(BaseModel):
    query: str
    source: Optional[str] = None
    chat_history: Optional[List[dict]] = None

class AnalysisResponse(BaseModel):
    result: str