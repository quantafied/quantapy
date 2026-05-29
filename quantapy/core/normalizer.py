from typing import List, Dict
from datetime import datetime

from quantapy.core.events import MarketEvent


class EventNormalizer:
    """Convert provider-specific payloads into normalized market events."""

    @staticmethod
    def parse_timestamp(value):
        """Parse supported timestamp values into ``datetime`` objects."""

        # already datetime
        if isinstance(value, datetime):
            return value

        # ISO string
        if isinstance(value, str):
            return datetime.fromisoformat(value)

        # fallback
        raise TypeError(
            f"Unsupported timestamp type: {type(value)}"
        )

    @staticmethod
    def ohlc_json_to_events(
        raw_data: List[Dict],
        symbol: str,
        source: str,
        dataset: str,
    ) -> List[MarketEvent]:
        """Convert FMP-style OHLC rows into ``MarketEvent`` instances."""

        events = []

        for row in raw_data:

            ts = EventNormalizer.parse_timestamp(row["date"])

            events.append(
                MarketEvent(
                    symbol=symbol,
                    timestamp=ts,
                    event_type="bar",
                    source=source,
                    payload={
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                    },
                    version="raw",
                    dataset=dataset,
                )
            )

        return events
