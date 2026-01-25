from tradinglib.core.base_data import BaseData
from tradinglib.registry.component_registry import register_component
from tradinglib.core.base_component import BaseComponentConfig
import pandas as pd
from pydantic import BaseModel,Field
import numpy as np
from typing import List
from datetime import timedelta
import requests
from tradinglib.modules.calculator.transform import CustomDataFrame
import dateutil.relativedelta as rd
from datetime import datetime
from joblib import Parallel, delayed

@register_component(category="Market", function="OHLC", source="Internal")
class OHLC(BaseData):
    
    config = {
        "title": "OHLC",
        "type": "object",
        "properties": {
    
            "ticker": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "default": ["AAPL"],
                "description": "One or more stock ticker symbols",
                "widget_type": "multiselect",
                "advanced": False
            },
    
            "period": {
                "type": "string",
                "default": "5 days",
                "description": "Select one or more periods",
                "enum": [
                    "1 day",
                    "5 days",
                    "1 month",
                    "3 months",
                    "1 year"
                ],
                "widget_type": "select",
                "optimizable": [5, 100],
                "advanced": False
            },
    
            "interval": {
                "type": "string",
                "default": "1 hour",
                "description": "Select one or more intervals",
                "enum": [
                    "1 min",
                    "5 min",
                    "15 min",
                    "1 hour"
                ],
                "widget_type": "select",
                "advanced": False
            }
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = "your_api_key_here"
        self.synthesizable = True # if true data synthesizer acts on these values
        # any other setup
    
#    def __init__(self, config: FmpDataConfig):
        
#        super().__init__(config)
#        self.api_key = 'sNfN2hHaQDfQj5lsxdS93VLuAGXk8JRA'
#        self.config = config
    
    @staticmethod
    def get_jsonparsed_data(url):
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch data from {self.url}")
            return None
        
    #def fetch_historical_data(self,ticker,period=None,interval=None,start=None,end=None):
    def fetch_historical_data(self, ticker, interval, period, start=None, end=None) -> pd.DataFrame:
        
        df = None
        
        print(f"Period: {period}")
        print(f"Interval: {interval}")
        
#        "1 min", "5 min", "15 min", "30 min", "1 hour", "4 hour", "1 day"

        if interval:
            if interval == "1 min":
                batch = 2 #3
            elif interval == "5 min":
                batch = 5 #10
            elif interval == "15 min":
                batch = 30 #45
            elif interval == "30 min":
                batch = 15 #30
            elif interval == "1 hour":
                batch = 60 #90
            elif interval == "4 hour":
                batch = 120 #180
            elif interval == "1 day":
                batch = 1500 #1825
            else:
                raise ValueError(f"Unrecognized interval: {interval}")
                
        # If period is defined, convert to start and end date
        
        if period:
       
            end_date = datetime.now()
            
            if period == "1 day":
                start_date = end_date - timedelta(days=1)
            elif period == "5 days":
                start_date = end_date - timedelta(days=5)
            elif period == "1 month":
                start_date = end_date - rd.relativedelta(months=1)
            elif period == "3 months":
                start_date = end_date - rd.relativedelta(months=3)
            elif period == "6 months":
                start_date = end_date - rd.relativedelta(months=6)
            elif period == "1 year":
                start_date = end_date - rd.relativedelta(years=1)
            elif period == "2 years":
                start_date = end_date - rd.relativedelta(years=2)
            elif period == "5 years":
                start_date = end_date - rd.relativedelta(years=5)
            else:
                raise ValueError(f"Unrecognized time frame: {period}")
                
            input_format = "%Y-%m-%d"
            # Convert the string to a datetime object
            start_date = start_date.date()
            end_date = end_date.date()
                
        else:
            
            # Define the format of the input string
            input_format = "%Y-%m-%d"
            # Convert the string to a datetime object
            start_date = datetime.strptime(start, input_format)
            end_date = datetime.strptime(end, input_format)
        
        interval = interval.replace(" ", "")
        #print(self.interval)
        
        base_url = 'https://financialmodelingprep.com/api/v3/historical-chart/'
        api_key = 'sNfN2hHaQDfQj5lsxdS93VLuAGXk8JRA'
            
        data_frames = []

        date_ranges = pd.date_range(start=start_date, end=end_date, freq=f'{batch}D')
        
        #print(self.start_date,self.end_date,date_ranges)
        
        delta = end_date - start_date

        # Get the number of days between start and end
        nod = delta.days
        
        #print(nod, self.batch)
        
        if nod >= batch:

            for i in range(len(date_ranges) - 1):
                batch_start = date_ranges[i].strftime('%Y-%m-%d')
                
                if i > 0:
                    batch_start = (date_ranges[i] + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
                batch_end = date_ranges[i + 1].strftime('%Y-%m-%d')
    
                url = f'{base_url}{interval}/{ticker}?from={batch_start}&to={batch_end}&apikey={api_key}'
                print(url)
                #print(self.url)
                data = self.get_jsonparsed_data(url)
    
                if data is not None:
                    df = pd.DataFrame(data)
                    data_frames.append(df)
    
            if data_frames:
                df = pd.concat(data_frames, ignore_index=True)
                df = df.sort_values(by='date')
                df = df.reset_index(drop=True)
              
            else:
                
                return None
            
        else:
            
            url = f'{base_url}{interval}/{ticker}?from={start_date}&to={end_date}&apikey={api_key}'
            print(url)
            data = self.get_jsonparsed_data(url)

            if data is not None:
                df = pd.DataFrame(data)
                print(df)
                df = df.sort_values(by='date')
                #print(df)
                
        #self.data = df
        data = CustomDataFrame(df)
        
        return data
        #return self.get_jsonparsed_data()
        
    def _fetch_one(self, asset):
        return asset, [self.fetch_historical_data(
            ticker=asset,
            interval=self.params["interval"],
            period=self.params["period"],
            start=None,
            end=None,
        )]

    def execute(self, n_jobs=-1):
        results = Parallel(
            n_jobs=n_jobs,
            backend="threading",
            prefer="threads",
        )(
            delayed(self._fetch_one)(asset)
            for asset in self.params["ticker"]
        )

        self.data = dict(results)
        return self.data
        

    



