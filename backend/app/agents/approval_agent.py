"""
Approval Agent — Intelligent Approval Routing & Workflow
Handles: approval routing, threshold evaluation, escalation, stakeholder coordination.
"""
import json
import re
from datetime import datetime
from typing import Optional
from loguru import logger
from app.core.model_router import model_router, ModelTask
from app.core.agent_logger import AgentTimer

ROUTING_PROMPT = """You are an approval routing AI. Determine the optimal approval chain for this financial transaction.

Consider: amount, vendor risk, policy violations, urgency.

Return JSON: {
  "approver_level": "manager|director|vp|cfo|ceo",
  "approvers": [str],
  "urgency": "low|medium|high|critical",
  "sla_hours": int,
  "auto_approve": bool,
  "reason": str,
  "escalation_trigger": str
}"""

APPROVAL_SUMMARY_PROMPT = """You are a financial approval AI assistant. Provide a clear, concise summary of this approval request for the approver.

Include: what it is, why it needs approval, risk factors, and your recommendation.
Keep to 2-3 sentences. Be direct and specific."""


class ApprovalAgent:
    AGENT_ID = "approval-agent"
    AGENT_NAME = "Approval Agent"

    async def route_approval(self, transaction: dict, violations: Optional[list] = None) -> dict:
        """Determine optimal approval routing for a transaction."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "route_approval") as timer:
            amount = float(transaction.get("amount", 0))
            currency = transaction.get("currency", "USD")
            timer.input_summary = f"{currency} {amount:,.0f} transaction routing"

            context = {
                "transaction": transaction,
                "violations": violations or [],
                "amount": amount,
                "currency": currency,
            }

            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.COMPLIANCE,
                    system_prompt=ROUTING_PROMPT,
                    user_prompt=f"Route approval for: {json.dumps(context, default=str)[:2000]}",
                    temperature=0.1, max_tokens=400,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                m = re.search(r'\{.*\}', result.content, re.DOTALL)
                if m:
                    data = json.loads(m.group())
                    timer.output_summary = f"Route to {data.get('approver_level')}, SLA: {data.get('sla_hours')}h"
                    return data
            except Exception as e:
                logger.error(f"ApprovalAgent routing failed: {e}")

        # Rule-based fallback
        has_violations = bool(violations)
        auto_approve = amount < 1000 and not has_violations
        level = "cfo" if amount > 50000 else "director" if amount > 10000 else "manager"
        return {
            "approver_level": level,
            "approvers": [f"{level}@company.com"],
            "urgency": "high" if has_violations else "medium",
            "sla_hours": 4 if has_violations else 24,
            "auto_approve": auto_approve,
            "reason": "Standard threshold routing",
            "escalation_trigger": f"No response after SLA",
        }

    async def generate_approval_summary(self, transaction: dict, violations: list) -> str:
        """Generate a clear approval summary for the approver."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "generate_summary") as timer:
            timer.input_summary = f"Summarizing approval for ${transaction.get('amount', 0):,.0f}"
            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.REASONING,
                    system_prompt=APPROVAL_SUMMARY_PROMPT,
                    user_prompt=f"Transaction: {json.dumps(transaction, default=str)}\nViolations: {json.dumps(violations, default=str)}",
                    temperature=0.3, max_tokens=200,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens
                timer.output_summary = result.content[:100]
                return result.content
            except Exception as e:
                logger.error(f"ApprovalAgent summary failed: {e}")

        amount = float(transaction.get("amount", 0))
        return f"Payment of {transaction.get('currency', 'USD')} {amount:,.0f} requires approval. {len(violations)} policy violation(s) detected."

    async def check_auto_approval(self, transaction: dict) -> dict:
        """Determine if a transaction qualifies for automatic approval."""
        amount = float(transaction.get("amount", 0))
        vendor_verified = transaction.get("vendor_verified", False)
        vendor_risk = float(transaction.get("vendor_risk_score", 0))

        auto_approve = (
            amount < 1000 and
            vendor_verified and
            vendor_risk < 30
        )

        return {
            "auto_approve": auto_approve,
            "reason": "Below auto-approve threshold with verified, low-risk vendor" if auto_approve else "Manual review required",
            "threshold_amount": 1000,
            "conditions_met": {
                "amount_ok": amount < 1000,
                "vendor_verified": vendor_verified,
                "risk_ok": vendor_risk < 30,
            }
        }


approval_agent = ApprovalAgent()
