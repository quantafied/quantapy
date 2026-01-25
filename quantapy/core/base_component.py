#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun May 18 22:35:20 2025

@author: andrewsimin
"""

from pydantic import BaseModel,Field
from typing import Dict, Tuple

class BaseComponentConfig(BaseModel):

    """Shared config interface for all user-extensible modules."""
    
    #optimizations: Dict[str, Tuple[int, int]] = Field(default_factory=dict, exclude=True)
    
    pass
