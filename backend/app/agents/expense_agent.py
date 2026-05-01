"""
Expense Intelligence Agent
Handles: AI categorization, anomaly detection, subscription detection, department tagging.
All invocations logged to agent_logs table. Redis heartbeat updated on each call.
"""
import json
import re
import time
from typing import Optional
from loguru import logger

from app.core.model_router import model_router, ModelTask
from app.core.agent_logger import AgentTimer


CATEGORIZATION_PROMPT = """You are an expert expense categorization AI for businesses.

Categorize the expense into ONE of these categories:
- Software & SaaS
- Cloud Infrastructure
- Marketing & Advertising
- Travel & Transportation
- Meals & Entertainment
- Office Supplies
- Professional Services
- HR & Recruitment
- Legal & Compliance
- Finance & Banking
- Hardware & Equipment
- Utilities
- Insurance
- Other

Also identify:
- subcategory: More specific classification
- department: Engineering / Marketing / Finance / HR / Operations / Sales / Legal / Executive
- is_recurring: true if this looks like a subscription/recurring charge
- vendor_type: "saas" | "service" | "utility" | "one-time"

Return JSON: {
  "category": string,
  "subcategory": string,
  "department": string,
  "is_recurring": bool,
  "vendor_type": string,
  "confidence": float (0-1)
}
"""

ANOMALY_DETECTION_PROMPT = """You are a financial anomaly detection AI. Analyze whether this expense is anomalous.

Consider:
- Amount unusually high or low for the category
- Unusual vendor for department
- Timing anomalies (weekends, late night, holidays)
- Duplicate or near-duplicate charges
- Category mismatch with vendor name
- Spend spike compared to history

Return JSON: {
  "is_anomaly": bool,
  "anomaly_score": float (0-1, higher = more anomalous),
  "anomaly_type": "amount_spike" | "unusual_vendor" | "timing" | "duplicate" | "category_mismatch" | "none",
  "reason": string (explanation),
  "severity": "low" | "medium" | "high" | "critical",
  "recommended_action": string
}
"""

SUBSCRIPTION_ANALYSIS_PROMPT = """You are a SaaS spend optimization AI. Analyze recurring expenses.
Return JSON: {
  "duplicates": [{"tools": [str], "category": str, "estimated_savings": float}],
  "optimizations": [{"vendor": str, "recommendation": str, "potential_savings": float}],
  "total_recurring_spend": float,
  "summary": str
}
"""


class ExpenseAgent:
    """AI agent for intelligent expense management."""

    AGENT_ID = "expense-agent"
    AGENT_NAME = "Expense Intelligence"

    async def categorize(self, description: str, vendor_name: str, amount: float, currency: str) -> dict:
        """Categorize expense using GPT-4o-mini — logs to agent_logs."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "categorize_expense") as timer:
            timer.input_summary = f"{vendor_name}: {currency} {amount:.2f}"
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.CLASSIFICATION,
                    system_prompt=CATEGORIZATION_PROMPT,
                    user_prompt=f"Categorize this expense:\nDescription: {description}\nVendor: {vendor_name}\nAmount: {amount} {currency}",
                    temperature=0.1,
                    max_tokens=300,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    r = json.loads(json_match.group())
                    timer.output_summary = f"Category: {r.get('category')}, Confidence: {r.get('confidence', 0):.2f}"
                    timer.confidence = float(r.get("confidence", 0))
                    return r
            except Exception as e:
                logger.error(f"ExpenseAgent: categorization failed: {e}")

        return {
            "category": "Other",
            "subcategory": "Uncategorized",
            "department": "Operations",
            "is_recurring": False,
            "vendor_type": "one-time",
            "confidence": 0.3,
        }

    async def detect_anomaly(self, expense_data: dict, historical_context: Optional[dict] = None) -> dict:
        """Detect anomalies using GPT-4o for reasoning — logs to agent_logs."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "detect_anomaly") as timer:
            timer.input_summary = f"Anomaly check: {expense_data.get('vendor_name', '?')} ${expense_data.get('amount', 0)}"
            context = {"expense": expense_data, "history": historical_context or {}}
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.REASONING,
                    system_prompt=ANOMALY_DETECTION_PROMPT,
                    user_prompt=f"Analyze this expense for anomalies:\n{json.dumps(context, indent=2, default=str)[:2000]}",
                    temperature=0.2,
                    max_tokens=400,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    r = json.loads(json_match.group())
                    timer.output_summary = f"Anomaly: {r.get('is_anomaly')}, Score: {r.get('anomaly_score', 0):.2f}"
                    return r
            except Exception as e:
                logger.error(f"ExpenseAgent: anomaly detection failed: {e}")

        return {
            "is_anomaly": False,
            "anomaly_score": 0.1,
            "anomaly_type": "none",
            "reason": "No anomaly detected",
            "severity": "low",
            "recommended_action": "No action required",
        }

    async def analyze_subscriptions(self, recurring_expenses: list[dict]) -> dict:
        """Identify duplicate SaaS tools and optimization opportunities."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "analyze_subscriptions") as timer:
            timer.input_summary = f"{len(recurring_expenses)} recurring expenses"
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.REASONING,
                    system_prompt=SUBSCRIPTION_ANALYSIS_PROMPT,
                    user_prompt=f"Analyze these recurring expenses:\n{json.dumps(recurring_expenses[:100], default=str)[:3000]}",
                    temperature=0.3,
                    max_tokens=800,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    r = json.loads(json_match.group())
                    timer.output_summary = f"Duplicates: {len(r.get('duplicates', []))}, Optimizations: {len(r.get('optimizations', []))}"
                    return r
            except Exception as e:
                logger.error(f"ExpenseAgent: subscription analysis failed: {e}")

        return {
            "duplicates": [],
            "optimizations": [],
            "total_recurring_spend": sum(e.get("amount", 0) for e in recurring_expenses),
            "summary": "Analysis unavailable",
        }

    async def batch_categorize(self, expenses: list[dict]) -> list[dict]:
        """Batch categorize multiple expenses."""
        results = []
        for expense in expenses:
            result = await self.categorize(
                description=expense.get("description", ""),
                vendor_name=expense.get("vendor_name", ""),
                amount=float(expense.get("amount", 0)),
                currency=expense.get("currency", "USD"),
            )
            results.append({**expense, **result})
        return results


expense_agent = ExpenseAgent()
