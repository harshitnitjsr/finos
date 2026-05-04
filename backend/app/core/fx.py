import httpx
import json
from typing import Dict, Optional
from loguru import logger
from app.core.redis_client import redis_client

class FXService:
    """Service for fetching and caching live exchange rates."""
    
    BASE_URL = "https://api.frankfurter.dev/v1/latest"
    CACHE_PREFIX = "afos:fx_rates:"
    TTL = 86400  # 24 hours

    async def get_rates(self, base_currency: str = "USD") -> Dict[str, float]:
        """
        Fetch exchange rates for a base currency.
        Checks Redis cache first, then calls Frankfurter API.
        """
        cache_key = f"{self.CACHE_PREFIX}{base_currency}"
        
        # 1. Try cache
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"FX Cache Read Error: {e}")

        # 2. Fetch from API
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(f"{self.BASE_URL}?from={base_currency}")
                response.raise_for_status()
                data = response.json()
                
                rates = data.get("rates", {})
                # API doesn't include base currency in rates (it's 1.0)
                rates[base_currency] = 1.0
                
                # 3. Cache results
                await redis_client.set(cache_key, json.dumps(rates), ex=self.TTL)
                return rates
        except Exception as e:
            logger.error(f"FX API Error (base={base_currency}): {e}")
            # Fallback to 1.0 for the base currency at least
            return {base_currency: 1.0}

    def convert(self, amount: float, from_currency: str, to_currency: str, rates: Dict[str, float]) -> float:
        """
        Convert an amount between currencies using provided rates.
        Rates should be relative to the 'to_currency' as base.
        """
        if from_currency == to_currency:
            return amount
        
        # If rates are relative to to_currency, we need to find how many 'from' per 'to'
        # Frankfurter returns rates where 1 base_currency = X foreign_currency
        # So if base is 'to_currency', then: 1 to_currency = X from_currency
        # Therefore: amount in to_currency = amount in from_currency / X
        
        rate = rates.get(from_currency)
        if rate:
            return amount / rate
        
        # If rate not found, return original amount (graceful failure)
        return amount

fx_service = FXService()
