"""
FMP OHLC provider for financial market data.

Returns columnar OHLC (Open, High, Low, Close) data for stocks.
Works with the generic data pipeline (Financial is just a domain, not special).
"""
import requests
from typing import Dict, List, Optional, Any

from quantapy.data.providers.base import BaseProvider
from quantapy.registry.component_registry import register_component


@register_component(category="Market", function="OHLC", source="FMP")
class OHLC(BaseProvider):
    """
    Fetch OHLC data from Financial Modeling Prep (FMP).
    
    Parameters:
        source_ids: list of stock symbols (e.g., ["AAPL", "GOOGL"])
        interval: time interval (e.g., "1min", "5min", "15min", "30min", "1hour", "4hour", "1day")
        date_range: (optional) date range for historical data (not yet implemented)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = "sNfN2hHaQDfQj5lsxdS93VLuAGXk8JRA"
        
        # Accept both new 'source_ids' and legacy 'ticker' parameter names
        if "source_ids" not in self.params and "ticker" in self.params:
            self.params["source_ids"] = self.params["ticker"]
        
        # Default interval
        if "interval" not in self.params:
            self.params["interval"] = "1hour"

    def fetch_raw(self, symbol: str) -> List[Dict]:
        """Fetch raw OHLC data for a symbol from FMP."""
        interval = self.params.get("interval", "1hour").replace(" ", "")
        
        url = (
            f"https://financialmodelingprep.com/api/v3/historical-chart/"
            f"{interval}/{symbol}"
            f"?apikey={self.api_key}"
        )

        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
            else:
                print(f"Warning: FMP returned {r.status_code} for {symbol}")
                return []
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return []

    def execute(self) -> Dict[str, List[Dict]]:
        """
        Fetch OHLC data for all source_ids.
        
        Returns:
            Dict mapping symbol to list of OHLC dicts.
            E.g., {"AAPL": [{"open": 150, "high": 152, "low": 149, "close": 151, ...}, ...]}
        """
        results = {}
        source_ids = self.params.get("source_ids", [])
        
        if not source_ids:
            raise ValueError("No source_ids provided (expected: ['AAPL', 'GOOGL', ...])")
        
        for symbol in source_ids:
            results[symbol] = self.fetch_raw(symbol)
        
        return results