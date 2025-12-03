from typing import Dict, Any, Optional
import os
import httpx
from dataclasses import dataclass

RAPTOR_URL = os.getenv("RAPTOR_URL")
RAPTOR_KEY = os.getenv("RAPTOR_API_KEY")
FALLBACK_URL = os.getenv("FALLBACK_MODEL_URL")
FALLBACK_KEY = os.getenv("FALLBACK_MODEL_KEY")

RAPTOR_TASKS = {"summarize_trace", "quick_fix", "unit_test_hint", "infer_function_name"}


@dataclass
class ModelRoute:
    url: str
    api_key: Optional[str]
    model_name: str


class ModelRouter:
    def choose_model(self, task: str, context: Dict[str, Any]) -> ModelRoute:
        if task in RAPTOR_TASKS and RAPTOR_URL:
            return ModelRoute(url=RAPTOR_URL, api_key=RAPTOR_KEY, model_name="raptor")
        if FALLBACK_URL:
            return ModelRoute(
                url=FALLBACK_URL, api_key=FALLBACK_KEY, model_name="fallback"
            )
        raise RuntimeError("No model endpoints configured")

    async def call_model(
        self, route: ModelRoute, payload: Dict[str, Any], timeout: int = 30
    ) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if route.api_key:
            headers["Authorization"] = f"Bearer {route.api_key}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(route.url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
