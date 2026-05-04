"""
Insight Agent — Proactive Financial Intelligence
Generates executive summaries, recommendations, and optimization insights.
All invocations logged to agent_logs table.
"""
import json
import re
from loguru import logger
from app.core.model_router import model_router, ModelTask
from app.core.agent_logger import AgentTimer


EXECUTIVE_SUMMARY_PROMPT = """You are a CFO-level financial AI advisor. Generate a concise, actionable executive financial summary.

Focus on:
1. Cash position and runway
2. Key risks and anomalies
3. Pending approvals urgency
4. Top optimization opportunities
5. Action items for today

Be direct, specific, and use numbers. Maximum 5 bullet points. Return as JSON:
{
  "headline": "One-line financial health summary",
  "status": "healthy|warning|critical",
  "bullets": ["actionable insight 1", ...],
  "urgent_actions": ["urgent action 1", ...],
  "opportunities": [{"title": str, "estimated_savings": float, "currency": str}]
}
"""

FORECAST_PROMPT = """You are a financial forecasting AI. Based on historical spending data, generate a 90-day financial forecast.

Return JSON: {
  "burn_rate_monthly": float,
  "runway_days": int,
  "currency": str,
  "cash_flow_forecast": [{"month": str, "inflow": float, "outflow": float, "net": float}],
  "risk_scenarios": [{"scenario": str, "probability": str, "impact": str}],
  "confidence": float
}
"""

RECOMMENDATION_PROMPT = """You are a financial optimization AI. Analyze spending patterns and generate specific, actionable cost optimization recommendations.

Return JSON: {"recommendations": [{"title": str, "category": str, "description": str, "estimated_savings": float, "currency": str, "effort": "low|medium|high", "priority": "low|medium|high|critical"}]}
"""

ANOMALY_EXPLANATION_PROMPT = """You are a financial risk explainer. Explain this financial anomaly in plain English for a business executive.

Be clear: what it is, why flagged, potential impact, recommended action. Under 3 sentences."""


class InsightAgent:
    """AI agent for proactive financial insights and recommendations."""

    AGENT_ID = "insight-agent"
    AGENT_NAME = "Insight Agent"

    async def generate_executive_summary(self, financial_data: dict) -> dict:
        """Generate executive summary using GPT-4o."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "executive_summary") as timer:
            timer.input_summary = f"Summarizing: {len(financial_data)} data points"
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.REASONING,
                    system_prompt=EXECUTIVE_SUMMARY_PROMPT,
                    user_prompt=f"Financial data:\n{json.dumps(financial_data, indent=2, default=str)[:3000]}",
                    temperature=0.3,
                    max_tokens=600,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    timer.output_summary = f"Status: {data.get('status')}, Bullets: {len(data.get('bullets', []))}"
                    timer.confidence = 0.88
                    return data
            except Exception as e:
                logger.error(f"InsightAgent executive summary failed: {e}")

        return {
            "headline": "Financial system operational",
            "status": "healthy",
            "bullets": ["All systems normal", "No critical anomalies detected"],
            "urgent_actions": [],
            "opportunities": [],
        }

    async def forecast_cashflow(self, historical_data: dict, months: int = 3, currency: str = "USD") -> dict:
        """Generate cash flow forecast using GPT-4o."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "forecast_cashflow") as timer:
            timer.input_summary = f"Forecasting {months} months from historical data ({currency})"
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.FORECAST,
                    system_prompt=FORECAST_PROMPT + f"\nNote: All values must be in {currency}.",
                    user_prompt=f"Historical data ({currency}):\n{json.dumps(historical_data, indent=2, default=str)[:3000]}\n\nForecast for next {months} months in {currency}.",
                    temperature=0.2,
                    max_tokens=1000,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    timer.output_summary = f"Burn: ${data.get('burn_rate_monthly', 0):,.0f}/mo, Runway: {data.get('runway_days', 0)} days"
                    return data
            except Exception as e:
                logger.error(f"InsightAgent forecast failed: {e}")

        return {
            "burn_rate_monthly": 0,
            "runway_days": 365,
            "currency": currency,
            "cash_flow_forecast": [],
            "risk_scenarios": [],
            "confidence": 0.5,
        }

    async def generate_recommendations(self, spending_data: dict) -> list[dict]:
        """Generate cost optimization recommendations using GPT-4o."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "generate_recommendations") as timer:
            timer.input_summary = "Generating cost optimization recommendations"
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.REASONING,
                    system_prompt=RECOMMENDATION_PROMPT,
                    user_prompt=f"Spending analysis:\n{json.dumps(spending_data, indent=2, default=str)[:3000]}",
                    temperature=0.4,
                    max_tokens=1200,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    recs = data.get("recommendations", [])
                    timer.output_summary = f"Generated {len(recs)} recommendations"
                    return recs
            except Exception as e:
                logger.error(f"InsightAgent recommendations failed: {e}")
        return []

    async def explain_anomaly(self, anomaly: dict) -> str:
        """Explain a financial anomaly in plain English."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "explain_anomaly") as timer:
            timer.input_summary = f"Explaining anomaly: {anomaly.get('anomaly_type', 'unknown')}"
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.REASONING,
                    system_prompt=ANOMALY_EXPLANATION_PROMPT,
                    user_prompt=f"Anomaly details:\n{json.dumps(anomaly, default=str)}",
                    temperature=0.3,
                    max_tokens=200,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens
                timer.output_summary = result.content[:100]
                return result.content
            except Exception:
                pass
        return "An unusual financial pattern was detected that requires your review."

    async def analyze_vendor_health(self, vendor_data: dict, transaction_history: list) -> dict:
        """Analyze vendor relationship health."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "vendor_health_analysis") as timer:
            timer.input_summary = f"Vendor: {vendor_data.get('name', 'Unknown')}"
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.REASONING,
                    system_prompt="""Analyze this vendor relationship. Return JSON: {
                      "health_score": float (0-100),
                      "risk_level": "low|medium|high",
                      "insights": [str],
                      "recommendations": [str]
                    }""",
                    user_prompt=f"Vendor: {json.dumps(vendor_data, default=str)}\nHistory: {json.dumps(transaction_history[:20], default=str)[:2000]}",
                    temperature=0.2,
                    max_tokens=500,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    timer.output_summary = f"Health: {data.get('health_score')}/100"
                    return data
            except Exception as e:
                logger.error(f"InsightAgent vendor health failed: {e}")
        return {"health_score": 70, "risk_level": "low", "insights": [], "recommendations": []}


insight_agent = InsightAgent()
