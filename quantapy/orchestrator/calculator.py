#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun May 25 10:00:15 2025

@author: andrewsimin
"""

# Data and Calulator are passed to strategy since they can be seperate from the
# from the strategy pipeline likeall other stock software

# Calculator is a non extendable component and is primarily for managing 
# multiple transformation components which are extendable

from tradinglib.registry.component_registry import COMPONENT_REGISTRY
from tradinglib.utils.loader import load_plugins_from_folder
from pydantic import BaseModel
from typing import get_args, get_origin, List, Union
#from tradinglib.gui.pydantic_form import single_model, list_of_models
import pandas as pd
import streamlit as st
import json
import datetime
import math
from joblib import Parallel, delayed

#import calculator

class Calculator():
    
    def __init__(self):
        
        """
        self.transforms is a list of transformation objects
        """
        
        self.synthetic_obj = None
        self.transformed_data = None
        self.transform_outputs = [] # store a list of output names so they can be options
        self.transforms = {}
        self.start = 0
        self.end = -1
        
        self.overlay_names = []
        self.indicator_names = []
        
    def add_transform(self, registered: str, function: str, source: str = "Internal", config: Union[BaseModel, None] = None, **kwargs):
        
        """Class to add transformations to raw input data. This operates on every raw dataframe in the datawarehouse (original and synthetic)"""
        
        # Get the class from the registry
        transform_class = COMPONENT_REGISTRY[registered][function][source]
        data_s_instance = transform_class(config=config, **kwargs)
        print("PRINTING CALC CONFIG")
        print(data_s_instance.params)
    
        self.transforms[f"{data_s_instance.params['name']}"] = data_s_instance
        
    def save(self):
        
        self.state = []
        
        for key, value in self.transforms.items():
            self.state.append(value.payload)
        
        with open("calculator.json", "w") as f:
            json.dump(self.state, f, indent=2)
            
    def load(self):
        with open("calculator.json", "r") as f:
            loaded = json.load(f)
            
        for config in loaded:
            # Need a way to store this in config but explicitely defineing them for now
            transform_class = COMPONENT_REGISTRY["Technical"][config["type"]]["Internal"]
            data_s_instance = transform_class(config=config)
            self.transforms[f"{data_s_instance.config.name}"] = data_s_instance
            
        self.apply_transformations()
        
    def remove(self,operation):
        
        del self.transforms[operation]
        print(f"Transforms From Remove: {self.transforms}")
        
    def update(self, name: str, **new_params):
        
        if name not in self.transforms:
            raise ValueError(f"No transform named '{name}' found.")
            
        print("What a Mess")
        print(self.transforms[name].params)
        
        old_transform = self.transforms[name]
        config_dict = old_transform.params
        config_dict.update(new_params)
        
        # Reconstruct the transform using original registry keys
        transform_class = type(old_transform)
        print(transform_class)
        new_instance = transform_class(config=config_dict)
        
        #st.write(self.transforms["RSI"])
        self.transforms[name] = new_instance
        print(self.transforms[name].params)
        #st.write(self.transforms["RSI"])
        
    def set_data(self,data):
        
        self.input_data = data
        self.transformed_data = data
        self.apply_transformations()
        
    def _apply_transformations_one(self,transforms,input_data,start,end):
    
        
        print(f"Transforms from Apply Transformations {self.transforms}")
        
        transformed_data = input_data
        transform_outputs = []
        
        # pass transforms 
        for _,transform in transforms.items():
            
            # Compute the output of each transform
            result = transform.compute(input_data)
            
            for i, (key, value) in enumerate(result.items()):
                transformed_data[key] = value
                transform_outputs.append(key)
            
        transformed_data["date"] = pd.to_datetime(transformed_data["date"])
        transformed_data = transformed_data.sort_values("date").iloc[start:end].reset_index(drop=True)

        return transformed_data
    
    def apply_transformations_(self,input_data_dict,n_jobs=-1):
        
        self.transformed_data = {}
        
        for dataset_type, dataset in input_data_dict["OHLC"].items():
            
            print(dataset_type)
            
            self.transformed_data[dataset_type] = {}
            
            for asset, data in dataset.items():
        
                results = Parallel(
                    n_jobs=n_jobs,
                    backend="loky",
                )(
                    delayed(self._apply_transformations_one)(self.transforms,trajectory,self.start,self.end)
                    for trajectory in data
                )
                    
                self.transformed_data[dataset_type][asset] = results
                
        return self.transformed_data
                    
                    
                
                

        #self.data = dict(results)
        #return self.data
        #return results
    
       
    def apply_transformations(self,input_data):
        
        # We have a huge problem with inconsistency of transformed data, copies 
        # Needed to hack the .iloc locations. 
        # THIS MUST BE FIXED
        # Temporarily fixed ... I think 08/02/2025
        
        self.overlays = {}
        self.indicators = {}
        
        self.transformed_data = self.input_data.copy()
        
        print(f"Transforms from Apply Transformations {self.transforms}")
        for _,transform in self.transforms.items():
            
            # Compute the output of each transform
            result = transform.compute(self.transformed_data)

            for i, (key, value) in enumerate(result.items()):
                self.transformed_data[key] = value
                self.transform_outputs.append(key)
                if transform.params['display'] == "Overlay":
                    import math
                    df = self.transformed_data[["date", key]].rename(columns={"date": "time", key: "value"}).iloc[self.start:self.end]
                    
                    # Convert NaN/inf to None
                    def sanitize_value(x):
                        if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
                            return None
                        return x
                    
                    records = [{"time": row["time"], "value": sanitize_value(row["value"])} for row in df.to_dict(orient="records")]
                    
                    print("WTF is Going On")
                    print(records)
                    self.overlays[key] = records
                    #self.overlays[key] = json.loads(self.transformed_data[["date",key]].rename(columns={"date": "time", key: "value"}).to_json(orient='records'))
                elif transform.params['display'] == "Indicator":
                    import math
                    df = self.transformed_data[["date", key]].rename(columns={"date": "time", key: "value"}).iloc[self.start:self.end]
                    
                    # Convert NaN/inf to None
                    def sanitize_value(x):
                        if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
                            return None
                        return x
                    
                    records = [{"time": row["time"], "value": sanitize_value(row["value"])} for row in df.to_dict(orient="records")]
                    
                    print(records)
                    self.indicators[key] = records
                    
        
        # CLEAN OVERLAYS AND INDICATORS
        cleaned_overlays = {}

        for key, series in self.overlays.items():
            cleaned_series = []
        
            for point in series:
                value = point.get("value")
        
                # Skip invalid values
                if value is None or (
                    isinstance(value, float) and (math.isnan(value) or math.isinf(value))
                ):
                    continue
        
                # 🔒 Canonical time normalization
                try:
                    ts = (
                        pd.to_datetime(point.get("time"), utc=True, errors="coerce")
                        .value // 10**9
                    )
                except Exception:
                    continue
        
                if pd.isna(ts):
                    continue
        
                cleaned_series.append(
                    {
                        "time": int(ts),   # UNIX seconds (guaranteed)
                        "value": value,
                    }
                )
        
            cleaned_overlays[key] = cleaned_series
            
        cleaned_indicators = {}

        for key, series in self.indicators.items():
            cleaned_series = []
        
            for point in series:
                value = point.get("value")
        
                # Skip invalid values
                if value is None or (
                    isinstance(value, float) and (math.isnan(value) or math.isinf(value))
                ):
                    continue
        
                # 🔒 Canonical time normalization
                try:
                    ts = (
                        pd.to_datetime(point.get("time"), utc=True, errors="coerce")
                        .value // 10**9
                    )
                except Exception:
                    continue
        
                if pd.isna(ts):
                    continue
        
                cleaned_series.append(
                    {
                        "time": int(ts),   # UNIX seconds (guaranteed)
                        "value": value,
                    }
                )
        
            cleaned_indicators[key] = cleaned_series
                
        #print("$$$$$$$$$$$$$")
        #print(self.overlays)
        self.overlays = cleaned_overlays
        self.indicators = cleaned_indicators
        
                
        # I think we need to fix the dataframe ordering
        
        self.transformed_data["date"] = pd.to_datetime(self.transformed_data["date"])
        self.transformed_data = self.transformed_data.sort_values("date").iloc[self.start:self.end].reset_index(drop=True)
        print("FROM CALCULATOR",file=open("folds.txt","a"))
        print(self.start,self.end,file=open("folds.txt","a"))
        print(self.transformed_data,file=open("folds.txt","a"))
        
        self.original_transformed_data = self.transformed_data.copy().iloc[self.start:self.end]
        
        #self.update_json_schema_options()
    
        return self.transformed_data.iloc[self.start:self.end]
    
    def index_data(self,start,end):
        
        self.start = start
        self.end = end
        print(f"Start Set to {self.start}",file=open("folds.txt","a"))
        print(f"End Set to {self.end}",file=open("folds.txt","a"))

        #self.indexed_data = self.original_transformed_data.iloc[self.start:self.end]
        #self.transformed_data = self.indexed_data.reset_index(drop=True)
        
        #return self.indexed_data
    
    def sample_data(self,samples):
        
        self.sampled_data = self.transformed_data.iloc[samples]
        
        return self.sampled_data
    
    def update_json_schema_options(self):
        # Example: update all transforms that have a "real" field to reflect current columns
        current_columns = self.transformed_data.columns.tolist()
        
        for transform in self.transforms.values():
            config_class = type(transform.config)
            if "real" in config_class.model_fields:
                field_info = config_class.model_fields["real"]
                extras = field_info.json_schema_extra or {}
                extras["options"] = current_columns
                field_info.json_schema_extra = extras
                
        
        
        
        
    
    
        
        
            
    
