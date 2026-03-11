import httpx
import json
import base64
from typing import Any
from src.core.config import settings
from src.core.logging import get_logger
from src.apps.shoot_right_config import (
    MODEL_1_SYSTEM_PROMPT,
    MODEL_2_SYSTEM_PROMPT,
    IMPROVEMENT_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


class LLMClientAsync:
    def __init__(self):
        self.base_url = settings.OPENROUTER_BASE_URL
        self.api_key = settings.OPENROUTER_API_KEY

    async def analyze_image(self, image_bytes: bytes, model1: str, model2: str) -> dict[str, Any]:
        encoded = base64.b64encode(image_bytes).decode("utf-8")

        # Step 1: model1 → narrative text
        payload1 = {
            "model": model1,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": MODEL_1_SYSTEM_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload1,
            )
            response.raise_for_status()
            narrative = response.json()["choices"][0]["message"]["content"]

        # Step 2: model2 → structured JSON
        payload2 = {
            "model": model2,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": MODEL_2_SYSTEM_PROMPT.format(narrative=narrative)},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload2,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)

    async def generate_improvement_prescription(
        self, analysis_data: dict[str, Any], model: str
    ) -> str:
        summary = json.dumps(
            {
                "overall_score": analysis_data.get("overall_score"),
                "summary_text": analysis_data.get("summary_text"),
                "composition": analysis_data.get("composition"),
                "technical": analysis_data.get("technical"),
                "color_aesthetic": analysis_data.get("color_aesthetic"),
                "clicking_tips": analysis_data.get("clicking_tips"),
            }
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": IMPROVEMENT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Photography analysis:\n{summary}\n\nProvide improvement prescription:"},
            ],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


class LLMClientSync:
    """Synchronous client for use in Celery workers."""

    def __init__(self):
        self.base_url = settings.OPENROUTER_BASE_URL
        self.api_key = settings.OPENROUTER_API_KEY

    def analyze_image(self, image_bytes: bytes, model1: str, model2: str) -> dict[str, Any]:
        encoded = base64.b64encode(image_bytes).decode("utf-8")

        # Step 1: model1 → narrative text
        payload1 = {
            "model": model1,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": MODEL_1_SYSTEM_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                    ],
                }
            ],
        }
        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload1,
            )
            response.raise_for_status()
            narrative = response.json()["choices"][0]["message"]["content"]

        # Step 2: model2 → structured JSON
        payload2 = {
            "model": model2,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": MODEL_2_SYSTEM_PROMPT.format(narrative=narrative)},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload2,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)

    def generate_improvement_prescription(self, analysis_data: dict[str, Any], model: str) -> str:
        summary = json.dumps(
            {
                "overall_score": analysis_data.get("overall_score"),
                "summary_text": analysis_data.get("summary_text"),
                "composition": analysis_data.get("composition"),
                "technical": analysis_data.get("technical"),
                "color_aesthetic": analysis_data.get("color_aesthetic"),
                "clicking_tips": analysis_data.get("clicking_tips"),
            }
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": IMPROVEMENT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Photography analysis:\n{summary}\n\nProvide improvement prescription:"},
            ],
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
