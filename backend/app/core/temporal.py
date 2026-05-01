"""
Temporal client connection management.
This is the central point for FastAPI to initialize a connection to the Temporal cluster.
"""
from typing import Optional
from temporalio.client import Client
from loguru import logger

from app.core.config import settings


class TemporalManager:
    def __init__(self):
        self.client: Optional[Client] = None

    async def connect(self):
        """Initialize the Temporal Client."""
        if self.client:
            return self.client

        try:
            logger.info(f"Connecting to Temporal at {settings.TEMPORAL_HOST} (namespace: {settings.TEMPORAL_NAMESPACE})")
            self.client = await Client.connect(
                settings.TEMPORAL_HOST,
                namespace=settings.TEMPORAL_NAMESPACE,
            )
            logger.info("Successfully connected to Temporal!")
            return self.client
        except Exception as e:
            logger.error(f"Failed to connect to Temporal: {e}")
            raise


temporal_manager = TemporalManager()
