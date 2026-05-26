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
import pandas as pd

from quantapy.modules.evaluation.portfolio import PortfolioAnalytics

@register_component(category="Evaluate", function="Portfolio", source="Internal")
class Portfolio(BaseSimulation):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def execute(self, metrics_df):

        analyzer = PortfolioAnalytics(metrics_df)

        outputs, metrics = analyzer.compute()

        return outputs, metrics

