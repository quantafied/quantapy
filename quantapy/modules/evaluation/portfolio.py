"""
Standalone portfolio analytics module intended to replace pyfolio dependency.

Features
--------
- Fully self-contained
- Minimal dependencies (numpy, pandas)
- Stable / maintainable
- Vectorized computations
- Compatible with your Quantapy backtest outputs

Implemented Metrics
-------------------
✓ CAGR / Annual Return
✓ Annual Volatility
✓ Sharpe Ratio
✓ Sortino Ratio
✓ Calmar Ratio
✓ Max Drawdown
✓ Omega Ratio
✓ Downside Risk
✓ Tail Ratio
✓ Common Sense Ratio
✓ Value at Risk (VaR)
✓ Rolling Volatility
✓ Rolling Sharpe
✓ Cumulative Returns
✓ Drawdown Series

Author
------
Designed as a pyfolio replacement for Quantapy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# Utility Functions
# ============================================================

def infer_periods_per_year(index: pd.Series | pd.DatetimeIndex) -> int:
    """
    Infer annualization factor from datetime index frequency.
    """

    if not isinstance(index, pd.DatetimeIndex):
        return 252

    if len(index) < 2:
        return 252

    delta = (index[1] - index[0]).total_seconds()

    # Approximate frequency detection
    minute = 60
    hour = 3600
    day = 86400

    if delta <= minute:
        return 252 * 6.5 * 60
    elif delta <= 5 * minute:
        return int(252 * 6.5 * 12)
    elif delta <= hour:
        return int(252 * 6.5)
    elif delta <= day:
        return 252
    else:
        return 12


def to_returns(equity: pd.Series) -> pd.Series:
    """
    Convert equity curve into returns series.
    """
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan)
    return returns.dropna()


# ============================================================
# Core Metrics
# ============================================================

def cumulative_returns(returns: pd.Series) -> pd.Series:
    """Convert periodic returns into a cumulative return curve."""
    return (1 + returns).cumprod()


def drawdown_series(returns: pd.Series) -> pd.Series:
    """Compute drawdown from the cumulative return high-water mark."""
    cumulative = cumulative_returns(returns)
    peaks = cumulative.cummax()
    return (cumulative - peaks) / peaks


def max_drawdown(returns: pd.Series) -> float:
    """Return the worst drawdown in a return series."""
    return drawdown_series(returns).min()


def annual_return(
    returns: pd.Series,
    periods_per_year: int = 252
) -> float:
    """Annualize total return over the observed number of periods."""

    cumulative = cumulative_returns(returns)

    if len(cumulative) == 0:
        return np.nan

    total_return = cumulative.iloc[-1]
    years = len(returns) / periods_per_year

    if years <= 0:
        return np.nan

    return total_return ** (1 / years) - 1


def annual_volatility(
    returns: pd.Series,
    periods_per_year: int = 252
) -> float:
    """Annualize the standard deviation of periodic returns."""

    return returns.std(ddof=1) * np.sqrt(periods_per_year)


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """Compute annualized Sharpe ratio using a constant risk-free rate."""

    excess = returns - (risk_free_rate / periods_per_year)

    vol = excess.std(ddof=1)

    if vol == 0:
        return np.nan

    return (
        excess.mean() / vol
    ) * np.sqrt(periods_per_year)


def downside_risk(
    returns: pd.Series,
    required_return: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """Compute annualized downside deviation below a required return."""

    downside = np.minimum(
        returns - required_return,
        0
    )

    downside_std = np.sqrt(np.mean(downside ** 2))

    return downside_std * np.sqrt(periods_per_year)


def sortino_ratio(
    returns: pd.Series,
    required_return: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """Compute annualized Sortino ratio using downside risk."""

    drisk = downside_risk(
        returns,
        required_return,
        periods_per_year
    )

    if drisk == 0:
        return np.nan

    annualized_return = (
        returns.mean() * periods_per_year
    )

    return (
        annualized_return - required_return
    ) / drisk


def calmar_ratio(
    returns: pd.Series,
    periods_per_year: int = 252
) -> float:
    """Compute annual return divided by absolute max drawdown."""

    mdd = abs(max_drawdown(returns))

    if mdd == 0:
        return np.nan

    return annual_return(
        returns,
        periods_per_year
    ) / mdd


def omega_ratio(
    returns: pd.Series,
    threshold: float = 0.0
) -> float:
    """Compute gains over losses relative to a threshold."""

    gains = returns[returns > threshold] - threshold
    losses = threshold - returns[returns < threshold]

    loss_sum = losses.sum()

    if loss_sum == 0:
        return np.nan

    return gains.sum() / loss_sum


def tail_ratio(returns: pd.Series) -> float:
    """
    Ratio of 95th percentile gain
    to 5th percentile loss magnitude.
    """

    upper = np.percentile(returns, 95)
    lower = abs(np.percentile(returns, 5))

    if lower == 0:
        return np.nan

    return upper / lower


def common_sense_ratio(returns: pd.Series) -> float:
    """
    Approximation used by pyfolio:
    tail_ratio * gain_to_pain_ratio
    """

    gain = returns[returns > 0].sum()
    pain = abs(returns[returns < 0].sum())

    if pain == 0:
        return np.nan

    gpr = gain / pain

    return tail_ratio(returns) * gpr


def value_at_risk(
    returns: pd.Series,
    cutoff: float = 0.05
) -> float:
    """Return historical value at risk at the requested cutoff."""

    return np.percentile(returns, cutoff * 100)


# ============================================================
# Rolling Metrics
# ============================================================

def rolling_volatility(
    returns: pd.Series,
    window: int = 10,
    periods_per_year: int = 252
) -> pd.Series:
    """Compute rolling annualized volatility."""

    return (
        returns.rolling(window)
        .std(ddof=1)
        * np.sqrt(periods_per_year)
    )


def rolling_sharpe(
    returns: pd.Series,
    window: int = 10,
    periods_per_year: int = 252
) -> pd.Series:
    """Compute rolling annualized Sharpe ratio."""

    mean = returns.rolling(window).mean()
    std = returns.rolling(window).std(ddof=1)

    return (
        mean / std
    ) * np.sqrt(periods_per_year)


# ============================================================
# Main Analyzer Class
# ============================================================

class PortfolioAnalytics:
    """Compute portfolio performance time series and summary metrics."""

    def __init__(
        self,
        metrics_df: pd.DataFrame,
        risk_free_rate: float = 0.0
    ):
        """Initialize analytics from a date/portfolio_value DataFrame."""

        self.metrics_df = metrics_df.copy()

        self.metrics_df["date"] = pd.to_datetime(
            self.metrics_df["date"]
        )

        self.metrics_df = (
            self.metrics_df
            .sort_values("date")
            .reset_index(drop=True)
        )

        self.equity = self.metrics_df["portfolio_value"]

        self.returns = to_returns(self.equity)

        self.periods_per_year = infer_periods_per_year(
            self.metrics_df["date"]
        )

        self.risk_free_rate = risk_free_rate

    # --------------------------------------------------------

    def compute(self):
        """Return rolling analytics outputs and one-row summary metrics."""

        returns = self.returns
        ppy = self.periods_per_year

        cumulative = cumulative_returns(returns)
        drawdown = drawdown_series(returns)

        outputs = pd.DataFrame({
            "date": self.metrics_df["date"].iloc[1:].values,
            "returns": returns.values,
            "cumulative_returns": cumulative.values,
            "drawdown": drawdown.values,
            "rolling_volatility": rolling_volatility(
                returns,
                10,
                ppy
            ).values,
            "rolling_sharpe": rolling_sharpe(
                returns,
                10,
                ppy
            ).values,
        })

        metrics = pd.DataFrame([{
            "CAGR": annual_return(returns, ppy),
            "Annual Return": annual_return(returns, ppy),
            "Annual Volatility": annual_volatility(returns, ppy),
            "Sharpe Ratio": sharpe_ratio(
                returns,
                self.risk_free_rate,
                ppy
            ),
            "Sortino Ratio": sortino_ratio(
                returns,
                0.0,
                ppy
            ),
            "Calmar Ratio": calmar_ratio(
                returns,
                ppy
            ),
            "Max Drawdown": max_drawdown(returns),
            "Omega Ratio": omega_ratio(returns),
            "Downside Risk": downside_risk(
                returns,
                0.0,
                ppy
            ),
            "Tail Ratio": tail_ratio(returns),
            "Common Sense Ratio": common_sense_ratio(returns),
            "Value at Risk": value_at_risk(returns),
            "Profit": (
                self.equity.iloc[-1]
                - self.equity.iloc[0]
            ),
        }])

        return outputs, metrics


# ============================================================
# Example Usage
# ============================================================

if __name__ == "__main__":

    # Example mock equity curve
    dates = pd.date_range(
        start="2024-01-01",
        periods=300,
        freq="D"
    )

    equity = 100000 * (
        1 + np.random.normal(
            0.0005,
            0.01,
            size=len(dates)
        )
    ).cumprod()

    metrics_df = pd.DataFrame({
        "date": dates,
        "portfolio_value": equity
    })

    analyzer = PortfolioAnalytics(metrics_df)

    outputs, metrics = analyzer.compute()

    print("\n===== METRICS =====")
    print(metrics)

    print("\n===== OUTPUTS =====")
    print(outputs.head())
