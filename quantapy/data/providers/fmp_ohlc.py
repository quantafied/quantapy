"""
FMP OHLC provider for financial market data.

Returns columnar OHLC (Open, High, Low, Close) data for stocks.
Works with the generic data pipeline (Financial is just a domain, not special).
"""
import requests
import os
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional

from quantapy.data.providers.base import BaseProvider
from quantapy.registry.component_registry import register_component


@register_component(category="Market", function="OHLC", source="FMP")
class OHLC(BaseProvider):
    """
    Fetch OHLC data from Financial Modeling Prep (FMP).
    
    Parameters:
        source_ids: list of stock symbols (e.g., ["AAPL", "GOOGL"])
        interval: time interval (e.g., "1min", "5min", "15min", "30min", "1hour", "4hour", "1day")
        date_range: common period or custom from/to dates
    """

    config = {
        "title": "FMP OHLC",
        "type": "object",
        "properties": {
            "source_ids": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["AAPL"],
                "description": "One or more ticker symbols",
                "widget_type": "multiselect",
            },
            "interval": {
                "type": "string",
                "default": "1hour",
                "description": "Historical chart interval",
                "enum": ["1min", "5min", "15min", "30min", "1hour", "4hour", "1day"],
                "widget_type": "select",
            },
            "date_range": {
                "type": "string",
                "default": "3mo",
                "description": "Date range to fetch",
                "enum": ["1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max", "custom"],
                "widget_type": "select",
            },
            "from_date": {
                "type": "string",
                "default": "",
                "description": "Custom start date",
                "widget_type": "date",
                "show_if": {"date_range": "custom"},
            },
            "to_date": {
                "type": "string",
                "default": "",
                "description": "Custom end date",
                "widget_type": "date",
                "show_if": {"date_range": "custom"},
            },
            "limit": {
                "type": "integer",
                "default": 0,
                "description": "Optional maximum rows after date filtering. Use 0 for no limit.",
            },
            "chunking": {
                "type": "string",
                "default": "auto",
                "description": "Split intraday date ranges into multiple FMP requests",
                "enum": ["auto", "off"],
                "widget_type": "select",
            },
            "chunk_days": {
                "type": "integer",
                "default": 0,
                "description": "Optional days per request. Use 0 for interval-based auto sizing.",
            },
            "chunk_safety_factor": {
                "type": "number",
                "default": 0.75,
                "description": "Fraction of observed FMP row limit to target per request.",
            },
            "coverage_grace_days": {
                "type": "integer",
                "default": 3,
                "description": "Calendar-day tolerance before a chunk is marked partial.",
            },
        },
    }

    STABLE_BASE_URL = "https://financialmodelingprep.com/stable"
    OBSERVED_ROW_LIMITS = {
        "4hour": 246,
        "1hour": 435,
        "30min": 273,
        "15min": 832,
        "5min": 546,
    }
    BARS_PER_TRADING_DAY = {
        "4hour": 2,
        "1hour": 7,
        "30min": 13,
        "15min": 26,
        "5min": 78,
    }

    def __init__(self, **kwargs):
        """Initialize FMP provider parameters and defaults."""
        super().__init__(**kwargs)
        self.api_key = self.params.get("api_key") or os.getenv("FMP_API_KEY")
        
        # Accept both new 'source_ids' and legacy 'ticker' parameter names
        if "source_ids" not in self.params and "ticker" in self.params:
            self.params["source_ids"] = self.params["ticker"]
        
        # Default interval
        if "interval" not in self.params:
            self.params["interval"] = "1hour"
        if "date_range" not in self.params:
            self.params["date_range"] = "3mo"
        if "chunking" not in self.params:
            self.params["chunking"] = "auto"
        self.fetch_metadata: Dict[str, Dict] = {}

    def _subtract_months(self, value: date, months: int) -> date:
        """Subtract calendar months without adding a dateutil dependency."""
        year = value.year
        month = value.month - months
        while month <= 0:
            year -= 1
            month += 12

        month_lengths = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                         31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        return date(year, month, min(value.day, month_lengths[month - 1]))

    def _date_window(self) -> Dict[str, str]:
        """Return FMP-compatible from/to query params for configured range."""
        date_range = str(self.params.get("date_range", "3mo")).lower()
        to_date = str(self.params.get("to_date") or date.today().isoformat())

        if date_range == "max":
            return {"to": to_date}

        if date_range == "custom":
            window = {}
            if self.params.get("from_date"):
                window["from"] = str(self.params["from_date"])
            if self.params.get("to_date"):
                window["to"] = str(self.params["to_date"])
            return window

        end = datetime.strptime(to_date, "%Y-%m-%d").date()
        if date_range == "1mo":
            start = self._subtract_months(end, 1)
        elif date_range == "3mo":
            start = self._subtract_months(end, 3)
        elif date_range == "6mo":
            start = self._subtract_months(end, 6)
        elif date_range == "1y":
            start = self._subtract_months(end, 12)
        elif date_range == "2y":
            start = self._subtract_months(end, 24)
        elif date_range == "5y":
            start = self._subtract_months(end, 60)
        elif date_range == "ytd":
            start = date(end.year, 1, 1)
        else:
            start = end - timedelta(days=90)

        return {"from": start.isoformat(), "to": end.isoformat()}

    def _endpoint_for_interval(self, interval: str) -> str:
        """Return the stable FMP endpoint for an OHLC interval."""
        if interval in {"1day", "daily", "day"}:
            return f"{self.STABLE_BASE_URL}/historical-price-eod/full"
        return f"{self.STABLE_BASE_URL}/historical-chart/{interval}"

    def _is_chunkable_interval(self, interval: str) -> bool:
        """Return whether the interval should be split into bounded requests."""
        return interval in self.OBSERVED_ROW_LIMITS

    def _auto_chunk_days(self, interval: str) -> int:
        """Estimate conservative request span from observed row caps."""
        override = int(self.params.get("chunk_days") or 0)
        if override > 0:
            return override

        row_limit = self.OBSERVED_ROW_LIMITS.get(interval)
        bars_per_day = self.BARS_PER_TRADING_DAY.get(interval)
        if not row_limit or not bars_per_day:
            return 0

        safety_factor = float(self.params.get("chunk_safety_factor") or 0.75)
        safety_factor = min(max(safety_factor, 0.1), 1.0)
        return max(1, int((row_limit * safety_factor) // bars_per_day))

    def _date_chunks(self, window: Dict[str, str], interval: str) -> List[Dict[str, str]]:
        """Split a requested window into FMP query windows."""
        if str(self.params.get("chunking", "auto")).lower() == "off":
            return [window]
        if not self._is_chunkable_interval(interval):
            return [window]
        if not window.get("from") or not window.get("to"):
            return [window]

        chunk_days = self._auto_chunk_days(interval)
        if chunk_days <= 0:
            return [window]

        start = datetime.strptime(window["from"], "%Y-%m-%d").date()
        end = datetime.strptime(window["to"], "%Y-%m-%d").date()
        chunks = []
        cursor = start
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
            chunks.append({"from": cursor.isoformat(), "to": chunk_end.isoformat()})
            cursor = chunk_end + timedelta(days=1)
        return chunks

    def _extract_rows(self, payload) -> List[Dict]:
        """Normalize known FMP response shapes into a row list."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("historical"), list):
            return payload["historical"]
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload["data"]
        return []

    def _parse_row_datetime(self, row: Dict) -> Optional[datetime]:
        """Parse an FMP row date or datetime value."""
        value = row.get("date")
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    def _filter_rows_by_window(self, rows: List[Dict], window: Dict[str, str]) -> List[Dict]:
        """Apply requested from/to filtering locally in case FMP returns a broader range."""
        if not window or not rows:
            return rows

        start = (
            datetime.combine(datetime.strptime(window["from"], "%Y-%m-%d").date(), time.min)
            if window.get("from")
            else None
        )
        end = (
            datetime.combine(datetime.strptime(window["to"], "%Y-%m-%d").date(), time.max)
            if window.get("to")
            else None
        )

        filtered = []
        for row in rows:
            row_dt = self._parse_row_datetime(row)
            if row_dt is None:
                filtered.append(row)
                continue
            if start is not None and row_dt < start:
                continue
            if end is not None and row_dt > end:
                continue
            filtered.append(row)
        return filtered

    def _row_bounds(self, rows: List[Dict]) -> Dict[str, Optional[str]]:
        """Return first and last row dates for a row collection."""
        dates = [
            str(row.get("date"))
            for row in rows
            if isinstance(row, dict) and row.get("date") is not None
        ]
        if not dates:
            return {"actual_from": None, "actual_to": None}
        ordered = sorted(dates)
        return {"actual_from": ordered[0], "actual_to": ordered[-1]}

    def _chunk_info(self, window: Dict[str, str], rows: List[Dict]) -> Dict:
        """Return diagnostics for one FMP request window."""
        bounds = self._row_bounds(rows)
        requested_from = window.get("from")
        actual_from = bounds["actual_from"]
        status = "complete"
        if not rows:
            status = "empty"
        elif requested_from and actual_from:
            requested_date = datetime.strptime(requested_from, "%Y-%m-%d").date()
            actual_date = datetime.strptime(actual_from[:10], "%Y-%m-%d").date()
            grace_days = int(self.params.get("coverage_grace_days") or 3)
            if (actual_date - requested_date).days > grace_days:
                status = "partial"
        return {
            "requested_from": window.get("from"),
            "requested_to": window.get("to"),
            "actual_from": bounds["actual_from"],
            "actual_to": bounds["actual_to"],
            "rows": len(rows),
            "status": status,
        }

    def _dedupe_rows(self, rows: List[Dict]) -> List[Dict]:
        """Sort and de-duplicate rows by date when available."""
        deduped = {}
        undated = []
        for row in rows:
            if isinstance(row, dict) and row.get("date") is not None:
                deduped[str(row["date"])] = row
            else:
                undated.append(row)
        return self._sort_chronological(list(deduped.values()) + undated)

    def _request_rows(self, symbol: str, interval: str, window: Dict[str, str]) -> List[Dict]:
        """Fetch one FMP request window."""
        query = {
            "symbol": symbol,
            "apikey": self.api_key,
            **window,
        }
        response = requests.get(self._endpoint_for_interval(interval), params=query, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"FMP returned {response.status_code} for {symbol}: {response.text[:200]}")
        rows = self._sort_chronological(self._extract_rows(response.json()))
        return self._filter_rows_by_window(rows, window)

    def fetch_raw(self, symbol: str) -> List[Dict]:
        """Fetch raw OHLC data for a symbol from FMP."""
        if not self.api_key:
            raise RuntimeError(
                "FMP API key is required. Set FMP_API_KEY or pass api_key=..."
            )

        interval = self.params.get("interval", "1hour").replace(" ", "")
        window = self._date_window()
        chunks = self._date_chunks(window, interval)
        rows = []
        chunk_infos = []

        try:
            for chunk in chunks:
                chunk_rows = self._request_rows(symbol, interval, chunk)
                chunk_infos.append(self._chunk_info(chunk, chunk_rows))
                rows.extend(chunk_rows)

            rows = self._dedupe_rows(rows)
            if not rows:
                raise RuntimeError(f"FMP returned no rows for {symbol}")
            limit = int(self.params.get("limit") or 0)
            if limit > 0:
                rows = rows[-limit:]

            empty_chunks = [chunk for chunk in chunk_infos if chunk["status"] == "empty"]
            partial_chunks = [chunk for chunk in chunk_infos if chunk["status"] == "partial"]
            bounds = self._row_bounds(rows)
            chunk_days = self._auto_chunk_days(interval) if len(chunks) > 1 else 0
            self.fetch_metadata[symbol] = {
                "chunking": "auto" if len(chunks) > 1 else "off",
                "chunk_days": chunk_days,
                "chunks_requested": len(chunks),
                "chunks_returned": sum(1 for chunk in chunk_infos if chunk["rows"] > 0),
                "empty_chunks": len(empty_chunks),
                "partial_chunks": len(partial_chunks),
                "chunk_status": chunk_infos,
                "missing_data": bool(empty_chunks or partial_chunks),
                **bounds,
            }
            return rows
        except Exception as e:
            raise RuntimeError(f"Error fetching {symbol}: {e}") from e

    def _sort_chronological(self, rows: List[Dict]) -> List[Dict]:
        """Return FMP rows ordered oldest to newest when a date column exists."""
        if not rows or not all(isinstance(row, dict) and "date" in row for row in rows):
            return rows
        return sorted(rows, key=lambda row: row["date"])

    def execute(self) -> Dict[str, List[Dict]]:
        """
        Fetch OHLC data for all source_ids.
        
        Returns:
            Dict mapping symbol to list of OHLC dicts.
            E.g., {"AAPL": [{"open": 150, "high": 152, "low": 149, "close": 151, ...}, ...]}
        """
        results = {}
        source_ids = self.params.get("source_ids", [])
        if isinstance(source_ids, str):
            source_ids = [item.strip() for item in source_ids.split(",") if item.strip()]
        
        if not source_ids:
            raise ValueError("No source_ids provided (expected: ['AAPL', 'GOOGL', ...])")
        
        for symbol in source_ids:
            results[symbol] = self.fetch_raw(symbol)
        
        return results
