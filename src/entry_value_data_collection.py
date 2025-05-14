from src.utils import round_to_0_05,get_options_data
import os,csv
import pandas as pd
from datetime import datetime
from config import entry_value_file_path,multi_option_data_file_path

class EntryValuesData:
    def __init__(self,smartApi, stock_name, qty,logger):
        self.smartApi = smartApi
        self.stock_name = stock_name.upper()
        self.qty = qty
        self.logger = logger

    def entry_values_data(self,future_price_data_dict):
        futures_symbol = future_price_data_dict['futures_symbol']
        futures_token = future_price_data_dict['futures_token']
        ltp_params = {"exchange": "NFO", "tradingsymbol": futures_symbol, "symboltoken": futures_token}
        ltp_data = self.smartApi.ltpData(**ltp_params)
        futures_price = ltp_data['data']['ltp'] if ltp_data.get('status') else None
    
        if futures_price is None:
            raise Exception("Failed to fetch futures LTP")
        future_price_data_dict['futures_price'] = futures_price
        options_data = get_options_data(self.smartApi,self.stock_name,future_price_data_dict) ## scrip master csv

        lot_size = options_data['lot_size']
        ce_symbol = options_data['ce_symbol']
        pe_symbol = options_data['pe_symbol']

        ce_high = self.get_max_high(ce_symbol, multi_option_data_file_path)
        pe_high = self.get_max_high(pe_symbol, multi_option_data_file_path)

        #CE 106.16475 PE 96.0395
        self.logger.write(f"Before calculation CE High value is {ce_symbol} --> {ce_high} and PE High value is {pe_symbol}--> {pe_high}")
        ce_entry_price = round_to_0_05(ce_high)
        pe_entry_price = round_to_0_05(pe_high)

        ce_entry_limit = round_to_0_05(ce_entry_price * 1.007)
        pe_entry_limit = round_to_0_05(pe_entry_price * 1.007)

        # Save entry data for future GTT logic
        self.save_entry_data({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ce_symbol": options_data['ce_symbol'],
            "ce_token": options_data['ce_token'],
            "pe_symbol": options_data['pe_symbol'],
            "pe_token": options_data['pe_token'],
            "ce_entry_price": ce_entry_price,
            "ce_entry_limit": ce_entry_limit,
            "pe_entry_price": pe_entry_price,
            "pe_entry_limit": pe_entry_limit,
            "ce_strike": options_data['ce_strike'],
            "pe_strike": options_data['pe_strike'],
            "expiry": options_data['expiry'],
            "lot_size": lot_size
        })

        # return data for sequential order
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ce_symbol": options_data['ce_symbol'],
            "ce_token": options_data['ce_token'],
            "pe_symbol": options_data['pe_symbol'],
            "pe_token": options_data['pe_token'],
            "ce_entry_price": ce_entry_price,
            "ce_entry_limit": ce_entry_limit,
            "pe_entry_price": pe_entry_price,
            "pe_entry_limit": pe_entry_limit,
            "ce_strike": options_data['ce_strike'],
            "pe_strike": options_data['pe_strike'],
            "expiry": options_data['expiry'],
            "lot_size": lot_size
        }

    def get_ltp(self, symbol, token):
        params = {
            "exchange": "NFO",
            "tradingsymbol": symbol,
            "symboltoken": token
        }
        data = self.smartApi.ltpData(**params)
        if not data.get('status'):
            raise Exception(f"LTP fetch failed for {symbol}")
        return data['data']['ltp']

    def save_entry_data(self, entry_data):

        with open(entry_value_file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=entry_data.keys())
            writer.writeheader()
            writer.writerow(entry_data)

        self.logger.write(f"📁 Entry data saved to {entry_value_file_path}")

    def get_max_high(self,symbol: str, filename: str) -> float:
        """
        Find maximum LTP value for a given symbol using Pandas.
        Returns float max_ltp if found, else None.
        """

        df = pd.read_csv(filename)

        if len(df)==0:
            self.logger.write(f"❌ ERROR: No rows found for symbol: {symbol} in {filename}")
            raise ValueError("---------There was no data in multi options file. Please Run the main.py file by enabling all parameters in flow control python file."
                             ".------------")

        # Filter rows matching the symbol
        filtered = df[df['symbol'] == symbol].copy()



        # Convert 'high' column to numeric safely
        filtered['high'] = pd.to_numeric(filtered['high'], errors='coerce')

        # Drop any invalid highs (NaN)
        filtered = filtered.dropna(subset=['high'])

        if filtered.empty:
            self.logger.write(f"❌ ERROR: No valid high values for {symbol} in {filename}")
            return None

        max_high = filtered['high'].max()

        return max_high
