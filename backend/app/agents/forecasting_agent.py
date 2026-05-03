"""
Forecasting Agent — Financial Prediction & Runway Analysis
Handles: runway forecasting, budget forecasting, seasonal analysis.
"""
import json
import re
from datetime import datetime, timedelta
from loguru import logger
from app.core.model_router import model_router, ModelTask
from app.core.agent_logger import AgentTimer

RUNWAY_PROMPT = """Analyze company financial data and forecast runway. Return ONLY valid JSON with no markdown:
{
  "current_burn_rate": float, "runway_months": float, "runway_days": int,
  "scenarios": {"optimistic": {"burn_rate": float, "runway_months": float}, "base": {"burn_rate": float, "runway_months": float}, "pessimistic": {"burn_rate": float, "runway_months": float}},
  "top_burn_categories": [{"category": str, "monthly_avg": float}],
  "reduction_opportunities": [{"category": str, "potential_reduction": float, "action": str}],
  "confidence": float
}"""

BUDGET_PROMPT = """Forecast budget by category. Return ONLY valid JSON with no markdown:
{
  "monthly_forecasts": [{"month": str, "categories": [{"category": str, "projected": float}]}],
  "total_projected_3m": float, "growth_categories": [str], "budget_alerts": [str], "recommendations": [str]
}"""


def _extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from LLM output that may contain:
    - markdown code fences (```json ... ```)
    - leading/trailing prose
    - nested objects (handles brace counting, not just first/last {})
    """
    # Strip markdown fences first
    text = re.sub(r'```(?:json)?\s*', '', text).strip()
    text = re.sub(r'```\s*$', '', text).strip()

    # Find the outermost { } by brace counting
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in response")

    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])

    raise ValueError("Unmatched braces in JSON response")



class ForecastingAgent:
    AGENT_ID = "forecasting-agent"
    AGENT_NAME = "Forecasting Agent"

    async def forecast_runway(self, monthly_expenses: list[dict], cash_on_hand: float = 0) -> dict:
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "forecast_runway") as timer:
            timer.input_summary = f"{len(monthly_expenses)} months, ${cash_on_hand:,.0f} cash"
            if not monthly_expenses:
                return self._empty_runway()
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.FORECAST,
                    system_prompt=RUNWAY_PROMPT,
                    user_prompt=f"Monthly data: {json.dumps({'expenses': monthly_expenses, 'cash': cash_on_hand}, default=str)[:2500]}",
                    temperature=0.15, max_tokens=700,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens
                m = _extract_json(result.content)
                timer.output_summary = f"Runway: {m.get('runway_months', 0):.1f}mo"
                timer.confidence = float(m.get("confidence", 0.75))
                return m
            except Exception as e:
                logger.error(f"ForecastingAgent runway failed: {e}")
        avg = sum(m.get("total", 0) for m in monthly_expenses) / max(len(monthly_expenses), 1)
        runway = (cash_on_hand / avg) if avg > 0 else 0
        return {"current_burn_rate": avg, "runway_months": runway, "runway_days": int(runway * 30),
                "scenarios": {"optimistic": {"burn_rate": avg * 0.8, "runway_months": runway * 1.25},
                              "base": {"burn_rate": avg, "runway_months": runway},
                              "pessimistic": {"burn_rate": avg * 1.2, "runway_months": runway * 0.83}},
                "top_burn_categories": [], "reduction_opportunities": [], "confidence": 0.6}

    async def forecast_budget(self, historical_by_category: list[dict], months: int = 3) -> dict:
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "forecast_budget") as timer:
            timer.input_summary = f"{len(historical_by_category)} categories"
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.FORECAST,
                    system_prompt=BUDGET_PROMPT,
                    user_prompt=f"Category data: {json.dumps(historical_by_category, default=str)[:2500]}",
                    temperature=0.2, max_tokens=800,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens
                m = _extract_json(result.content)
                timer.output_summary = f"Budget forecast: ${m.get('total_projected_3m', 0):,.0f}"
                return m
            except Exception as e:
                logger.error(f"ForecastingAgent budget failed: {e}")
        return {"monthly_forecasts": [], "total_projected_3m": 0, "growth_categories": [], "budget_alerts": [], "recommendations": []}

    def _empty_runway(self) -> dict:
        return {"current_burn_rate": 0, "runway_months": 0, "runway_days": 0,
                "scenarios": {"optimistic": {"burn_rate": 0, "runway_months": 0}, "base": {"burn_rate": 0, "runway_months": 0}, "pessimistic": {"burn_rate": 0, "runway_months": 0}},
                "top_burn_categories": [], "reduction_opportunities": [], "confidence": 0}


forecasting_agent = ForecastingAgent()
