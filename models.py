from pydantic import BaseModel
from typing import Optional

class QueryRequest(BaseModel):
    query: str
    source: Optional[str] = None

class AnalysisResponse(BaseModel):
    result: str