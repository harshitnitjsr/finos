"""
Treasury Agent — Cash Flow Intelligence
Handles: burn rate analysis, runway forecasting, payment prioritization, liquidity insights.
Model: GPT-4o for all treasury reasoning.
"""
import json
import re
import time
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

from app.core.model_router import model_router, ModelTask
from app.core.agent_logger import AgentTimer


BURN_RATE_PROMPT = """You are a treasury management AI. Analyze the company's cash burn rate and financial health.

Given monthly expense data, calculate:
- Average monthly burn rate
- Runway estimate (months of cash remaining)
- Burn trend (accelerating/decelerating)
- Top burn drivers by category

Return JSON: {
  "burn_rate_monthly": float,
  "burn_rate_trend": "increasing|stable|decreasing",
  "runway_months": float,
  "runway_days": int,
  "burn_drivers": [{"category": str, "amount": float, "percentage": float}],
  "cash_health": "critical|warning|healthy|excellent",
  "insights": [str],
  "recommended_actions": [str]
}"""

PAYMENT_PRIORITIZATION_PROMPT = """You are a payment prioritization AI. Given pending invoices and cash position, determine optimal payment order.

Consider:
- Due dates (overdue = highest priority)
- Vendor risk (high-risk vendors may need early payment to maintain relationship)
- Cash flow impact
- Discount opportunities (early payment discounts)

Return JSON: {
  "prioritized_payments": [{"invoice_id": str, "priority": int, "reason": str, "due_date": str, "amount": float}],
  "total_due_this_week": float,
  "total_due_this_month": float,
  "cash_flow_impact": str,
  "recommendation": str
}"""

CASHFLOW_FORECAST_PROMPT = """You are a cash flow forecasting AI. Generate a 90-day forward-looking cash flow model.

Based on historical monthly spend data, predict:
- Month-by-month inflows and outflows
- Net cash position changes
- Risk scenarios (best/base/worst case)

Return JSON: {
  "forecast": [{"month": str, "projected_outflow": float, "confidence": float}],
  "burn_acceleration": float,
  "risk_scenario": {"best": float, "base": float, "worst": float},
  "key_risks": [str],
  "opportunities": [str]
}"""


class TreasuryAgent:
    """AI agent for cash flow intelligence and treasury optimization."""

    AGENT_ID = "treasury-agent"
    AGENT_NAME = "Treasury Agent"

    async def analyze_burn_rate(self, monthly_expenses: list[dict], cash_position: float = 0) -> dict:
        """Analyze burn rate from real expense data."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "analyze_burn_rate") as timer:
            timer.input_summary = f"{len(monthly_expenses)} months of expense data"

            context = {
                "monthly_expenses": monthly_expenses,
                "cash_position": cash_position,
                "analysis_date": datetime.utcnow().isoformat(),
            }

            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.FORECAST,
                    system_prompt=BURN_RATE_PROMPT,
                    user_prompt=f"Expense data: {json.dumps(context, default=str)[:3000]}",
                    temperature=0.2,
                    max_tokens=800,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    timer.output_summary = f"Burn rate: ${data.get('burn_rate_monthly', 0):,.0f}/mo, Runway: {data.get('runway_months', 0):.1f} months"
                    timer.confidence = 0.85
                    return data
            except Exception as e:
                logger.error(f"TreasuryAgent burn rate analysis failed: {e}")
                timer.output_summary = "Analysis failed — using fallback"

        # Fallback from real data
        if monthly_expenses:
            avg_burn = sum(m.get("total", 0) for m in monthly_expenses) / len(monthly_expenses)
            runway = (cash_position / avg_burn) if avg_burn > 0 else 0
        else:
            avg_burn = 0
            runway = 0

        return {
            "burn_rate_monthly": avg_burn,
            "burn_rate_trend": "stable",
            "runway_months": runway,
            "runway_days": int(runway * 30),
            "burn_drivers": [],
            "cash_health": "healthy" if runway > 12 else "warning" if runway > 6 else "critical",
            "insights": ["Historical data analyzed"],
            "recommended_actions": [],
        }

    async def prioritize_payments(self, pending_invoices: list[dict], cash_available: float) -> dict:
        """Determine optimal payment order for pending invoices."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "prioritize_payments") as timer:
            timer.input_summary = f"{len(pending_invoices)} pending invoices, ${cash_available:,.0f} available"

            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.FORECAST,
                    system_prompt=PAYMENT_PRIORITIZATION_PROMPT,
                    user_prompt=f"Cash: ${cash_available:,.0f}\nPending invoices: {json.dumps(pending_invoices[:20], default=str)[:2500]}",
                    temperature=0.1,
                    max_tokens=800,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    timer.output_summary = f"Prioritized {len(data.get('prioritized_payments', []))} payments"
                    return data
            except Exception as e:
                logger.error(f"TreasuryAgent payment prioritization failed: {e}")

        # Rule-based fallback: sort by due date
        sorted_invoices = sorted(pending_invoices, key=lambda x: x.get("due_date", "9999"))
        return {
            "prioritized_payments": [
                {"invoice_id": inv.get("id"), "priority": i + 1, "reason": "Due date order", "amount": inv.get("total_amount", 0)}
                for i, inv in enumerate(sorted_invoices[:10])
            ],
            "total_due_this_week": sum(float(i.get("total_amount", 0)) for i in pending_invoices[:3]),
            "total_due_this_month": sum(float(i.get("total_amount", 0)) for i in pending_invoices),
            "cash_flow_impact": "Standard",
            "recommendation": "Pay overdue invoices first",
        }

    async def forecast_cashflow(self, monthly_data: list[dict], months_ahead: int = 3) -> dict:
        """Generate forward-looking cash flow forecast."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "forecast_cashflow") as timer:
            timer.input_summary = f"{len(monthly_data)} months historical data, {months_ahead}m forecast"

            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.FORECAST,
                    system_prompt=CASHFLOW_FORECAST_PROMPT,
                    user_prompt=f"Historical monthly data: {json.dumps(monthly_data, default=str)[:3000]}\nForecast horizon: {months_ahead} months",
                    temperature=0.2,
                    max_tokens=800,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    timer.output_summary = f"Generated {months_ahead}-month forecast"
                    timer.confidence = 0.80
                    return data
            except Exception as e:
                logger.error(f"TreasuryAgent forecast failed: {e}")

        return {
            "forecast": [],
            "burn_acceleration": 1.0,
            "risk_scenario": {"best": 0, "base": 0, "worst": 0},
            "key_risks": ["Insufficient data for forecast"],
            "opportunities": [],
        }


treasury_agent = TreasuryAgent()
