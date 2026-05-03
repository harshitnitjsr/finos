"""
AI Model Router — Routes requests to appropriate OpenAI models
based on task type and complexity.
Also captures token usage for agent logging.
"""
from enum import Enum
from typing import Any, Optional
from openai import AsyncOpenAI
from app.core.config import settings
from loguru import logger


class ModelTask(str, Enum):
    REASONING = "reasoning"          # GPT-4o — complex analysis, insights, explanations
    EXTRACTION = "extraction"        # GPT-4o-mini — invoice parsing, data extraction
    CLASSIFICATION = "classification" # GPT-4o-mini — expense categorization, risk scoring
    EMBEDDING = "embedding"          # text-embedding-3-small — vector similarity
    FORECAST = "forecast"            # GPT-4o — financial forecasting, trend analysis
    COMPLIANCE = "compliance"        # GPT-4o — policy evaluation, risk assessment


MODEL_MAP = {
    ModelTask.REASONING: settings.MODEL_ROUTER_REASONING,
    ModelTask.EXTRACTION: settings.MODEL_ROUTER_EXTRACTION,
    ModelTask.CLASSIFICATION: settings.MODEL_ROUTER_CLASSIFICATION,
    ModelTask.EMBEDDING: settings.MODEL_ROUTER_EMBEDDING,
    ModelTask.FORECAST: settings.MODEL_ROUTER_FORECAST,
    ModelTask.COMPLIANCE: settings.MODEL_ROUTER_COMPLIANCE,
}


class CompletionResult:
    """Holds completion response + token usage for agent logging."""

    def __init__(self, content: str, prompt_tokens: int, completion_tokens: int, model: str):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.model = model

    def __str__(self):
        return self.content


class ModelRouter:
    """Routes AI tasks to the most appropriate and cost-efficient model."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    def get_model(self, task: ModelTask) -> str:
        return MODEL_MAP.get(task, settings.MODEL_ROUTER_REASONING)

    async def complete_with_usage(
        self,
        task: ModelTask,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_format: Optional[dict] = None,
        messages: Optional[list] = None,
    ) -> CompletionResult:
        """
        Generate a completion and return full result including token usage.
        Use this when you need to log token counts.
        """
        model = self.get_model(task)
        logger.debug(f"ModelRouter: task={task.value}, model={model}")

        if messages:
            # Multi-turn conversation
            msg_list = messages
        else:
            msg_list = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": msg_list,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        usage = response.usage

        return CompletionResult(
            content=content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=model,
        )

    async def complete(
        self,
        task: ModelTask,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_format: Optional[dict] = None,
    ) -> str:
        """Generate a completion using the appropriate model for the task. Returns string only."""
        result = await self.complete_with_usage(
            task=task,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        return result.content

    async def generate(
        self,
        task_type: ModelTask,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        agent_name: str = "AI Agent",
        messages: Optional[list] = None,
    ) -> str:
        """
        Alias for complete() — used by chat and other components.
        Supports multi-turn messages list.
        """
        result = await self.complete_with_usage(
            task=task_type,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
        )
        return result.content

    async def embed(self, text: str) -> list[float]:
        """Generate embeddings using text-embedding-3-small. Returns [] on failure."""
        try:
            model = self.get_model(ModelTask.EMBEDDING)
            response = await self.client.embeddings.create(
                model=model,
                input=text[:8000],
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"ModelRouter.embed failed: {e}")
            return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts. Returns [] on failure."""
        try:
            model = self.get_model(ModelTask.EMBEDDING)
            response = await self.client.embeddings.create(
                model=model,
                input=[t[:8000] for t in texts],
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"ModelRouter.embed_batch failed: {e}")
            return [[] for _ in texts]


# Singleton
model_router = ModelRouter()
