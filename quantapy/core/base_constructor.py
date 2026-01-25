#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun 22 09:40:07 2025

@author: andrewsimin
"""

"""
This is a base class to process multi-type construction
where each child class takes this constructor
"""

from abc import ABC, abstractmethod
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from pydantic import BaseModel,Field
from typing import List,Union,Type

class BaseConstructor(ABC):
    
    config_class: Type[BaseModel] = None

    def __init__(self, config: Union[BaseModel, dict, None] = None, **kwargs):
        self.payload = config if isinstance(config, dict) and "config_values" in config else None

        if self.config_class is None:
            raise NotImplementedError(f"{self.__class__.__name__} must define `config_class`.")
        
        if isinstance(config, self.config_class):
            final_config = config
        elif isinstance(config, dict):
            values = config["config_values"] if "config_values" in config else config
            final_config = self.config_class(**values)
        elif kwargs:
            final_config = self.config_class(**kwargs)
        else:
            final_config = self.config_class()

        self.config = final_config