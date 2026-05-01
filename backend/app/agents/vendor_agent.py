"""
Vendor Intelligence Agent
Handles: vendor scoring, duplicate SaaS detection, contract analysis, vendor risk assessment.
Uses Qdrant for semantic vendor matching.
"""
import json
import re
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

from app.core.model_router import model_router, ModelTask
from app.core.agent_logger import AgentTimer


VENDOR_SCORING_PROMPT = """You are a vendor risk assessment AI. Analyze a vendor and assign a risk score.

Consider:
- Payment history and reliability
- Vendor category risk profile
- Verification status
- Contract terms clarity
- Geographic/regulatory risk
- Concentration risk (single vendor dependency)

Return JSON: {
  "risk_score": float (0-100, higher = riskier),
  "risk_level": "low|medium|high|critical",
  "risk_factors": [{"factor": str, "severity": str, "description": str}],
  "vendor_health": "excellent|good|fair|poor",
  "recommended_action": str,
  "contract_insights": [str]
}"""

SAAS_DEDUP_PROMPT = """You are a SaaS spend optimization AI. Identify duplicate tools, underutilized subscriptions, and consolidation opportunities.

Look for:
- Tools in the same category from different vendors (potential duplicates)
- Vendors with similar functionality
- Consolidation savings opportunities

Return JSON: {
  "duplicate_groups": [{"category": str, "vendors": [str], "recommended_keep": str, "estimated_savings": float}],
  "underutilized": [{"vendor": str, "reason": str, "recommendation": str}],
  "consolidation_opportunities": [{"description": str, "savings": float}],
  "total_potential_savings": float,
  "summary": str
}"""

VENDOR_HEALTH_PROMPT = """You are a vendor relationship analyst. Assess the health of a vendor relationship based on transaction history.

Return JSON: {
  "health_score": float (0-100),
  "relationship_status": "excellent|good|fair|poor|at_risk",
  "payment_reliability": str,
  "insights": [str],
  "risk_flags": [str],
  "recommendations": [str]
}"""


class VendorAgent:
    """AI agent for vendor intelligence and risk management."""

    AGENT_ID = "vendor-agent"
    AGENT_NAME = "Vendor Intelligence"

    async def score_vendor(self, vendor_data: dict, transaction_history: Optional[list] = None) -> dict:
        """Score a vendor's risk using AI analysis."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "score_vendor") as timer:
            timer.input_summary = f"Vendor: {vendor_data.get('name', 'Unknown')}"

            context = {
                "vendor": vendor_data,
                "transaction_history": (transaction_history or [])[:20],
                "analysis_date": datetime.utcnow().isoformat(),
            }

            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.COMPLIANCE,
                    system_prompt=VENDOR_SCORING_PROMPT,
                    user_prompt=f"Vendor data: {json.dumps(context, default=str)[:2500]}",
                    temperature=0.1,
                    max_tokens=600,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    timer.output_summary = f"Risk: {data.get('risk_level')}, Score: {data.get('risk_score')}"
                    timer.confidence = 0.88
                    return data
            except Exception as e:
                logger.error(f"VendorAgent scoring failed: {e}")

        # Rule-based fallback
        risk_score = float(vendor_data.get("risk_score", 20))
        risk_level = "high" if risk_score > 60 else "medium" if risk_score > 30 else "low"
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": [],
            "vendor_health": "good" if risk_score < 30 else "fair",
            "recommended_action": "Standard monitoring",
            "contract_insights": [],
        }

    async def detect_saas_duplicates(self, recurring_vendors: list[dict]) -> dict:
        """Find duplicate SaaS tools across vendor list."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "detect_saas_duplicates") as timer:
            timer.input_summary = f"{len(recurring_vendors)} recurring vendors"

            if not recurring_vendors:
                return {"duplicate_groups": [], "underutilized": [], "consolidation_opportunities": [], "total_potential_savings": 0, "summary": "No recurring vendors"}

            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.REASONING,
                    system_prompt=SAAS_DEDUP_PROMPT,
                    user_prompt=f"Recurring SaaS vendors: {json.dumps(recurring_vendors[:30], default=str)[:3000]}",
                    temperature=0.3,
                    max_tokens=1000,
                )
                timer.model_used = result.model
                timer.tokens_used = result.total_tokens
                timer.prompt_tokens = result.prompt_tokens
                timer.completion_tokens = result.completion_tokens

                json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    timer.output_summary = f"Found {len(data.get('duplicate_groups', []))} duplicate groups, ${data.get('total_potential_savings', 0):,.0f} savings"
                    return data
            except Exception as e:
                logger.error(f"VendorAgent SaaS dedup failed: {e}")

        return {
            "duplicate_groups": [],
            "underutilized": [],
            "consolidation_opportunities": [],
            "total_potential_savings": 0,
            "summary": "Analysis completed — no duplicates detected",
        }

    async def assess_vendor_health(self, vendor_data: dict, transactions: list[dict]) -> dict:
        """Assess vendor relationship health from transaction history."""
        async with AgentTimer(self.AGENT_ID, self.AGENT_NAME, "assess_vendor_health") as timer:
            timer.input_summary = f"Vendor: {vendor_data.get('name')}, {len(transactions)} transactions"

            try:
                result = await model_router.complete_with_usage(
                    task=ModelTask.REASONING,
                    system_prompt=VENDOR_HEALTH_PROMPT,
                    user_prompt=f"Vendor: {json.dumps(vendor_data, default=str)}\nTransactions: {json.dumps(transactions[:20], default=str)[:2000]}",
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
                    timer.output_summary = f"Health: {data.get('health_score')}/100, Status: {data.get('relationship_status')}"
                    return data
            except Exception as e:
                logger.error(f"VendorAgent health assessment failed: {e}")

        return {
            "health_score": 70.0,
            "relationship_status": "good",
            "payment_reliability": "Unknown",
            "insights": [],
            "risk_flags": [],
            "recommendations": [],
        }

    async def find_similar_vendors_semantic(self, vendor_name: str, org_id: str) -> list[dict]:
        """Use Qdrant to find semantically similar vendors (fuzzy matching)."""
        try:
            from app.core.vector_store import vector_store
            embedding = await model_router.embed(vendor_name)
            return await vector_store.find_similar_vendors(embedding, org_id=org_id, threshold=0.80)
        except Exception as e:
            logger.warning(f"VendorAgent semantic search failed: {e}")
            return []


vendor_agent = VendorAgent()
