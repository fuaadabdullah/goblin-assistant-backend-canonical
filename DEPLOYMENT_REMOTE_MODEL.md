# Deploying llama3.2:3b to Remote Ollama Server

## Issue

The model needs to be deployed on the **remote Ollama server** at `45.61.60.3:8002`, not locally (no space on local disk).

## Deployment Steps

### Option 1: SSH into Remote Server

```bash
# SSH into your Kamatera VPS
ssh user@45.61.60.3

# Pull the llama3.2:3b model
ollama pull llama3.2:3b

# Verify it's available
ollama list

# Test the model
ollama run llama3.2:3b "Hello, how are you?"
```

### Option 2: Use API to Load Model

The model will auto-load on first use, but you can pre-warm it:

```bash
curl http://45.61.60.3:8002/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "Test",
  "stream": false
}'
```

This will download the model if not present.

## Verify Deployment

Test the verification system locally (connects to remote server):

```bash
cd apps/goblin-assistant/backend

# Run verification tests (will use remote server)
python test_verification_scoring.py
```

## Model Configuration

The code has been updated to use `llama3.2:3b` (without `-instruct` suffix):

- **`services/local_llm_routing.py`** - Model config updated
- **`services/output_verification.py`** - Default verifier model updated

## Current Models on Server

As of last check:
- ✅ `phi3:3.8b` - 2.2 GB
- ✅ `gemma:2b` - 1.7 GB
- ✅ `qwen2.5:3b` - 1.9 GB
- ✅ `deepseek-coder:1.3b` - 776 MB
- ❌ `mistral:7b` - **NOT YET DEPLOYED** (~4.1 GB)
- ❌ `llama3.2:3b` - **NEEDS DEPLOYMENT** (~2.0 GB)

## Next Steps

1. **Deploy llama3.2:3b on remote server** (SSH method recommended)
2. **Optionally deploy mistral:7b** for highest quality tier
3. **Run tests** to verify everything works

## If Remote Deployment Not Possible

If you can't access the remote server, you can:

1. Use an alternative smaller model already on the server:
   ```python
   # In output_verification.py, change default to:
   verifier_model: str = "qwen2.5:3b"  # Already deployed
   ```

2. Or disable verification for now:
   ```json
   {
     "messages": [...],
     "enable_verification": false
   }
   ```

## Testing Without llama3.2:3b

The confidence scoring will still work with `phi3:3.8b` (already deployed). Only safety verification requires the new model.

---

**Status:** Awaiting deployment on remote server
**Alternative:** Use `qwen2.5:3b` as verifier (already available)
