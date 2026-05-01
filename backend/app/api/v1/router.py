"""API Router — combines all route modules."""
from fastapi import APIRouter
from app.api.v1 import invoices, expenses, approvals, analytics, agents, workflows, vendors, treasury, insights, chat, temporal_api

api_router = APIRouter()

api_router.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(agents.router, prefix="/agents", tags=["AI Agents"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
api_router.include_router(treasury.router, prefix="/treasury", tags=["Treasury"])
api_router.include_router(insights.router, prefix="/insights", tags=["AI Insights"])
api_router.include_router(chat.router, prefix="/chat", tags=["AI Chat"])
api_router.include_router(temporal_api.router, prefix="/temporal", tags=["Temporal Workflows"])
