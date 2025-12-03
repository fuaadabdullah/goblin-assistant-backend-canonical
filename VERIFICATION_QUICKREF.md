# Verification & Confidence Scoring - Quick Reference

## Overview

Two-layer quality assurance for LLM outputs with automatic escalation.

## Models

| Model | Purpose | Threshold |
|-------|---------|-----------|
| `llama3.2:3b-instruct` | Safety verification | 0.7 |
| `phi3:3.8b` | Confidence scoring | 0.65 |

## Escalation Chain

```
gemma:2b → phi3:3.8b → qwen2.5:3b → mistral:7b
```

## API Usage

### Enable (Default)

```json
{
  "messages": [...],
  "enable_verification": true,
  "enable_confidence_scoring": true,
  "auto_escalate": true
}
```

### Disable (For Speed)

```json
{
  "messages": [...],
  "enable_verification": false,
  "enable_confidence_scoring": false
}
```

## Response Fields

```json
{
  "verification_result": {
    "is_safe": true,
    "safety_score": 0.85,
    "issues": [],
    "explanation": "..."
  },
  "confidence_result": {
    "confidence_score": 0.78,
    "reasoning": "...",
    "recommended_action": "accept"
  },
  "escalated": true,
  "original_model": "gemma:2b"
}
```

## Decision Logic

| Condition | Action |
|-----------|--------|
| `is_safe = false` | ❌ Reject (HTTP 422) |
| `confidence < 0.4` | ❌ Reject (HTTP 422) |
| `confidence < 0.65` | 🔄 Escalate to next model |
| `confidence >= 0.65` AND `is_safe = true` | ✅ Accept |

## Performance

- **Overhead:** +2-4s per request
- **With escalation:** +10-15s total
- **Models needed:** llama3.2:3b-instruct, phi3:3.8b

## Testing

```bash
python test_verification_scoring.py
```

## Files

- `services/output_verification.py` - Core logic
- `chat_router.py` - API integration
- `VERIFICATION_SCORING.md` - Full docs

## Quick Deploy

```bash
# Pull verifier model
ollama pull llama3.2:3b-instruct

# Test
python test_verification_scoring.py

# Start backend
uvicorn main:app --reload
```

---

**Status:** ✅ Production-ready
