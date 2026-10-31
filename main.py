import base64
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

load_dotenv()

import voice
from engine import MAX_PHOTOS, Engine, Session
from models import Gemma

sessions: dict[str, Session] = {}
engine = Engine(Gemma())


@asynccontextmanager
async def lifespan(_: FastAPI):
    required = ["GEMINI_API_KEY", "ELEVENLABS_API_KEY"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing in .env: {', '.join(missing)}")
    if not os.getenv("TAVILY_API_KEY"):
        print("TAVILY_API_KEY not set: web search is off, so guides use general knowledge and photos only")
    yield


app = FastAPI(lifespan=lifespan)


class Turn(BaseModel):
    session_id: str
    text: str


class Vision(BaseModel):
    session_id: str
    image: str


class Photos(BaseModel):
    session_id: str
    images: list[str]


class Live(BaseModel):
    session_id: str
    image: str
    question: str = ""


class Speech(BaseModel):
    text: str


def session(session_id: str) -> Session:
    return sessions.setdefault(session_id, Session())


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/api/turn")
async def turn(body: Turn):
    return await engine.turn(session(body.session_id), body.text[:1000])


@app.post("/api/vision")
async def vision(body: Vision):
    try:
        base64.b64decode(body.image, validate=True)
    except ValueError:
        raise HTTPException(400, "Invalid image")
    return await engine.vision(session(body.session_id), body.image)


@app.post("/api/photos")
async def photos(body: Photos):
    if not 1 <= len(body.images) <= MAX_PHOTOS:
        raise HTTPException(400, f"Send 1 to {MAX_PHOTOS} photos")
    try:
        for image in body.images:
            base64.b64decode(image, validate=True)
    except ValueError:
        raise HTTPException(400, "Invalid image")
    return await engine.add_photos(session(body.session_id), body.images)


@app.post("/api/live")
async def live(body: Live):
    try:
        base64.b64decode(body.image, validate=True)
    except ValueError:
        raise HTTPException(400, "Invalid image")
    return await engine.live(session(body.session_id), body.image, body.question[:300])


@app.post("/api/tts")
async def tts(body: Speech):
    try:
        return Response(await voice.tts(body.text[:1000]), media_type="audio/mpeg")
    except httpx.HTTPError:
        raise HTTPException(502, "Speech service failed")