from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(..., description="The query question for the financial documents.")
    limit: int = Field(default=3, ge=1, le=10, description="The maximum number of matching pages to retrieve.")

class QueryResponse(BaseModel):
    question: str
    answer: str
    pages_retrieved: int
    images: list[str] = Field(default=[], description="List of base64 encoded images of matching pages.")
