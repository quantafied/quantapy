from tradinglib.registry.component_registry import COMPONENT_REGISTRY
from tradinglib.utils.loader import load_plugins_from_folder
from pydantic import BaseModel
from typing import get_args, get_origin, List, Union
#from tradinglib.gui.pydantic_form import single_model, list_of_models
import pandas as pd

#import calculator

class Data():
    
    def __init__(self):
        
        self.data_objects = {}
        self.synthetic_data_objects = {}
        self.data = {}
        
    def add(self, category: str, name: str, source: str, config: Union[BaseModel, None] = None, **kwargs):
        
        # Get the class from the registry
        transform_class = COMPONENT_REGISTRY[category][name][source]
        print(transform_class)
        data_s_instance = transform_class(config=config, **kwargs)
    
        self.data_objects[name] = data_s_instance
        
    def add_synthetic(self, category: str, name: str, source: str, config: Union[BaseModel, None] = None, **kwargs):
        
        # Get the class from the registry
        transform_class = COMPONENT_REGISTRY[category][name][source]
        print(transform_class)
        data_s_instance = transform_class(config=config, **kwargs)
    
        self.synthetic_data_objects[name] = data_s_instance
        
    def fetch_data(self):
        
        # Fetch raw data
        for data_type, data_object in self.data_objects.items():
            
            self.data[data_type] = {}
            # Compute the output of each transform
            raw_data = data_object.execute()
            self.data[data_type]["Raw"] = raw_data
            if data_object.synthesizable:
                for synthetic_type, synthetic_object in self.synthetic_data_objects.items():
                    noisy = synthetic_object.execute(raw_data)
                    self.data[data_type][synthetic_type] = noisy
            
        return self.data