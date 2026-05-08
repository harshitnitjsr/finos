"""
Qdrant Vector Store Service — full implementation.
Handles: collection management, embedding upsert, semantic search,
         vendor dedup, invoice duplicate detection, anomaly clustering.
"""
import uuid
from typing import Optional
from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
    UpdateStatus,
    PayloadSchemaType,
)

from app.core.config import settings

# Collection names
COLLECTION_INVOICES = "afos_invoices"
COLLECTION_EXPENSES = "afos_expenses"
COLLECTION_VENDORS = "afos_vendors"
COLLECTION_ANOMALIES = "afos_anomalies"
COLLECTION_CONVERSATIONS = "afos_conversations"  # semantic memory
COLLECTION_WORKFLOWS = "afos_workflows"           # workflow context RAG

VECTOR_DIM = 1024  # bge-m3 dimension (DO Tier 1 free embedding model)


class VectorStoreService:
    """
    Qdrant-backed vector store for semantic financial search and deduplication.
    All collections use bge-m3 (1024 dims, cosine similarity) via DO Inference Hub.
    """

    def __init__(self):
        self.client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=10
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Create all required collections if they don't exist."""
        collections_to_create = [
            COLLECTION_INVOICES,
            COLLECTION_EXPENSES,
            COLLECTION_VENDORS,
            COLLECTION_ANOMALIES,
            COLLECTION_CONVERSATIONS,
            COLLECTION_WORKFLOWS,
        ]
        try:
            existing = await self.client.get_collections()
            existing_names = {c.name for c in existing.collections}

            for name in collections_to_create:
                if name not in existing_names:
                    await self.client.create_collection(
                        collection_name=name,
                        vectors_config=VectorParams(
                            size=VECTOR_DIM,
                            distance=Distance.COSINE,
                        ),
                    )
                    logger.info(f"Qdrant: created collection '{name}'")
                else:
                    logger.info(f"Qdrant: collection '{name}' already exists")

                # Ensure org_id index exists (required by some Qdrant providers like DO/Cloud)
                try:
                    await self.client.create_payload_index(
                        collection_name=name,
                        field_name="org_id",
                        field_schema=PayloadSchemaType.KEYWORD,
                    )
                    logger.info(f"Qdrant: ensured 'org_id' index for '{name}'")
                except Exception as e:
                    # Ignore if index already exists or other non-critical issues
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Qdrant: could not create 'org_id' index for {name}: {e}")

            self._initialized = True
            logger.info("✅ Qdrant vector store initialized")
        except Exception as e:
            logger.error(f"Qdrant initialization failed: {e}")

    # ── Conversation memory operations ──────────────────────────────────────

    async def upsert_conversation_turn(
        self,
        turn_id: str,
        embedding: list[float],
        payload: dict,
    ) -> bool:
        """Store a conversation turn embedding for semantic long-term recall."""
        try:
            result = await self.client.upsert(
                collection_name=COLLECTION_CONVERSATIONS,
                points=[
                    PointStruct(
                        id=_stable_uuid(turn_id),
                        vector=embedding,
                        payload={
                            "turn_id": turn_id,
                            "org_id": payload.get("org_id"),
                            "session_id": payload.get("session_id"),
                            "role": payload.get("role"),
                            "content": payload.get("content", "")[:1000],
                            "agent_name": payload.get("agent_name", ""),
                            "intent": payload.get("intent", ""),
                            "created_at": payload.get("created_at", ""),
                        },
                    )
                ],
            )
            return result.status == UpdateStatus.COMPLETED
        except Exception as e:
            logger.error(f"Qdrant upsert_conversation_turn failed: {e}")
            return False

    async def search_similar_turns(
        self,
        embedding: list[float],
        org_id: str,
        limit: int = 4,
        threshold: float = 0.72,
        exclude_session: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search over all past conversation turns.
        Returns the most relevant past Q&A pairs to inject as RAG context.
        """
        try:
            conditions = [FieldCondition(key="org_id", match=MatchValue(value=org_id))]
            results = await self.client.search(
                collection_name=COLLECTION_CONVERSATIONS,
                query_vector=embedding,
                limit=limit,
                score_threshold=threshold,
                query_filter=Filter(must=conditions),
                with_payload=True,
            )
            out = []
            for r in results:
                # Skip turns from same current session to avoid echo
                if exclude_session and r.payload.get("session_id") == exclude_session:
                    continue
                out.append({
                    "turn_id": r.payload.get("turn_id"),
                    "role": r.payload.get("role"),
                    "content": r.payload.get("content"),
                    "agent_name": r.payload.get("agent_name"),
                    "intent": r.payload.get("intent"),
                    "score": round(r.score, 3),
                })
            return out
        except Exception as e:
            logger.error(f"Qdrant search_similar_turns failed: {e}")
            return []

    # ── Invoice operations ───────────────────────────────────────────────────

    async def upsert_invoice(
        self,
        invoice_id: str,
        embedding: list[float],
        payload: dict,
    ) -> bool:
        """Index an invoice vector for duplicate/semantic search."""
        try:
            result = await self.client.upsert(
                collection_name=COLLECTION_INVOICES,
                points=[
                    PointStruct(
                        id=_stable_uuid(invoice_id),
                        vector=embedding,
                        payload={
                            "invoice_id": invoice_id,
                            "org_id": payload.get("org_id"),
                            "vendor_name": payload.get("vendor_name", ""),
                            "invoice_number": payload.get("invoice_number", ""),
                            "total_amount": float(payload.get("total_amount") or 0),
                            "currency": payload.get("currency", "USD"),
                            "invoice_date": payload.get("invoice_date", ""),
                        },
                    )
                ],
            )
            return result.status == UpdateStatus.COMPLETED
        except Exception as e:
            logger.error(f"Qdrant upsert_invoice failed: {e}")
            return False

    async def find_duplicate_invoices(
        self,
        embedding: list[float],
        org_id: str,
        threshold: float = 0.92,
        exclude_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Find invoices semantically similar to the given embedding.
        Returns list of {invoice_id, score, payload} for score >= threshold.
        """
        try:
            filter_conditions = [FieldCondition(key="org_id", match=MatchValue(value=org_id))]
            results = await self.client.search(
                collection_name=COLLECTION_INVOICES,
                query_vector=embedding,
                limit=5,
                score_threshold=threshold,
                query_filter=Filter(must=filter_conditions),
                with_payload=True,
            )
            return [
                {
                    "invoice_id": r.payload.get("invoice_id"),
                    "score": r.score,
                    "vendor_name": r.payload.get("vendor_name"),
                    "invoice_number": r.payload.get("invoice_number"),
                    "total_amount": r.payload.get("total_amount"),
                }
                for r in results
                if r.payload.get("invoice_id") != exclude_id
            ]
        except Exception as e:
            logger.error(f"Qdrant duplicate search failed: {e}")
            return []

    # ── Vendor operations ────────────────────────────────────────────────────

    async def upsert_vendor(
        self,
        vendor_id: str,
        embedding: list[float],
        payload: dict,
    ) -> bool:
        """Index a vendor for semantic matching (fuzzy name lookup)."""
        try:
            result = await self.client.upsert(
                collection_name=COLLECTION_VENDORS,
                points=[
                    PointStruct(
                        id=_stable_uuid(vendor_id),
                        vector=embedding,
                        payload={
                            "vendor_id": vendor_id,
                            "org_id": payload.get("org_id"),
                            "name": payload.get("name", ""),
                            "category": payload.get("category", ""),
                            "risk_level": payload.get("risk_level", "low"),
                            "risk_score": float(payload.get("risk_score") or 0),
                            "is_verified": bool(payload.get("is_verified", False)),
                        },
                    )
                ],
            )
            return result.status == UpdateStatus.COMPLETED
        except Exception as e:
            logger.error(f"Qdrant upsert_vendor failed: {e}")
            return False

    async def find_similar_vendors(
        self,
        embedding: list[float],
        org_id: str,
        threshold: float = 0.85,
        limit: int = 5,
    ) -> list[dict]:
        """
        Semantic vendor matching — finds similar vendors even with typos/variations.
        Returns best matches with similarity score.
        """
        try:
            results = await self.client.search(
                collection_name=COLLECTION_VENDORS,
                query_vector=embedding,
                limit=limit,
                score_threshold=threshold,
                query_filter=Filter(
                    must=[FieldCondition(key="org_id", match=MatchValue(value=org_id))]
                ),
                with_payload=True,
            )
            return [
                {
                    "vendor_id": r.payload.get("vendor_id"),
                    "name": r.payload.get("name"),
                    "score": r.score,
                    "category": r.payload.get("category"),
                    "risk_level": r.payload.get("risk_level"),
                    "is_verified": r.payload.get("is_verified"),
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Qdrant vendor search failed: {e}")
            return []

    # ── Expense / anomaly operations ─────────────────────────────────────────

    async def upsert_expense(
        self,
        expense_id: str,
        embedding: list[float],
        payload: dict,
    ) -> bool:
        """Index an expense for anomaly clustering."""
        try:
            result = await self.client.upsert(
                collection_name=COLLECTION_EXPENSES,
                points=[
                    PointStruct(
                        id=_stable_uuid(expense_id),
                        vector=embedding,
                        payload={
                            "expense_id": expense_id,
                            "org_id": payload.get("org_id"),
                            "category": payload.get("category", ""),
                            "amount": float(payload.get("amount") or 0),
                            "currency": payload.get("currency", "USD"),
                            "vendor_name": payload.get("vendor_name", ""),
                            "is_anomaly": bool(payload.get("is_anomaly", False)),
                        },
                    )
                ],
            )
            return result.status == UpdateStatus.COMPLETED
        except Exception as e:
            logger.error(f"Qdrant upsert_expense failed: {e}")
            return False

    async def find_similar_expenses(
        self,
        embedding: list[float],
        org_id: str,
        category: Optional[str] = None,
        threshold: float = 0.8,
        limit: int = 10,
    ) -> list[dict]:
        """Find similar historical expenses — used for anomaly comparison."""
        try:
            conditions = [FieldCondition(key="org_id", match=MatchValue(value=org_id))]
            if category:
                conditions.append(FieldCondition(key="category", match=MatchValue(value=category)))

            results = await self.client.search(
                collection_name=COLLECTION_EXPENSES,
                query_vector=embedding,
                limit=limit,
                score_threshold=threshold,
                query_filter=Filter(must=conditions),
                with_payload=True,
            )
            return [
                {
                    "expense_id": r.payload.get("expense_id"),
                    "amount": r.payload.get("amount"),
                    "currency": r.payload.get("currency"),
                    "vendor_name": r.payload.get("vendor_name"),
                    "score": r.score,
                    "is_anomaly": r.payload.get("is_anomaly"),
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Qdrant expense search failed: {e}")
            return []

    # ── Anomaly operations ────────────────────────────────────────────────────

    async def upsert_anomaly(
        self,
        anomaly_id: str,
        embedding: list[float],
        payload: dict,
    ) -> bool:
        """Index an anomaly embedding for clustering and pattern detection."""
        try:
            result = await self.client.upsert(
                collection_name=COLLECTION_ANOMALIES,
                points=[
                    PointStruct(
                        id=_stable_uuid(anomaly_id),
                        vector=embedding,
                        payload={
                            "anomaly_id": anomaly_id,
                            "org_id": payload.get("org_id"),
                            "category": payload.get("category", ""),
                            "amount": float(payload.get("amount") or 0),
                            "vendor_name": payload.get("vendor_name", ""),
                            "anomaly_score": float(payload.get("anomaly_score") or 0),
                            "reason": payload.get("reason", ""),
                            "detected_at": payload.get("detected_at", ""),
                        },
                    )
                ],
            )
            return result.status == UpdateStatus.COMPLETED
        except Exception as e:
            logger.error(f"Qdrant upsert_anomaly failed: {e}")
            return False

    async def find_similar_anomalies(
        self,
        embedding: list[float],
        org_id: str,
        threshold: float = 0.80,
        limit: int = 5,
    ) -> list[dict]:
        """Find semantically similar past anomalies — used for anomaly explanation enrichment."""
        try:
            results = await self.client.search(
                collection_name=COLLECTION_ANOMALIES,
                query_vector=embedding,
                limit=limit,
                score_threshold=threshold,
                query_filter=Filter(
                    must=[FieldCondition(key="org_id", match=MatchValue(value=org_id))]
                ),
                with_payload=True,
            )
            return [
                {
                    "anomaly_id": r.payload.get("anomaly_id"),
                    "category": r.payload.get("category"),
                    "vendor_name": r.payload.get("vendor_name"),
                    "amount": r.payload.get("amount"),
                    "anomaly_score": r.payload.get("anomaly_score"),
                    "reason": r.payload.get("reason"),
                    "score": round(r.score, 3),
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Qdrant anomaly search failed: {e}")
            return []

    # ── Workflow context operations ────────────────────────────────────────────

    async def upsert_workflow_context(
        self,
        workflow_id: str,
        embedding: list[float],
        payload: dict,
    ) -> bool:
        """Index workflow execution context for semantic retrieval and pattern learning."""
        try:
            result = await self.client.upsert(
                collection_name=COLLECTION_WORKFLOWS,
                points=[
                    PointStruct(
                        id=_stable_uuid(workflow_id),
                        vector=embedding,
                        payload={
                            "workflow_id": workflow_id,
                            "org_id": payload.get("org_id"),
                            "workflow_type": payload.get("workflow_type", ""),
                            "invoice_id": payload.get("invoice_id", ""),
                            "status": payload.get("status", ""),
                            "amount": float(payload.get("amount") or 0),
                            "risk_level": payload.get("risk_level", ""),
                            "outcome": payload.get("outcome", ""),
                            "completed_at": payload.get("completed_at", ""),
                        },
                    )
                ],
            )
            return result.status == UpdateStatus.COMPLETED
        except Exception as e:
            logger.error(f"Qdrant upsert_workflow_context failed: {e}")
            return False

    async def search_similar_workflows(
        self,
        embedding: list[float],
        org_id: str,
        threshold: float = 0.78,
        limit: int = 4,
    ) -> list[dict]:
        """Find similar past workflow executions — aids approval routing decisions."""
        try:
            results = await self.client.search(
                collection_name=COLLECTION_WORKFLOWS,
                query_vector=embedding,
                limit=limit,
                score_threshold=threshold,
                query_filter=Filter(
                    must=[FieldCondition(key="org_id", match=MatchValue(value=org_id))]
                ),
                with_payload=True,
            )
            return [
                {
                    "workflow_id": r.payload.get("workflow_id"),
                    "workflow_type": r.payload.get("workflow_type"),
                    "status": r.payload.get("status"),
                    "outcome": r.payload.get("outcome"),
                    "risk_level": r.payload.get("risk_level"),
                    "amount": r.payload.get("amount"),
                    "score": round(r.score, 3),
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Qdrant workflow search failed: {e}")
            return []

    async def get_collection_stats(self) -> dict:
        """Get stats for all collections."""
        stats = {}
        for name in [
            COLLECTION_INVOICES, COLLECTION_EXPENSES, COLLECTION_VENDORS,
            COLLECTION_ANOMALIES, COLLECTION_CONVERSATIONS, COLLECTION_WORKFLOWS,
        ]:
            try:
                info = await self.client.get_collection(name)
                stats[name] = {
                    "vectors_count": info.vectors_count,
                    "points_count": info.points_count,
                    "status": str(info.status),
                }
            except Exception:
                stats[name] = {"status": "unavailable"}
        return stats

    async def ping(self) -> bool:
        """Check Qdrant connectivity."""
        try:
            await self.client.get_collections()
            return True
        except Exception:
            return False


def _stable_uuid(source_id: str) -> str:
    """Convert any string ID to a stable UUID (Qdrant requires UUID or int)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, source_id))


# Singleton
vector_store = VectorStoreService()
