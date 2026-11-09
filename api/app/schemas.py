from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class Citation(BaseModel):
    category: str
    title: str
    anchor: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    suggested_followups: list[str]
    categories: list[str] | None = None


class MatchJdRequest(BaseModel):
    job_description: str | None = Field(default=None, max_length=8000)
    jd: str | None = Field(default=None, max_length=8000)

    def text(self) -> str:
        return (self.job_description or self.jd or "").strip()


class MatchJdResponse(BaseModel):
    summary: str
    citations: list[Citation]


class HealthResponse(BaseModel):
    api: str
    db: str
    schema_status: str = "pending"
    llm: str = "auto"


class SuggestionsResponse(BaseModel):
    suggestions: list[str]


class SeedResponse(BaseModel):
    status: str
    counts: dict[str, int]
