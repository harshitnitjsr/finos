"""
AI Agents API — live status from Redis heartbeats + DB agent log stats.
ROUTE ORDER IS CRITICAL: all static paths must come before /{agent_id} dynamic routes.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, case
from app.core.database import get_db
from app.core.redis_client import cache, TTL_AGENT_STATUS
from app.models.models import AgentLog, AgentToolLog

from app.api.deps import get_org_id

router = APIRouter()
# Agent registry — static config only, no hardcoded metrics
AGENT_REGISTRY = [
    {"id": "invoice-agent",     "name": "Invoice Intelligence",  "model": "gpt-4o-mini", "task": "extraction"},
    {"id": "expense-agent",     "name": "Expense Intelligence",  "model": "gpt-4o-mini", "task": "classification"},
    {"id": "compliance-agent",  "name": "Compliance Agent",      "model": "gpt-4o",      "task": "compliance"},
    {"id": "insight-agent",     "name": "Insight Agent",         "model": "gpt-4o",      "task": "reasoning"},
    {"id": "treasury-agent",    "name": "Treasury Agent",        "model": "gpt-4o",      "task": "forecast"},
    {"id": "vendor-agent",      "name": "Vendor Intelligence",   "model": "gpt-4o-mini", "task": "classification"},
    {"id": "approval-agent",    "name": "Approval Agent",        "model": "gpt-4o",      "task": "routing"},
    {"id": "forecasting-agent", "name": "Forecasting Agent",     "model": "gpt-4o",      "task": "forecast"},
]


async def _get_agent_db_stats(agent_id: str, org_id: str, db: AsyncSession) -> dict:
    """Pull actual invocation stats from agent_logs table for last 24h."""
    try:
        since = datetime.utcnow() - timedelta(hours=24)
        result = await db.execute(
            select(
                func.count(AgentLog.id).label("total"),
                func.avg(AgentLog.duration_ms).label("avg_ms"),
                func.sum(AgentLog.tokens_used).label("total_tokens"),
            ).where(
                AgentLog.agent_id == agent_id,
                AgentLog.org_id == org_id,
                AgentLog.created_at >= since,
            )
        )
        row = result.one()
        return {
            "requests_24h": int(row.total or 0),
            "avg_latency_ms": int(row.avg_ms or 0),
            "tokens_24h": int(row.total_tokens or 0),
        }
    except Exception:
        return {"requests_24h": 0, "avg_latency_ms": 0, "tokens_24h": 0}


# ── STATIC ROUTES (must come before any /{param} dynamic routes) ──────────────

@router.get("/status")
async def agents_status(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Live status of all 8 AI agents.
    Heartbeat from Redis + activity stats from agent_logs DB table.
    """
    cached = await cache.get("agent_status", org_id)
    if cached:
        return cached

    agents_out = []
    for agent_cfg in AGENT_REGISTRY:
        aid = agent_cfg["id"]
        heartbeat = await cache.get_agent_heartbeat(aid)
        stats = await _get_agent_db_stats(aid, org_id, db)
        agents_out.append({
            **agent_cfg,
            "status": "active" if heartbeat or stats["requests_24h"] > 0 else "idle",
            "last_active": heartbeat.get("timestamp") if heartbeat else None,
            **stats,
        })

    response = {
        "agents": agents_out,
        "total": len(agents_out),
        "active": sum(1 for a in agents_out if a["status"] in ("active", "idle")),
        "generated_at": datetime.utcnow().isoformat(),
    }
    await cache.set("agent_status", response, TTL_AGENT_STATUS, org_id)
    return response


@router.get("/tool-logs/summary")
async def get_tool_logs_summary(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Aggregated tool usage summary: call counts, avg latency, success rate per tool.
    """
    result = await db.execute(
        select(
            AgentToolLog.tool_name,
            AgentToolLog.agent_name,
            func.count(AgentToolLog.id).label("calls"),
            func.avg(AgentToolLog.duration_ms).label("avg_ms"),
            func.sum(case((AgentToolLog.status == "success", 1), else_=0)).label("successes"),
        )
        .where(AgentToolLog.org_id == org_id)
        .group_by(AgentToolLog.tool_name, AgentToolLog.agent_name)
        .order_by(desc(func.count(AgentToolLog.id)))
    )
    rows = result.all()
    return {
        "tools": [
            {
                "tool_name": r.tool_name,
                "agent_name": r.agent_name,
                "total_calls": r.calls,
                "avg_duration_ms": round(float(r.avg_ms or 0), 1),
                "success_rate": round(int(r.successes) / max(r.calls, 1) * 100, 1),
            }
            for r in rows
        ]
    }


@router.get("/tool-logs")
async def get_tool_logs(
    agent_id_filter: str = None,
    run_id: str = None,
    limit: int = 100,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Per-tool-call logs with full request + response JSON.
    Each entry shows: tool name, agent, input args, output data, duration_ms, status.
    """
    q = select(AgentToolLog).where(AgentToolLog.org_id == org_id)
    if agent_id_filter:
        q = q.where(AgentToolLog.agent_id == agent_id_filter)
    if run_id:
        q = q.where(AgentToolLog.run_id == run_id)
    q = q.order_by(desc(AgentToolLog.created_at)).limit(min(limit, 500))

    result = await db.execute(q)
    logs = result.scalars().all()
    return {
        "total": len(logs),
        "tool_logs": [
            {
                "id": l.id,
                "agent_id": l.agent_id,
                "agent_name": l.agent_name,
                "run_id": l.run_id,
                "tool_name": l.tool_name,
                "tool_description": l.tool_description,
                "input_data": l.input_data,
                "output_data": l.output_data,
                "input_summary": l.input_summary,
                "output_summary": l.output_summary,
                "duration_ms": l.duration_ms,
                "status": l.status,
                "error": l.error,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
    }


# ── DYNAMIC ROUTES (/{param} — must come AFTER all static routes) ─────────────

@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed profile + recent logs for one agent."""
    cfg = next((a for a in AGENT_REGISTRY if a["id"] == agent_id), None)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    heartbeat = await cache.get_agent_heartbeat(agent_id)
    stats = await _get_agent_db_stats(agent_id, org_id, db)

    logs_result = await db.execute(
        select(AgentLog)
        .where(AgentLog.agent_id == agent_id, AgentLog.org_id == org_id)
        .order_by(AgentLog.created_at.desc())
        .limit(10)
    )
    recent_logs = logs_result.scalars().all()

    return {
        **cfg,
        "status": "active" if heartbeat else "idle",
        "last_active": heartbeat.get("timestamp") if heartbeat else None,
        **stats,
        "recent_logs": [
            {
                "id": log.id,
                "action": log.action,
                "status": log.status,
                "duration_ms": log.duration_ms,
                "tokens_used": log.tokens_used,
                "created_at": log.created_at.isoformat(),
            }
            for log in recent_logs
        ],
    }


@router.get("/{agent_id}/logs")
async def get_agent_logs(
    agent_id: str,
    limit: int = 50,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Paginated agent invocation logs for one agent."""
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.agent_id == agent_id, AgentLog.org_id == org_id)
        .order_by(AgentLog.created_at.desc())
        .limit(min(limit, 200))
    )
    logs = result.scalars().all()
    return {
        "total": len(logs),
        "logs": [
            {
                "id": log.id,
                "action": log.action,
                "status": log.status,
                "input_summary": log.input_summary,
                "output_summary": log.output_summary,
                "duration_ms": log.duration_ms,
                "tokens_used": log.tokens_used,
                "model_used": log.model_used,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }
