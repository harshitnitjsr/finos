"""
AFOS LangGraph State — shared state passed between all graph nodes.
"""
from __future__ import annotations
from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import BaseMessage
import operator


class AFOSState(TypedDict):
    """State flowing through the LangGraph supervisor."""

    # Core conversation
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Routing metadata
    intent: str                         # classified intent
    agent_id: str                       # which agent is handling
    agent_name: str                     # human-readable agent name
    run_id: str                         # unique ID for this LangGraph run
    org_id: str                         # tenant org ID
    session_id: str                     # chat session for history

    # Tool call tracking (appended as tools are called)
    tool_calls: Annotated[list[dict], operator.add]

    # Final answer
    final_response: Optional[str]

    # Memory context (Redis recent + Qdrant semantic hits) injected into agent prompts
    memory_context: str

    # Execution stats
    total_tokens: int
    total_duration_ms: int
