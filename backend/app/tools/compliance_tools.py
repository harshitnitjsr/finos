"""
Compliance & Approval Tools — LangChain tools for Compliance and Approval Agents.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ApprovalsInput(BaseModel):
    status: Optional[str] = Field(default="pending", description="Filter by status: pending, approved, rejected, escalated")
    limit: int = Field(default=20, description="Max results")


class RiskItemsInput(BaseModel):
    risk_level: Optional[str] = Field(default="high", description="Risk level: medium, high, critical")
    include_invoices: bool = Field(default=True)
    include_expenses: bool = Field(default=True)


class PolicyCheckInput(BaseModel):
    amount: float = Field(description="Transaction amount to evaluate")
    currency: str = Field(default="USD", description="Currency code")
    vendor_verified: bool = Field(default=False)
    vendor_risk_score: float = Field(default=0.0)
    is_duplicate: bool = Field(default=False)
    is_international: bool = Field(default=False)


@tool("get_pending_approvals", args_schema=ApprovalsInput)
async def get_pending_approvals(status: Optional[str] = "pending", limit: int = 20) -> dict:
    """
    Get approval requests from the database filtered by status.
    Shows AI recommendations, risk levels, and amounts requiring decisions.
    Use for: 'pending approvals', 'what needs my approval?', 'approval queue', 'review items'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Approval, Invoice, Vendor
    from sqlalchemy import select, desc
    from app.core.context import org_id_var
    ORG_ID = org_id_var.get()

    async with AsyncSessionLocal() as db:
        q = (
            select(Approval, Invoice.invoice_number, Vendor.name.label("vendor_name"))
            .join(Invoice, Approval.invoice_id == Invoice.id, isouter=True)
            .join(Vendor, Invoice.vendor_id == Vendor.id, isouter=True)
            .where(Approval.org_id == ORG_ID)
        )
        if status:
            q = q.where(Approval.status == status.lower())
        q = q.order_by(desc(Approval.created_at)).limit(limit)

        result = await db.execute(q)
        rows = result.all()

        total_pending_amount = sum(float(r[0].amount or 0) for r in rows if r[0].status == "pending")
        return {
            "total_count": len(rows),
            "total_pending_amount": total_pending_amount,
            "approvals": [
                {
                    "id": r[0].id,
                    "invoice_number": r.invoice_number or "N/A",
                    "vendor": r.vendor_name or "Unknown",
                    "amount": float(r[0].amount or 0),
                    "currency": r[0].currency,
                    "status": r[0].status,
                    "risk_level": r[0].risk_level,
                    "risk_score": float(r[0].risk_score or 0),
                    "ai_recommendation": r[0].ai_recommendation,
                    "ai_explanation": r[0].ai_explanation,
                    "assigned_to": r[0].assigned_to,
                    "requested_by": r[0].requested_by,
                    "created_at": r[0].created_at.isoformat(),
                }
                for r in rows
            ],
        }


@tool("evaluate_policy_rules", args_schema=PolicyCheckInput)
async def evaluate_policy_rules(
    amount: float,
    currency: str = "USD",
    vendor_verified: bool = False,
    vendor_risk_score: float = 0.0,
    is_duplicate: bool = False,
    is_international: bool = False,
) -> dict:
    """
    Evaluate a transaction against distributed Open Policy Agent (OPA) rules.
    Always use this to check OPA rules.
    Use for: 'will this payment be blocked?', 'what policies apply?', 'check compliance'.
    """
    import httpx
    
    from app.core.config import settings
    opa_url = f"{settings.OPA_URL}/evaluate"
    
    input_data = {
        "input": {
            "amount": amount,
            "currency": currency,
            "vendor": {
                "verified": vendor_verified,
                "risk_score": vendor_risk_score
            },
            "is_duplicate": is_duplicate,
            "is_international": is_international
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(opa_url, json=input_data)
            
            if response.status_code == 200:
                result = response.json().get("result", {})
                
                # Format OPA output to match the expected schema back down to the agent
                violations = result.get("violations", [])
                is_compliant = result.get("allow", False) and len(violations) == 0
                
                return {
                    "compliant": is_compliant,
                    "violations_count": len(violations),
                    "violations": violations,
                    "auto_approve": result.get("allow", False) and amount < 5000, 
                    "required_approval_level": result.get("required_approval", "manager"),
                    "sla_hours": 4 if violations else 24,
                    "risk_score": min(len(violations) * 25, 100),
                }
            else:
                return {"error": f"OPA returned {response.status_code}: {response.text}"}
                
    except Exception as e:
        return {"error": f"Failed to connect to OPA: {str(e)}"}


@tool("get_high_risk_items", args_schema=RiskItemsInput)
async def get_high_risk_items(risk_level: Optional[str] = "high", include_invoices: bool = True, include_expenses: bool = True) -> dict:
    """
    Get all high-risk financial items (invoices and expenses) requiring attention.
    Returns items sorted by risk score with explanations.
    Use for: 'what are the risks?', 'high risk items', 'urgent financial risks', 'risk report'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Invoice, Expense
    from sqlalchemy import select, desc
    from app.core.context import org_id_var
    ORG_ID = org_id_var.get()

    valid_levels = {"medium": ["medium", "high", "critical"], "high": ["high", "critical"], "critical": ["critical"]}
    levels = valid_levels.get(risk_level or "high", ["high", "critical"])

    async with AsyncSessionLocal() as db:
        risky_invoices, risky_expenses = [], []

        if include_invoices:
            inv_result = await db.execute(
                select(Invoice).where(Invoice.org_id == ORG_ID, Invoice.risk_level.in_(levels))
                .order_by(desc(Invoice.risk_score)).limit(10)
            )
            risky_invoices = [
                {"type": "invoice", "id": i.id, "invoice_number": i.invoice_number, "amount": float(i.total_amount), "currency": i.currency, "risk_level": i.risk_level, "risk_score": float(i.risk_score or 0), "status": i.status}
                for i in inv_result.scalars().all()
            ]

        if include_expenses:
            exp_result = await db.execute(
                select(Expense).where(Expense.org_id == ORG_ID, Expense.is_anomaly == True)
                .order_by(desc(Expense.anomaly_score)).limit(10)
            )
            risky_expenses = [
                {"type": "expense", "id": e.id, "description": e.description, "amount": float(e.amount), "currency": e.currency, "risk_level": "high", "anomaly_score": float(e.anomaly_score or 0), "reason": e.anomaly_reason}
                for e in exp_result.scalars().all()
            ]

        all_items = risky_invoices + risky_expenses
        return {
            "total_high_risk_items": len(all_items),
            "invoices_at_risk": len(risky_invoices),
            "anomalous_expenses": len(risky_expenses),
            "items": all_items,
        }


COMPLIANCE_TOOLS = [get_pending_approvals, evaluate_policy_rules, get_high_risk_items]
