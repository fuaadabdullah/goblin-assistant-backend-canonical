# GoblinOS Assistant Backend — Canonical Repository

This is the **canonical backend repository** for GoblinOS Assistant, containing all backend code and documentation (excluding infrastructure).

## Overview

A FastAPI-based backend service that provides:
- Intelligent routing of chat and debug requests to local/cloud LLM providers
- User authentication (JWT, Google OAuth, WebAuthn passkeys)
- Task execution orchestration via GoblinOS integration
- Monitoring, structured logs, and Prometheus metrics
- Background health probes for providers and RQ/Redis workers

## Architecture

**Core Technologies:**
- Python 3.11+
- FastAPI (async web framework)
- SQLAlchemy (ORM for SQLite/PostgreSQL)
- Redis + RQ (background task processing)
- Prometheus (metrics collection)
- Structured logging with JSON output

**Key Components:**
- `main.py` - FastAPI application entry point
- `auth/` - Authentication modules (OAuth, passkeys)
- `providers/` - LLM provider adapters (OpenAI, Anthropic, etc.)
- `services/` - Business logic services
- `middleware/` - Request processing middleware
- `models/` - Database models and schemas
- `docs/` - Comprehensive documentation

## Quick Start

### Prerequisites
- Python 3.11+
- Redis (for background tasks)
- PostgreSQL or SQLite (database)

### Setup

1. **Clone and setup environment:**
```bash
git clone https://github.com/fuaadabdullah/goblin-assistant-backend-canonical.git
cd goblin-assistant-backend-canonical
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your configuration:
# - DATABASE_URL
# - JWT_SECRET_KEY
# - API keys for LLM providers
# - Redis connection details
```

3. **Initialize database:**
```bash
alembic upgrade head
```

4. **Start the server:**
```bash
uvicorn main:app --reload --port 8001
```

5. **Verify health:**
```bash
curl http://localhost:8001/health
```

## API Endpoints

### Core Endpoints
- `GET /` - API root
- `GET /health` - Health check
- `POST /chat/completions` - Chat completions with intelligent routing
- `POST /auth/login` - User authentication
- `GET /dashboard/metrics` - System metrics

### Development Endpoints
- `POST /debugger/suggest` - Code debugging assistance
- `POST /execute/code` - Code execution
- `GET /settings` - Configuration management

## Development

### Running Tests
```bash
pytest
# Or run specific test categories:
pytest tests/test_health_router.py
pytest test_chat_api.py
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

### Code Quality
- Uses `black` for formatting
- `flake8` for linting
- `mypy` for type checking

## Documentation

See `docs/` directory for comprehensive documentation:
- `SETUP_GUIDE.md` - Detailed setup instructions
- `PRODUCTION_DEPLOYMENT_GUIDE.md` - Production deployment
- `TESTING_IMPLEMENTATION_SUMMARY.md` - Testing documentation
- `ENDPOINT_AUDIT.md` - API endpoint documentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Ensure all tests pass
5. Submit a pull request

## License

See LICENSE file for details.

## Related Repositories

- [GoblinOS Assistant Frontend](https://github.com/fuaadabdullah/goblin-assistant-frontend)
- [GoblinOS Core](https://github.com/fuaadabdullah/goblinos-core)
