"""SQLAlchemy database models for AFOS."""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String, Numeric, DateTime, Boolean, Text, Integer,
    ForeignKey, JSON, Enum as SAEnum, Index, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import enum


def gen_uuid():
    return str(uuid.uuid4())


class Currency(str, enum.Enum):
    USD = "USD"
    INR = "INR"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    AUD = "AUD"
    CAD = "CAD"
    SGD = "SGD"


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"
    OVERDUE = "overdue"
    DUPLICATE = "duplicate"


class ExpenseStatus(str, enum.Enum):
    PENDING = "pending"
    CATEGORIZED = "categorized"
    FLAGGED = "flagged"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    COMPENSATING = "compensating"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    default_currency: Mapped[str] = mapped_column(String(10), default="USD")
    fiscal_year_start: Mapped[int] = mapped_column(Integer, default=1)  # Month
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), default=datetime.utcnow)
    owner_user_id: Mapped[str] = mapped_column(String(36), nullable=True) # ID from auth.users
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    vendors = relationship("Vendor", back_populates="organization")
    invoices = relationship("Invoice", back_populates="organization")
    expenses = relationship("Expense", back_populates="organization")


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    total_paid: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    payment_currency: Mapped[str] = mapped_column(String(10), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="vendors")
    invoices = relationship("Invoice", back_populates="vendor")
    expenses = relationship("Expense", back_populates="vendor")

    __table_args__ = (Index("ix_vendors_org_id", "org_id"),)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=InvoiceStatus.PENDING)
    
    # Amounts
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    
    # Dates
    invoice_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # OCR & AI
    file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    ocr_raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[str] = mapped_column(String(36), nullable=True)
    
    # Risk & Compliance
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    policy_violations: Mapped[list] = mapped_column(JSON, default=list)
    
    # Notes
    description: Mapped[str] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="invoices")
    vendor = relationship("Vendor", back_populates="invoices")
    approvals = relationship("Approval", back_populates="invoice")

    __table_args__ = (
        Index("ix_invoices_org_id", "org_id"),
        Index("ix_invoices_status", "status"),
        Index("ix_invoices_due_date", "due_date"),
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    subcategory: Mapped[str] = mapped_column(String(100), nullable=True)
    department: Mapped[str] = mapped_column(String(100), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default=ExpenseStatus.PENDING)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_score: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0)
    anomaly_reason: Mapped[str] = mapped_column(Text, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_category_confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0)
    
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="expenses")
    vendor = relationship("Vendor", back_populates="expenses")

    __table_args__ = (
        Index("ix_expenses_org_id", "org_id"),
        Index("ix_expenses_category", "category"),
        Index("ix_expenses_transaction_date", "transaction_date"),
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default=ApprovalStatus.PENDING)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=True)
    assigned_to: Mapped[str] = mapped_column(String(255), nullable=True)
    decision_by: Mapped[str] = mapped_column(String(255), nullable=True)
    decision_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    ai_recommendation: Mapped[str] = mapped_column(String(20), nullable=True)  # approve/reject/escalate
    ai_explanation: Mapped[str] = mapped_column(Text, nullable=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    policy_checks: Mapped[list] = mapped_column(JSON, default=list)
    
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    invoice = relationship("Invoice", back_populates="approvals")

    __table_args__ = (Index("ix_approvals_org_id", "org_id"),)


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=WorkflowStatus.PENDING)
    
    steps: Mapped[list] = mapped_column(JSON, default=list)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_workflows_org_id", "org_id"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(50), default="user")  # user, agent, system
    
    changes: Mapped[dict] = mapped_column(JSON, default=dict)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_audit_logs_org_id", "org_id"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)

    # Identifies which agent ran
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)   # e.g. "invoice-agent"
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)      # e.g. "extract_invoice"
    status: Mapped[str] = mapped_column(String(50), default="success")   # success | failed

    # Model
    model_used: Mapped[str] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)          # total tokens
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Summaries (not raw data to keep table lean)
    input_summary: Mapped[str] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str] = mapped_column(Text, nullable=True)

    # Full data (optional, can be large)
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)

    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0)
    error: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_agent_logs_org_id", "org_id"),
        Index("ix_agent_logs_agent_id", "agent_id"),
    )


class AgentToolLog(Base):
    """Per-tool-call log: every LangChain tool invocation with req + res."""
    __tablename__ = "agent_tool_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Which agent triggered this tool
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Which LangGraph run this belongs to
    run_id: Mapped[str] = mapped_column(String(36), nullable=True)

    # Tool identity
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_description: Mapped[str] = mapped_column(Text, nullable=True)

    # Full req / res as JSON
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)

    # Summaries for quick display
    input_summary: Mapped[str] = mapped_column(String(500), nullable=True)
    output_summary: Mapped[str] = mapped_column(String(500), nullable=True)

    # Execution metrics
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="success")   # success | error
    error: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_agent_tool_logs_org_id", "org_id"),
        Index("ix_agent_tool_logs_agent_id", "agent_id"),
        Index("ix_agent_tool_logs_run_id", "run_id"),
    )


class ConversationMessage(Base):
    """
    Persistent conversation history store (SQL tier of memory system).
    Every chat turn — user + assistant — is stored here permanently,
    supplementing Redis (hot cache) and Qdrant (semantic recall).
    """
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Message content
    role: Mapped[str] = mapped_column(String(20), nullable=False)       # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Agent metadata (populated for assistant messages)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=True)

    # Tool usage snapshot
    tool_calls: Mapped[dict] = mapped_column(JSON, default=list)

    # Token and perf
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Whether this turn was embedded into Qdrant
    qdrant_indexed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_conv_msg_org_session", "org_id", "session_id"),
        Index("ix_conv_msg_created_at", "created_at"),
    )


class WorkspaceChat(Base):
    """
    A named conversation session in the AI Chatbot Workspace.
    Completely isolated from the floating widget's ConversationMessage table.
    One WorkspaceChat maps to one LangGraph session (session_id = 'ws_<uuid>').
    """
    __tablename__ = "workspace_chats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=True)   # auth user
    user_email: Mapped[str] = mapped_column(String(255), nullable=True)

    # Human-readable title (auto-generated from first message, then user-editable)
    title: Mapped[str] = mapped_column(String(255), default="New Chat")

    # Links to the LangGraph / memory session — prefix ws_ prevents
    # widget session IDs from leaking into workspace history
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Model metadata (future multi-model support)
    model: Mapped[str] = mapped_column(String(100), default="gpt-4o")

    # Stats (denormalised for sidebar display performance)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_preview: Mapped[str] = mapped_column(String(300), nullable=True)

    # Soft delete / archive
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("WorkspaceChatMessage", back_populates="chat", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_workspace_chats_org_id", "org_id"),
        Index("ix_workspace_chats_user_id", "user_id"),
        Index("ix_workspace_chats_updated_at", "updated_at"),
    )


class WorkspaceChatMessage(Base):
    """
    Per-turn message log for workspace conversations.
    Mirrors ConversationMessage but scoped to a WorkspaceChat.
    """
    __tablename__ = "workspace_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chat_id: Mapped[str] = mapped_column(ForeignKey("workspace_chats.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Message content
    role: Mapped[str] = mapped_column(String(20), nullable=False)   # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Agent metadata (assistant messages only)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=True)

    # Tool usage snapshot
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)

    # Memory sources used
    memory_used: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_sources: Mapped[list] = mapped_column(JSON, default=list)

    # Performance
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Whether embedded into Qdrant
    qdrant_indexed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chat = relationship("WorkspaceChat", back_populates="messages")

    __table_args__ = (
        Index("ix_workspace_messages_chat_id", "chat_id"),
        Index("ix_workspace_messages_org_id", "org_id"),
        Index("ix_workspace_messages_created_at", "created_at"),
    )
