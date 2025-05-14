import os
import shutil
import requests
from datetime import datetime, timedelta
from config import *
# Removed redundant import: import requests
import json
from colorama import Fore, Style, init
import csv
import os  # Note: 'os' is also imported twice
import time

class ScripMasterManager:
    def __init__(self,stock_name,logger):
        self.api_url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        self.today = datetime.now()
        self.stock_name = stock_name.upper()
        self.logger=logger

    def prepare_folders(self):
        """
        Create data/current and data/backup folders if missing.
        """
        os.makedirs(CURRENT_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def download_scripmaster(self):
        self.logger.write("⬇️  Downloading latest ScripMaster...")

        response = requests.get(self.api_url)
        if response.status_code == 200:
            data = response.json()
            import pandas as pd
            # Filter out BSE data
            all_data = [contract for contract in data if contract.get('exch_seg') not in (
                'BSE', 'NCS', 'CDS', 'MCX', 'BFO', 'MCXFO', 'BFOFO', 'NCDEX', 'NCO')]
            all_data = [contract for contract in all_data if contract.get('instrumenttype') in ('FUTIDX','FUTSTK','OPTIDX','OPTSTK')]
            all_data = [contract for contract in all_data if contract.get('symbol').startswith(self.stock_name)]
            df = pd.DataFrame(all_data)
            df.to_csv(scripmaster_csv_file_path, index=False)
            self.logger.write(f"✅ ScripMaster downloaded and saved to {scripmaster_csv_file_path}")
        else:
            raise Exception("Failed to download ScripMaster file.Please re-run the workflow again")

    def setup_scripmaster(self):
        """
        Full Setup: create folders → backup old file → download new file
        """
        self.prepare_folders()
        self.download_scripmaster()
    
    def expiry_dates_check_and_return(self,future_data_df):
        today = datetime.now()
        current_month = today.strftime('%b').upper()
        next_month = (today.replace(day=28) + timedelta(days=4)).strftime('%b').upper()  # Safely next month
        TODAY = today.strftime('%d%b%y').upper()
        for idx, row in future_data_df.iterrows():
            expiry_date = row['expiry']
            expiry_raw = expiry_date.strftime('%d%b%y').upper()
            symbol = row['symbol']
            token = int(row['token'])
            expiry_month = expiry_date.strftime('%b').upper()
            today_minus1 = (expiry_date - timedelta(days=1)).strftime('%d%b%y').upper()

            # Case 1: Current Month Contract
            if expiry_month == current_month:
                if expiry_raw == TODAY or expiry_raw == today_minus1:
                    self.logger.write(f"⚠ Skipping current month future expiring today/tomorrow: {symbol}")
                    continue
                else:
                    self.logger.write(f"✅ Picked current month valid future: {symbol}")
                    return symbol, token, expiry_raw

        # Now check Next Month if current month not valid
        for idx, row in future_data_df.iterrows():
            expiry_date = row['expiry']
            expiry_raw = expiry_date.strftime('%d%b%y').upper()
            symbol = row['symbol']
            token = int(row['token'])
            expiry_month = expiry_date.strftime('%b').upper()

            if expiry_month == next_month:
                self.logger.write(f"✅ Picked next month future: {symbol}")
                return symbol, token, expiry_raw

        raise Exception(f"No valid future contract found. Please verify the scrip master file. after verifying please re-run the main.py by enabling all the parameters in flow control file")


    def get_scrip_master_data_and_along_with_future_price(self,smartApi,stock_name,):

        import pandas as pd
        import numpy as np

        scrip_master_data_df = pd.read_csv(scripmaster_csv_file_path)
        future_data_df = scrip_master_data_df[(scrip_master_data_df['exch_seg'] == 'NFO') & (scrip_master_data_df['instrumenttype'].str.contains('FUT'))]
        future_data_df = future_data_df[future_data_df['name'] == stock_name]

        if future_data_df.empty:
            raise Exception(f"No futures stock found for {stock_name}. please verify in scrip master file and re-run the main.py by enabling all the parameters in flow control file")

        # Pick nearest expiry
        future_data_df['expiry'] = pd.to_datetime(future_data_df['expiry'], format='%d%b%Y')
        future_data_df = future_data_df[future_data_df['expiry'] > self.today]
        future_data_df = future_data_df.sort_values('expiry')
        #nearest_expiry = future_data_df['expiry'].iloc[0].strftime('%d%b%y').upper()
        
        futures_symbol, futures_token, nearest_expiry = self.expiry_dates_check_and_return(future_data_df)
        
        # Get futures symbol
        futures_row = future_data_df.iloc[0]
        #futures_symbol = futures_row['symbol']
        #futures_token = int(futures_row['token'])
        lot_size = int(futures_row['lotsize'])

        # Get LTP of futures
        ltp_params = {"exchange": "NFO", "tradingsymbol": futures_symbol, "symboltoken": futures_token}
        ltp_data = smartApi.ltpData(**ltp_params)
        futures_price = ltp_data['data']['ltp'] if ltp_data.get('status') else None
    
        if futures_price is None:
            raise Exception("Failed to fetch futures LTP.Please verify in scrip master file and re-run the main.py by enabling all the parameters in flow control file")

        # Strike Gap
        option_data_df = scrip_master_data_df[(scrip_master_data_df['exch_seg'] == 'NFO') & (scrip_master_data_df['instrumenttype'].str.contains('OPT'))]
        option_data_df = option_data_df[option_data_df['name'] == stock_name]
        option_data_df['strike'] = pd.to_numeric(option_data_df['strike'], errors='coerce') // 100
        strikes = option_data_df['strike'].dropna().unique()
        strikes.sort()
        strike_gap = int(np.min(np.diff(strikes)))

        return {
            'futures_price':futures_price,
            'strike_gap':strike_gap,
            'lot_size':lot_size,
            'expiry':nearest_expiry,
            'futures_symbol':futures_symbol,
            'futures_token':futures_token
        }


