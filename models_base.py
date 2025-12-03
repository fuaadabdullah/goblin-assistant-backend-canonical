from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    JSON,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

# Import Base from database.py to use the same declarative base
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String)
    name = Column(String)
    google_id = Column(String, unique=True)
    passkey_credential_id = Column(String)
    passkey_public_key = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tasks = relationship("Task", back_populates="user")
    streams = relationship("Stream", back_populates="user")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    goblin = Column(String, nullable=False)
    task = Column(Text, nullable=False)
    code = Column(Text)
    provider = Column(String)
    model = Column(String)
    status = Column(
        String, default="queued"
    )  # queued, running, completed, failed, cancelled
    result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="tasks")


class Stream(Base):
    __tablename__ = "streams"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    goblin = Column(String, nullable=False)
    task = Column(Text, nullable=False)
    code = Column(Text)
    provider = Column(String)
    model = Column(String)
    status = Column(String, default="running")  # running, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="streams")
    chunks = relationship(
        "StreamChunk", back_populates="stream", cascade="all, delete-orphan"
    )


class StreamChunk(Base):
    __tablename__ = "stream_chunks"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(String, ForeignKey("streams.id"), nullable=False)
    content = Column(Text)
    token_count = Column(Integer)
    cost_delta = Column(Float)
    done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    stream = relationship("Stream", back_populates="chunks")


class SearchCollection(Base):
    __tablename__ = "search_collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    documents = relationship(
        "SearchDocument", back_populates="collection", cascade="all, delete-orphan"
    )


class SearchDocument(Base):
    __tablename__ = "search_documents"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("search_collections.id"), nullable=False)
    document_id = Column(String, nullable=False)  # External document ID
    document = Column(Text, nullable=False)
    document_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    collection = relationship("SearchCollection", back_populates="documents")

    __table_args__ = (
        {"schema": None},  # Default schema
    )
