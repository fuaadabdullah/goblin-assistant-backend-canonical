import time
from typing import Dict, Any


def test_connection(api_key: str) -> Dict[str, Any]:
    """Test Anthropic API connection"""
    start_time = time.time()
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        # Simple test: create a minimal message
        _ = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1,
            messages=[{"role": "user", "content": "Test"}],
        )
        latency = time.time() - start_time
        return {
            "success": True,
            "latency_ms": round(latency * 1000, 2),
            "status_code": 200,
            "message": "Connected successfully.",
        }
    except ImportError:
        return {"success": False, "error": "Anthropic package not installed"}
    except Exception as e:
        latency = time.time() - start_time
        return {
            "success": False,
            "latency_ms": round(latency * 1000, 2),
            "error": str(e),
        }
