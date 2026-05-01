"""
Compliance Agent — Policy Engine
Enforces financial policies, evaluates risk, routes approvals.
Model: GPT-4o for compliance reasoning.
"""
import json
import re
from typing import Optional
from loguru import logger
from app.core.model_router import model_router, ModelTask


# Built-in policy rules
DEFAULT_POLICIES = [
    {
        "id": "POL-001",
        "name": "High-Value Approval",
        "description": "Payments above $10,000 require CFO approval",
        "rule": "amount > 10000",
        "action": "require_approval",
        "approver_role": "cfo",
        "severity": "high",
    },
    {
        "id": "POL-002",
        "name": "Unknown Vendor Block",
        "description": "Unverified vendors with risk score > 70 require review",
        "rule": "vendor_risk_score > 70 AND NOT vendor_verified",
        "action": "require_review",
        "severity": "high",
    },
    {
        "id": "POL-003",
        "name": "Spend Spike Alert",
        "description": "Spending 3x above category average triggers alert",
        "rule": "amount > category_avg * 3",
        "action": "alert_and_review",
        "severity": "medium",
    },
    {
        "id": "POL-004",
        "name": "Duplicate Payment Block",
        "description": "Duplicate invoices are automatically blocked",
        "rule": "is_duplicate == true",
        "action": "block",
        "severity": "critical",
    },
    {
        "id": "POL-005",
        "name": "International Payment Review",
        "description": "Cross-border payments above $5,000 require review",
        "rule": "is_international AND amount > 5000",
        "action": "require_approval",
        "severity": "medium",
    },
]

POLICY_EVALUATION_PROMPT = """You are a financial compliance AI. Evaluate a transaction against company policies.

Analyze each policy rule against the transaction data. For each violation:
- State which policy is violated
- Explain why
- Recommend action (approve/reject/escalate/review)

Return JSON: {
  "compliant": bool,
  "violations": [{
    "policy_id": str,
    "policy_name": str,
    "reason": str,
    "severity": "low|medium|high|critical",
    "action": "approve|reject|escalate|review"
  }],
  "overall_recommendation": "approve|reject|escalate|review",
  "risk_score": float (0-100),
  "explanation": str
}
"""

APPROVAL_ROUTING_PROMPT = """You are an approval workflow AI. Determine the optimal approval chain for this transaction.

Consider:
- Transaction amount and currency
- Vendor risk level
- Policy violations detected
- Business context

Return JSON: {
  "approver_level": "manager|director|vp|cfo|ceo",
  "approvers": [str],
  "escalation_threshold": float,
  "urgency": "low|medium|high|critical",
  "sla_hours": int,
  "auto_approve": bool,
  "reason": str
}
"""


class ComplianceAgent:
    """AI agent for policy enforcement and compliance evaluation."""

    OPA_URL = "http://localhost:8181/v1/data/finance/compliance"

    async def evaluate_rules_opa(self, transaction: dict) -> list[dict]:
        """Evaluate rule-based policies using Open Policy Agent (OPA)."""
        import httpx
        opa_input = {
            "input": {
                "amount": float(transaction.get("amount") or 0),
                "has_approval": False,
                "vendor_risk_score": float(transaction.get("vendor_risk_score") or 0),
                "category_average": 2000.0,
                "is_duplicate": transaction.get("is_duplicate", False),
                "is_international": transaction.get("is_international", False)
            }
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.OPA_URL, json=opa_input, timeout=5.0)
                if resp.status_code == 200:
                    opa_data = resp.json().get("result", {})
                    if not opa_data.get("allow", False):
                        return opa_data.get("violations", [])
        except Exception as e:
            from loguru import logger
            logger.error(f"OPA Evaluation failed: {e}")
        return []

    async def evaluate(self, transaction: dict, policies: Optional[list] = None) -> dict:
        """Full compliance evaluation using AI + OPA rule engine."""
        # Rule-based check first via OPA
        rule_violations = await self.evaluate_rules_opa(transaction)

        # AI-enhanced evaluation for complex cases
        try:
            ai_policies = [p for p in (policies or DEFAULT_POLICIES) if p["id"] not in ["POL-004"]]
            policies_text = json.dumps(ai_policies, indent=2)
            response = await model_router.complete(
                task=ModelTask.COMPLIANCE,
                system_prompt=POLICY_EVALUATION_PROMPT,
                user_prompt=f"Policies:\n{policies_text[:1500]}\n\nTransaction:\n{json.dumps(transaction, default=str)[:1500]}",
                temperature=0.1,
                max_tokens=600,
            )
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                ai_result = json.loads(json_match.group())
                # Merge rule violations with AI violations
                all_violations = rule_violations + [
                    v for v in ai_result.get("violations", [])
                    if not any(rv["policy_id"] == v.get("policy_id") for rv in rule_violations)
                ]
                ai_result["violations"] = all_violations
                ai_result["compliant"] = len(all_violations) == 0
                return ai_result
        except Exception as e:
            logger.error(f"Compliance AI evaluation failed: {e}")

        compliant = len(rule_violations) == 0
        return {
            "compliant": compliant,
            "violations": rule_violations,
            "overall_recommendation": "approve" if compliant else "review",
            "risk_score": len(rule_violations) * 25.0,
            "explanation": f"{'No violations detected' if compliant else f'{len(rule_violations)} policy violation(s) detected'}",
        }

    async def route_approval(self, transaction: dict, violations: list) -> dict:
        """Determine approval routing using AI."""
        context = {
            "transaction": transaction,
            "violations": violations,
            "amount": transaction.get("amount", 0),
            "currency": transaction.get("currency", "USD"),
        }
        try:
            response = await model_router.complete(
                task=ModelTask.COMPLIANCE,
                system_prompt=APPROVAL_ROUTING_PROMPT,
                user_prompt=f"Route approval for:\n{json.dumps(context, default=str)[:2000]}",
                temperature=0.2,
                max_tokens=400,
            )
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Approval routing failed: {e}")

        amount = float(transaction.get("amount", 0))
        return {
            "approver_level": "cfo" if amount > 10000 else "manager",
            "approvers": [],
            "escalation_threshold": 10000,
            "urgency": "high" if violations else "low",
            "sla_hours": 4 if violations else 24,
            "auto_approve": amount < 1000 and not violations,
            "reason": "Standard routing",
        }


compliance_agent = ComplianceAgent()
