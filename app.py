
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import run_travel_agent


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="TripMate AI",
    description="LangGraph Multi-Agent Travel Planner API",
    version="1.0.0"
)

# Allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount static files only if the folder exists
STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static"
    )


# -------------------------
# Request Schema
# -------------------------

class ChatRequest(BaseModel):

    message: str = Field(
        ...,
        min_length=1,
        max_length=8000
    )

    thread_id: str | None = None

    travel_date: str | None = None


# -------------------------
# Response Schema
# -------------------------

class ChatResponse(BaseModel):

    thread_id: str

    answer: str

    trip_context: dict = Field(default_factory=dict)


# -------------------------
# Home Endpoint
# -------------------------

@app.get("/")
def home():

    return {
        "message": "TripMate AI API is running",
        "status": "Online",
        "documentation": "/docs"
    }


# -------------------------
# Health Endpoint
# -------------------------

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# -------------------------
# Travel Chat Endpoint
# -------------------------

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    try:

        thread_id = request.thread_id or str(uuid4())

        result = run_travel_agent(
            user_input=request.message,
            travel_date=request.travel_date or "",
            thread_id=thread_id
        )

        # Support either dictionary or string responses
        if isinstance(result, dict):

            answer = (
                result.get("answer")
                or result.get("response")
                or result.get("output")
                or result.get("final_answer")
                or str(result)
            )

            trip_context = result.get("trip_context", {})

        else:

            answer = str(result)
            trip_context = {}

        return ChatResponse(
            thread_id=thread_id,
            answer=answer,
            trip_context=trip_context
        )

    except Exception as error:

        print("TripMate API Error:", repr(error))

        raise HTTPException(
            status_code=500,
            detail="Unable to generate travel plan. Check backend logs."
        ) from error
