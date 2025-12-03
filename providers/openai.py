import time
from typing import Dict, Any


def test_connection(api_key: str) -> Dict[str, Any]:
    """Test OpenAI API connection"""
    start_time = time.time()
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        # Simple test: list models
        models = client.models.list()
        latency = time.time() - start_time
        return {
            "success": True,
            "latency_ms": round(latency * 1000, 2),
            "status_code": 200,
            "message": f"Connected successfully. Found {len(models.data)} models.",
        }
    except ImportError:
        return {"success": False, "error": "OpenAI package not installed"}
    except Exception as e:
        latency = time.time() - start_time
        return {
            "success": False,
            "latency_ms": round(latency * 1000, 2),
            "error": str(e),
        }
