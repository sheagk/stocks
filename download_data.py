#!/usr/bin/env python3

# idea -- given weekly/daily activity, sector, and maybe some other stuff, 
# predict growth over the next year (i.e. exactly 1 year in the future)
# then do it again for 1 day in the future.

import os
import re
import urllib.request
import pandas as pd
import numpy as np

datatype = 'csv'

root_dir = os.path.expanduser('~')+'/stocks/'
stock_dir = root_dir + '/symbols/'
master_fname = root_dir + 'reduced_data.csv'

symbol_fname = lambda symbol:  stock_dir+symbol+datatype

# api key for alpha should be stored as in a non-checked-in text file 
with open(root_dir+'alpha_api_key') as f:
    apikey = f.readline()

def load_symbols(exchange, df=None, sector_to_index_lookup=None):
    assert exchange in ['nasdaq', 'amex', 'nyse']
    this_df = pd.read_csv(root_dir+'companylist_{}.csv'.format(exchange))

    #now sanitize the data...
    if exchange == 'nasdaq':
        this_df = this_df.drop(columns='ADR TSO')

    else:
        # have to convert the market cap into a number
        this_df['MarketCap'] = this_df['MarketCap'].apply(lambda x:
            float(x.replace('M', 'e6').replace('B', 'e9').strip('$')) if pd.notnull(x)
            else np.nan)

        # also have to capitalize industry column name
        this_df = this_df.rename({'industry':'Industry'}, axis='columns')

    # replace NaNs in the sectors...
    this_df['Sector'] = this_df['Sector'].apply(lambda x:  x if pd.notnull(x) else 'Unknown')

    unnamed_keys = [k for k in this_df.keys() if k.startswith('Unnamed')]
    for k in unnamed_keys:
        if np.isfinite(this_df[k]).any():
            raise IOError("Got an unnamed column with data")
        else:
            this_df = this_df.drop(columns=k)

    # may need to alter symbol depending on the exchange, since there can be dupes...

    if df is None:
        return this_df
    else:
        return df.append(this_df)


def extract_training_data(df, ending_dates):
    """
    ok, the input df should have the time series as well as the info in the symbols list,
    and this will return a dataframe that has the stuff I want to train on 

    now....what to train on. definitely sector (one hot encoded), log10 market cap,
    fractional month-to-month deviations over the past N years (probably just a list 
    of the differences),  
    """
    training_df = pd.DataFrame()

    # market cap is easy
    training_df['log_market_cap'] = np.log10(df['MarketCap'])
    
    # use one-hot encoding to do the sector
    # first clean up to try to minimize duplicates
    # -- make all lowercase and replace non-alphanumeric with _
    clean_sector = df['Sector'].apply(lambda x:  
        re.sub('[^0-9a-zA-Z]+', '_', x.lower()))

    encoded_sector = pd.get_dummies(clean_sector)
    for sector in encoded_sector:
        training_df[sector] = encoded_sector[sector]

    for date in ending_dates:
        pass


    
    return training_df    

def extract_targets(df, ending_dates):




def download_symbol(symbol, function='TIME_SERIES_WEEKLY_ADJUSTED'):
    """
    save historical data for a stock symbol to a local file
    """
    url = 'https://www.alphavantage.co/query?'
          'function={}&symbol={}}&apikey={}}&datatype={}'.format(
            function, symbol, apikey, datatype)

    urllib.request.urlretrieve(url, symbol_fname(symbol))  


def add_symbol_to_dataframe(df, symbol):
    """
    add the information for a single symbol to an overarching dataframe
    
    so basically, at the end, i want a column for each date and a row for
    each symbol.  i also want some extra information in the dataframe, 
    such as the sector, and umm....other stuff.  those can (i think) be
    extra rows that aren't 
    """

    this_df = df.read_csv(symbol_fname(symbol))


def __main__():
    symbol_list = None
    for exchange in ['nasdaq', 'amex', 'nyse']:
        symbol_list = load_symbols(exchange, symbol_list)

    # randomly re-order the symbols:
    symbol_list = symbol_list.reindex(np.random.permutation(symbol_list.index))


