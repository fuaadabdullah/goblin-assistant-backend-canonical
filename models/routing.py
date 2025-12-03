"""
Routing database models for provider registry, metrics, and policies.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    JSON,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class RoutingProvider(Base):
    """Represents a routing provider (OpenAI, Anthropic, etc.) with capabilities and configuration."""

    __tablename__ = "routing_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(100), nullable=False, unique=True
    )  # e.g., "openai", "anthropic"
    display_name = Column(String(200), nullable=False)  # e.g., "OpenAI", "Anthropic"
    base_url = Column(String(500), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)  # Encrypted API key
    is_active = Column(Boolean, default=True)
    capabilities = Column(JSON, nullable=False)  # List of supported capabilities
    models = Column(JSON, nullable=False)  # List of available models
    rate_limits = Column(JSON, nullable=True)  # Rate limiting configuration
    cost_per_token = Column(Float, nullable=True)  # Cost per token in USD
    priority = Column(Integer, default=0)  # Higher priority = preferred
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    metrics = relationship(
        "ProviderMetric", back_populates="provider", cascade="all, delete-orphan"
    )
    policies = relationship(
        "ProviderPolicy", back_populates="provider", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<RoutingProvider(name='{self.name}', active={self.is_active})>"


class ProviderMetric(Base):
    """Metrics collected for provider health monitoring."""

    __tablename__ = "provider_metrics"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("routing_providers.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Health metrics
    is_healthy = Column(Boolean, nullable=False)
    response_time_ms = Column(Float, nullable=True)  # Average response time
    error_rate = Column(Float, default=0.0)  # Error rate (0.0 to 1.0)
    throughput_rpm = Column(Float, nullable=True)  # Requests per minute

    # Resource metrics
    tokens_used = Column(Integer, nullable=True)
    cost_incurred = Column(Float, nullable=True)

    # Additional metadata
    metadata_json = Column(JSON, nullable=True)  # Additional metric data

    # Relationships
    provider = relationship("RoutingProvider", back_populates="metrics")


class ProviderPolicy(Base):
    """Policies for routing decisions (fallback, load balancing, etc.)."""

    __tablename__ = "provider_policies"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("routing_providers.id"), nullable=False)
    name = Column(String(100), nullable=False)  # e.g., "fallback", "load_balance"
    policy_type = Column(
        String(50), nullable=False
    )  # "fallback", "load_balance", "circuit_breaker"
    conditions = Column(JSON, nullable=False)  # Conditions for policy activation
    actions = Column(JSON, nullable=False)  # Actions to take when conditions met
    priority = Column(Integer, default=0)  # Policy priority
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    provider = relationship("RoutingProvider", back_populates="policies")

    def __repr__(self):
        return f"<ProviderPolicy(provider_id={self.provider_id}, name='{self.name}', type='{self.policy_type}')>"


class RoutingRequest(Base):
    """Log of routing requests for analytics and debugging."""

    __tablename__ = "routing_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(100), nullable=False, unique=True)
    capability = Column(String(100), nullable=False)
    requirements = Column(JSON, nullable=True)  # Specific requirements for the request
    selected_provider_id = Column(
        Integer, ForeignKey("routing_providers.id"), nullable=True
    )
    response_time_ms = Column(Float, nullable=True)
    success = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    selected_provider = relationship("RoutingProvider")

    def __repr__(self):
        return f"<RoutingRequest(id='{self.request_id}', capability='{self.capability}', success={self.success})>"
