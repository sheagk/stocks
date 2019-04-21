#!/usr/bin/env python3

# idea -- given weekly/daily activity, sector, and maybe some other stuff, 
# predict growth over the next year (i.e. exactly 1 year in the future)
# then do it again for 1 day in the future.

import os
import re
import time
import tqdm
import urllib.request
import pandas as pd
import numpy as np
from copy import deepcopy

datatype = 'csv'

root_dir = os.path.expanduser('~')+'/projects/stocks/'
stock_dir = root_dir + '/symbols/'
master_fname = root_dir + 'reduced_data.csv'

symbol_fname = lambda symbol:  stock_dir+symbol+'.'+datatype

# api key for alphavantage should be stored as in a non-checked-in text file 
with open(root_dir+'alpha_api_key') as f:
    apikey = f.readline().strip()

def load_symbols_in_one_exchange(exchange, df=None):
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

    # store the exchange:
    this_df['Exchange'] = exchange

    # replace NaNs in the sectors...
    this_df['Sector'] = this_df['Sector'].apply(lambda x:  x if pd.notnull(x) else 'Unknown')

    unnamed_keys = [k for k in this_df.keys() if k.startswith('Unnamed')]
    for k in unnamed_keys:
        if np.isfinite(this_df[k]).any():
            raise IOError("Got an unnamed column with data")
        else:
            this_df = this_df.drop(columns=k)

    # may need to alter symbol depending on the exchange, since there can be dupes...
    # don't seem to be running across this problem though

    if df is None:
        return this_df
    else:
        return df.append(this_df, ignore_index=True)


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
    """
    extract what I want the model to predict.  returns a series 

    I want to predict the fractional change over some next time...one week I guess
    """

    pass



def download_symbol(symbol, function='TIME_SERIES_WEEKLY_ADJUSTED'):
    """
    save historical data for a stock symbol to a local file
    """
    url = ('https://www.alphavantage.co/query?function={}&symbol={}&apikey={}&datatype={}'.format(
            function, symbol, apikey, datatype))

    urllib.request.urlretrieve(url, symbol_fname(symbol))  


def load_symbol_data(symbol, symbol_list, df=None):
    """
    add the information for a single symbol to an overarching dataframe
    
    so basically, at the end, i want a column for each date and a row for
    each symbol.  i also want some extra information in the dataframe, 
    such as the sector, and time series data that should all be stationary:

    -- change in volume
    -- fractional change in volume

    -- change in adjusted close
    -- fractional change in adjusted close

    -- change in adjusted high 
    -- fractional change in adjusted high

    -- difference between high and low in a given time period    
    """

    # get the sector, market cap, exchange, and industry from the symbol_list
    symbol_row = symbol_list.loc[symbol_list['Symbol'] == symbol]

    # load the information for a single symbol and index it by the date
    date_column_name = 'timestamp'
    input_df = pd.read_csv(symbol_fname(symbol), 
        parse_dates=[date_column_name], index_col=date_column_name)

    # get the total change in each column over a 1 week period
    change_df = input_df - input_df.shift()
    
    # create a new dataframe to store the output numbers we care about
    output_df = pd.DataFrame()
    output_df['timestamp'] = input_df.index
    output_df.set_index('timestamp', inplace=True)
    
    # store the metadata -- only going to be useful when I stack a bunch 
    # of them together, which I'm not up to yet, but let's be forward 
    # thinking and include them now
    for key in ['Sector', 'MarketCap', 'Industry', 'Symbol']:
        output_df[key] = symbol_row[key].item()

    output_df['high-low'] = input_df['high'] - input_df['low']
    for key in ['adjusted close', 'high', 'volume']:
        output_df['delta_'+key] = change_df[key]
        output_df['fractional_delta_'+key] = (
            output_df['delta_'+key] / input_df[key])

    output_df.dropna(inplace=True)
    
    if df is None:
        return output_df
    else:
        return df.append(output)


def load_full_symbol_list(reorder=True):
    """
    load, sanitize, and (optionally) reorder the full list of symbols
    """
    symbol_list = None
    for exchange in ['nasdaq', 'amex', 'nyse']:
        symbol_list = load_symbols_in_one_exchange(exchange, symbol_list)

    if reorder:
        # randomly re-order the list:
        symbol_list = symbol_list.reindex(np.random.permutation(symbol_list.index))

    # drop the first instance of the 12 symbols that are listed in two exchanges
    symbol_list.drop_duplicates('Symbol', inplace=True)

    # select symbols that are not "preferred stocks", 
    # since I can't figure out how to grab those via alphavantage's API
    symbol_list = symbol_list.loc[symbol_list['Symbol'].map(lambda x:  '^' not in x)]

    # clean up any white space, cause that shouldn't exist in any of them
    symbol_list['Symbol'] = symbol_list['Symbol'].apply(lambda x: x.strip())

    return symbol_list


def download_all_symbols():
    symbol_list = load_full_symbol_list()

    # now start downloading the data:
    for symbol in tqdm.tqdm(symbol_list['Symbol']):
        if not os.path.isfile(symbol_fname(symbol)):
            download_symbol(symbol)

            with open(symbol_fname(symbol), 'r') as f:
                if f.readline()[0] == '{':  #downloading as CSV, so this only happens if we go too fast
                    print("Looks like we failed to download {}".format(symbol))
                    print("Will remove then take a short break before continuing; rerun later to fix")
                    os.remove(symbol_fname(symbol))
                    time.sleep(20)

            # rate limit the downloads to 500 per day:
            time.sleep(24*60*60/500)


def load_all_symbols_performance():
    pass



