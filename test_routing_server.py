#!/usr/bin/env python
"""
Minimal test server for routing functionality only.
"""

import uvicorn
import sys

# Add the backend directory to Python path
sys.path.insert(0, "/Users/fuaadabdullah/ForgeMonorepo/apps/goblin-assistant/backend")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Database imports
from database import create_tables

# Routing imports
from routing_router import router as routing_router

app = FastAPI(
    title="Routing Test Server",
    description="Minimal server for testing routing functionality",
    version="1.0.0",
)


# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    create_tables()
    print("Database tables created")


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routing router
app.include_router(routing_router)


@app.get("/")
async def root():
    return {"message": "Routing Test Server API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
