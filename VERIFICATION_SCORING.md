# Output Verification & Confidence Scoring

## Overview

The Goblin Assistant now includes **two-layer quality assurance** for LLM outputs:

1. **Safety Verifier** - Uses `llama3.2:3b-instruct` (3B instruction-tuned model) to check for:
   - Hallucinations
   - Harmful content
   - Bias
   - Off-topic responses
   - Overconfidence

2. **Confidence Scorer** - Uses `phi3:3.8b` to evaluate output quality and determine escalation needs:
   - Relevance
   - Completeness
   - Accuracy
   - Clarity
   - Overall confidence

## Architecture

```
User Request
    ↓
Routing Service (selects initial model)
    ↓
Model Generation (e.g., gemma:2b)
    ↓
┌─────────────────────────────────────┐
│  Verification Pipeline              │
│  ├─ Safety Verifier (llama3.2:3b)  │  → Is output safe?
│  └─ Confidence Scorer (phi3:3.8b)  │  → Is quality sufficient?
└─────────────────────────────────────┘
    ↓
Decision:
  • Accept (high confidence, safe)
  • Escalate (low confidence) → Retry with better model
  • Reject (unsafe or critically low confidence)
```

## Models

### Safety Verifier: `llama3.2:3b-instruct`

- **Size:** 3B parameters
- **Optimized for:** Instruction following, alignment, safety
- **Temperature:** 0.0 (deterministic)
- **Purpose:** Detect safety issues before returning to user

### Confidence Scorer: `phi3:3.8b`

- **Size:** 3.8B parameters
- **Optimized for:** Low-latency reasoning
- **Temperature:** 0.0 (deterministic)
- **Purpose:** Evaluate output quality and trigger escalation

## Thresholds

### Safety Thresholds

- **Safety Score:** 0.0 to 1.0
- **Pass Threshold:** ≥ 0.7
- **Reject if:** `is_safe = False` OR critical issues detected

### Confidence Thresholds

- **Confidence Score:** 0.0 to 1.0
- **Escalation Threshold:** < 0.65 (escalate to better model)
- **Critical Threshold:** < 0.4 (reject immediately)

### Escalation Chain

```
gemma:2b (ultra-fast)
    ↓
phi3:3.8b (low-latency)
    ↓
qwen2.5:3b (long-context)
    ↓
mistral:7b (highest quality)
    ↓
No further escalation (top tier)
```

## API Usage

### Chat Completions Endpoint

```bash
POST /chat/completions
```

**Request Body:**

```json
{
  "messages": [
    {"role": "user", "content": "Your question here"}
  ],
  "enable_verification": true,        // Default: true
  "enable_confidence_scoring": true,  // Default: true
  "auto_escalate": true                // Default: true
}
```

**Response (with verification):**

```json
{
  "id": "request-uuid",
  "model": "mistral:7b",
  "provider": "Ollama Local",
  "intent": "explain",
  "escalated": true,
  "original_model": "gemma:2b",
  "verification_result": {
    "is_safe": true,
    "safety_score": 0.85,
    "issues": [],
    "explanation": "Output is safe and appropriate"
  },
  "confidence_result": {
    "confidence_score": 0.78,
    "reasoning": "Response is complete and accurate",
    "recommended_action": "accept"
  },
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Model's response here..."
      },
      "finish_reason": "stop"
    }
  ]
}
```

## Example Scenarios

### Scenario 1: Low Confidence → Escalation

**User:** "Explain quantum entanglement in detail"

**Initial Model:** `gemma:2b`

**Response:** "Quantum stuff is complicated."

**Verification:**
- ✅ Safe (no harmful content)
- ❌ Low confidence (0.3 - incomplete)

**Action:** Escalate to `phi3:3.8b`

**New Response:** "Quantum entanglement is a phenomenon where particles become correlated..."

**Verification:**
- ✅ Safe
- ✅ High confidence (0.75)

**Result:** Return improved response to user

---

### Scenario 2: Safety Issue → Rejection

**User:** "I have a fever. What medication should I take?"

**Initial Model:** `phi3:3.8b`

**Response:** "You should take 800mg of ibuprofen every 4 hours."

**Verification:**
- ❌ Unsafe (medical advice without disclaimer)
- ⚠️ Issues: `["harmful_content", "overconfidence"]`

**Action:** Reject with HTTP 422

**Error Response:**
```json
{
  "error": "Output rejected due to safety or quality concerns",
  "verification": {
    "is_safe": false,
    "safety_score": 0.4,
    "issues": ["harmful_content", "overconfidence"]
  }
}
```

---

### Scenario 3: High Quality → Accept

**User:** "What is the capital of France?"

**Initial Model:** `mistral:7b`

**Response:** "The capital of France is Paris."

**Verification:**
- ✅ Safe (1.0)
- ✅ High confidence (0.95)

**Action:** Return immediately (no escalation needed)

---

## Configuration

### Environment Variables

```bash
# Ollama endpoint
LOCAL_LLM_PROXY_URL=http://45.61.60.3:8002

# API key
LOCAL_LLM_API_KEY=your-secure-key

# Optional: Override thresholds
SAFETY_THRESHOLD=0.7          # Default: 0.7
CONFIDENCE_THRESHOLD=0.65     # Default: 0.65
CRITICAL_THRESHOLD=0.4        # Default: 0.4
```

### Disabling Verification (for speed)

For use cases where speed is critical and safety is less of a concern:

```json
{
  "messages": [...],
  "enable_verification": false,
  "enable_confidence_scoring": false
}
```

This skips both verification and confidence scoring, reducing latency by ~2-3 seconds.

---

## Testing

### Run Verification Tests

```bash
cd apps/goblin-assistant/backend
python test_verification_scoring.py
```

**Test Coverage:**

1. **Safety Verifier Tests** (6 scenarios)
   - Safe factual response
   - Hallucination detection
   - Harmful medical advice
   - Appropriate refusal
   - Overconfidence detection
   - Balanced political response

2. **Confidence Scorer Tests** (6 scenarios)
   - High quality code
   - Incomplete response
   - Off-topic response
   - Good conversational response
   - Vague response
   - Comprehensive explanation

3. **Escalation Pipeline Tests** (3 scenarios)
   - Low confidence triggers escalation
   - Safety issue triggers rejection
   - High quality output accepted

---

## Performance Impact

### Latency Overhead

- **Safety Verification:** +1-2 seconds (llama3.2:3b-instruct)
- **Confidence Scoring:** +1-2 seconds (phi3:3.8b)
- **Total Overhead:** +2-4 seconds per request

### When to Disable

Consider disabling for:
- Ultra-low latency requirements (< 5s total)
- Internal/trusted use cases
- Non-user-facing applications
- High-volume batch processing

### When to Enable (Recommended)

Always enable for:
- User-facing applications
- Medical/financial/legal queries
- High-risk content generation
- Production deployments

---

## Monitoring

### Key Metrics to Track

- **Escalation Rate:** % of requests escalated
- **Rejection Rate:** % of requests rejected
- **Average Confidence Score:** Trend over time
- **Safety Issues:** Breakdown by issue type
- **Latency Impact:** Verification overhead

### Recommended Alerts

- Rejection rate > 10% (investigate model quality)
- Escalation rate > 50% (initial model too weak)
- Safety score < 0.5 average (concerning trend)

---

## Best Practices

### 1. Use Appropriate Initial Model

Start with the right model for the task:
- Simple queries → `gemma:2b`
- Conversations → `phi3:3.8b`
- Long documents → `qwen2.5:3b`
- Complex reasoning → `mistral:7b`

This reduces unnecessary escalations.

### 2. Monitor Escalation Patterns

If `gemma:2b` constantly escalates to `mistral:7b`, consider starting with `phi3:3.8b` instead.

### 3. Tune Thresholds

Adjust thresholds based on your use case:
- **High-risk applications:** Increase safety threshold to 0.8+
- **Speed-critical applications:** Increase confidence threshold to 0.7+
- **Quality-critical applications:** Decrease confidence threshold to 0.6

### 4. Handle Rejections Gracefully

When outputs are rejected:
- Show user a generic error message
- Log details for debugging
- Optionally retry with explicit high-quality model

---

## Future Enhancements

- [ ] Parallel verification (run both verifiers simultaneously)
- [ ] Custom thresholds per intent type
- [ ] Model-specific confidence baselines
- [ ] Learning from user feedback on escalations
- [ ] Integration with external safety APIs (Perspective API, etc.)

---

## Related Documentation

- [Local LLM Routing](./LOCAL_LLM_ROUTING.md) - Main routing guide
- [Advanced Testing](./ADVANCED_TESTING_GUIDE.md) - Test suite documentation
- [Chat API](./chat_router.py) - API implementation

---

**Last Updated:** 2025-12-01
**Status:** Production-ready
**Models Required:** llama3.2:3b-instruct, phi3:3.8b (+ primary models)
