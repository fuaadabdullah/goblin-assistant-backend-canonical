#!/usr/bin/env python3
"""
Local LLM Proxy Service
FastAPI proxy that enforces x-api-key authentication and routes requests
to local Ollama and llama.cpp servers on Kamatera VPS.

This runs as a separate service from the main Goblin Assistant backend,
providing secure access to local LLMs with API key validation.
"""

import os
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Local LLM Proxy", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
API_KEY = os.getenv("LOCAL_LLM_API_KEY", "your-secure-api-key-here")  # Change this!
OLLAMA_URL = "http://localhost:11434"
LLAMACPP_URL = "http://localhost:8080"

# HTTP client with timeout
client = httpx.AsyncClient(timeout=300.0)  # 5 minute timeout for LLM requests


class ChatRequest(BaseModel):
    model: str
    messages: list
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


def verify_api_key(request: Request) -> None:
    """Verify x-api-key header"""
    api_key = request.headers.get("x-api-key")
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    logger.info(f"{request.method} {request.url}")
    response = await call_next(request)
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "local-llm-proxy"}


@app.get("/models")
async def list_models(request: Request):
    """List available models from both Ollama and llama.cpp"""
    verify_api_key(request)

    models = {"ollama": [], "llamacpp": []}

    try:
        # Get Ollama models
        ollama_response = await client.get(f"{OLLAMA_URL}/api/tags")
        if ollama_response.status_code == 200:
            ollama_data = ollama_response.json()
            models["ollama"] = [
                model["name"] for model in ollama_data.get("models", [])
            ]
    except Exception as e:
        logger.error(f"Ollama models error: {e}")

    try:
        # llama.cpp doesn't have a standard models endpoint, so we'll return configured models
        models["llamacpp"] = ["active-model"]  # Update based on your active model
    except Exception as e:
        logger.error(f"llama.cpp models error: {e}")

    return {"models": models}


@app.post("/chat/completions")
async def chat_completions(request: Request):
    """Route chat completions to appropriate local LLM"""
    verify_api_key(request)

    try:
        body = await request.json()
        model = body.get("model", "").lower()

        # Route based on model name
        if any(keyword in model for keyword in ["phi3", "gemma", "qwen", "deepseek"]):
            # Ollama models
            target_url = f"{OLLAMA_URL}/api/chat"
        elif any(keyword in model for keyword in ["llama", "gguf", "active"]):
            # llama.cpp models - convert to llama.cpp format
            target_url = f"{LLAMACPP_URL}/completion"
            # Convert OpenAI format to llama.cpp format
            body = convert_openai_to_llamacpp(body)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model}")

        # Forward the request
        headers = {"Content-Type": "application/json"}
        response = await client.post(target_url, json=body, headers=headers)

        if response.status_code != 200:
            logger.error(f"LLM request failed: {response.status_code} {response.text}")
            raise HTTPException(
                status_code=response.status_code, detail="LLM request failed"
            )

        return Response(
            content=response.content, media_type=response.headers.get("content-type")
        )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM request timeout")
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


def convert_openai_to_llamacpp(openai_body: Dict[str, Any]) -> Dict[str, Any]:
    """Convert OpenAI chat format to llama.cpp completion format"""
    messages = openai_body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Extract the last user message as prompt
    prompt = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            prompt = msg.get("content", "")
            break

    if not prompt:
        raise HTTPException(status_code=400, detail="No user message found")

    # Build llama.cpp format
    llamacpp_body = {
        "prompt": prompt,
        "n_predict": openai_body.get("max_tokens", 512),
        "temperature": openai_body.get("temperature", 0.7),
        "stop": ["\n\n", "###"],  # Common stop sequences
        "stream": openai_body.get("stream", False),
    }

    return llamacpp_body


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await client.aclose()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
