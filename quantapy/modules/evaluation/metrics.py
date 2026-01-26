from quantapy.registry.component_registry import COMPONENT_REGISTRY
from quantapy.utils.loader import load_plugins_from_folder
from typing import get_args, get_origin, List, Union
import pandas as pd
import optuna
from quantapy.modules.evaluation.metrics import *


from abc import ABC, abstractmethod
import pandas as pd
from typing import List,Union,Type
from quantapy.core.base_simulation import BaseSimulation
from quantapy.registry.component_registry import register_component
import pyfolio as pf
import pandas as pd

@register_component(category="Evaluate", function="Portfolio", source="Internal")
class Portfolio(BaseSimulation):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def execute(self,metrics_df):
        
        #metrics_df = self.simulation_outputs
        
        #port = pd.DataFrame({'periods': self.data["date"].iloc[start:end], "equity": equity_series}).dropna()
        port = pd.DataFrame({'periods':metrics_df['date'],"equity":metrics_df['portfolio_value']})
        port = port['equity'].pct_change()
        # Extract drawdown series
        cumulative_returns = (1 + port).cumprod()
        previous_peaks = cumulative_returns.cummax()
        drawdown = (cumulative_returns - previous_peaks) / previous_peaks
        #metrics["drawdown"] = drawdown

        # Metrics
        
        CAGR = pf.timeseries.annual_return(port)
        sortino_ratio = pf.timeseries.sortino_ratio(port)
        calmar_ratio = pf.timeseries.calmar_ratio(port)
        sharpe_ratio = pf.timeseries.sharpe_ratio(port)
        max_drawdown = pf.timeseries.max_drawdown(port)
        
        annual_return = pf.timeseries.annual_return(port)
        annual_volatility = pf.timeseries.annual_volatility(port)
        omega_ratio = pf.timeseries.omega_ratio(port)
        downside_risk = pf.timeseries.downside_risk(port)
        #alpha, beta = pf.timeseries.alpha_beta(port)
        tail_ratio = pf.timeseries.tail_ratio(port)
        common_sense_ratio = pf.timeseries.common_sense_ratio(port)
        cum_returns = pf.timeseries.cum_returns(port)
        #gross_lev = pf.timeseries.gross_lev(port)
        value_at_risk = pf.timeseries.value_at_risk(port)
        rolling_volatility = pf.timeseries.rolling_volatility(port,rolling_vol_window=10)
        rolling_sharpe = pf.timeseries.rolling_sharpe(port,rolling_sharpe_window=10)
 
        outputs = pd.DataFrame({'time':metrics_df['date'],"equity":metrics_df['portfolio_value']})
        outputs["Cumulative Returns"] = cumulative_returns
        outputs["Drawdown"] = drawdown
        
        metrics = pd.DataFrame({"Sortino Ratio": [sortino_ratio],
                                "Calmar Ratio": [calmar_ratio],
                                "Sharpe Ratio": [sharpe_ratio],
                                "Profit": [metrics_df['portfolio_value'].iloc[-1] - metrics_df['portfolio_value'][0]]})
 
        #return {"Vector": {"Cumulative Returns": cumulative_returns,
        #                   "Drawdown": drawdown,
        #                   },
        #        "Scalar": {"Sortino Ratio": sortino_ratio,
        #                   "Calmar Ratio": calmar_ratio,
        #                   "Sharpe Ratio": sharpe_ratio,
        #                   "Profit": metrics_df['portfolio_value'].iloc[-1] - metrics_df['portfolio_value'][0]
        #                   }
        #        }
    
        return outputs, metrics

"""
def vector_metrics():
    
    pass

def scalar_metrics(metrics_df):
    
    #port = pd.DataFrame({'periods': self.data["date"].iloc[start:end], "equity": equity_series}).dropna()
    port = pd.DataFrame({'periods':metrics_df['date'],"equity":metrics_df['portfolio_value']})
    port = port['equity'].pct_change()
    # Extract drawdown series
    cumulative_returns = (1 + port).cumprod()
    previous_peaks = cumulative_returns.cummax()
    drawdown = (cumulative_returns - previous_peaks) / previous_peaks
    #metrics["drawdown"] = drawdown

    # Metrics
    
    CAGR = pf.timeseries.annual_return(port)
    sortino_ratio = pf.timeseries.sortino_ratio(port)
    calmar_ratio = pf.timeseries.calmar_ratio(port)
    sharpe_ratio = pf.timeseries.sharpe_ratio(port)
    max_drawdown = pf.timeseries.max_drawdown(port)
    
    annual_return = pf.timeseries.annual_return(port)
    annual_volatility = pf.timeseries.annual_volatility(port)
    omega_ratio = pf.timeseries.omega_ratio(port)
    downside_risk = pf.timeseries.downside_risk(port)
    #alpha, beta = pf.timeseries.alpha_beta(port)
    tail_ratio = pf.timeseries.tail_ratio(port)
    common_sense_ratio = pf.timeseries.common_sense_ratio(port)
    cum_returns = pf.timeseries.cum_returns(port)
    #gross_lev = pf.timeseries.gross_lev(port)
    value_at_risk = pf.timeseries.value_at_risk(port)
    rolling_volatility = pf.timeseries.rolling_volatility(port,rolling_vol_window=10)
    rolling_sharpe = pf.timeseries.rolling_sharpe(port,rolling_sharpe_window=10)
    
    return {"Cumulative Returns": cumulative_returns,
            "Drawdown": drawdown,
            "CAGR": CAGR,
            "Sortino Ratio": sortino_ratio,
            "Calmar Ratio": calmar_ratio,
            "Sharpe Ratio": sharpe_ratio,
            "Profit": metrics_df['portfolio_value'].iloc[-1] - metrics_df['portfolio_value'][0]
            }
"""
