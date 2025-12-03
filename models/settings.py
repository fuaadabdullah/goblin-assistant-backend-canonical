from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)  # e.g., "openai", "anthropic"
    display_name = Column(String)
    capabilities = Column(JSON)  # List of capabilities like ["chat", "embedding"]
    default_model = Column(String, nullable=True)
    metadata_ = Column(JSON, nullable=True)  # Additional config
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    credentials = relationship("ProviderCredential", back_populates="provider")
    models = relationship("ModelConfig", back_populates="provider")


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"))
    encrypted_key = Column(Text)  # Encrypted API key using cryptography
    scopes = Column(JSON, nullable=True)  # e.g., ["read", "write"]
    created_by = Column(String)  # User ID or "system"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    provider = relationship("Provider", back_populates="credentials")


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"))
    name = Column(String)  # e.g., "gpt-4", "claude-3"
    params = Column(JSON)  # Model parameters like max_tokens, temperature
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    provider = relationship("Provider", back_populates="models")


class GlobalSetting(Base):
    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True)
    value = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
