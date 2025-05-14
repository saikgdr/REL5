import csv
import shutil,pytz,time
from datetime import datetime
from config import *
from src.symbol_token import SymbolTokenManager
from src.utils import get_ist_now,get_target_time,get_options_data,fetch_high, fetch_ltp


class OptionsDataManager:
    def __init__(self, smartApi, stock_name,logger):
        self.smartApi = smartApi
        self.stock_name = stock_name.upper()
        self.csv_file = scripmaster_csv_file_path
        self.today = datetime.now()
        self.logger = logger

    # Previous get_options_data() method remains here...

    def fetch_multi_options_data(self,future_price_data_dict):
        """
        Fetch 5 CE + 5 PE strikes around ATM and save LTP data continuously.
        """

        options_data = get_options_data(self.smartApi,self.stock_name,future_price_data_dict)

        ce_strike = options_data['ce_strike']
        pe_strike = options_data['pe_strike']
        expiry = options_data['expiry']

        self.logger.write(f"CE Strike: {ce_strike}, PE Strike: {pe_strike}, Expiry: {expiry}")

        # Create strike lists
        ce_strike_list = self.generate_strike_list(ce_strike, 3,future_price_data_dict['strike_gap'])
        pe_strike_list = self.generate_strike_list(pe_strike, 3,future_price_data_dict['strike_gap'])

        self.logger.write(f"CE Strike List: {ce_strike_list}")
        self.logger.write(f"PE Strike List: {pe_strike_list}")

        # Fetch corresponding symbols & tokens
        ce_symbol_token_list = self.get_symbols_and_tokens(expiry, ce_strike_list, "CE")
        pe_symbol_token_list = self.get_symbols_and_tokens(expiry, pe_strike_list, "PE")
        self.logger.write(f"CE Symbol-Token List: {ce_symbol_token_list}")
        self.logger.write(f"PE Symbol-Token List: {pe_symbol_token_list}")

        import pandas as pd

        # Prepare to collect data
        collected_data = []

        # Start time control
        ist = pytz.timezone('Asia/Kolkata')
        end_time = datetime.now(ist).replace(hour=multi_option_fetch_data_hr, minute=multi_option_fetch_data_min,
                                             second=multi_option_fetch_data_sec, microsecond=0)

        self.logger.write(f"⏳ Collecting mutltiple options ltp data until {end_time} IST...")

        while True:
            now = datetime.now(ist)
            if now >= end_time:
                self.logger.write("✅ Time reached. Stopping data collection.")
                break

            # Fetch LTPs and collect data in a list
            for (ce_symbol, ce_token), (pe_symbol, pe_token) in zip(ce_symbol_token_list, pe_symbol_token_list):
                ce_high = fetch_ltp(self.smartApi, ce_symbol, ce_token,self.logger)
                pe_high = fetch_ltp(self.smartApi, pe_symbol, pe_token,self.logger)

                if ce_high is not None:
                    collected_data.append({'symbol': ce_symbol, 'token': ce_token, 'high': ce_high})
                if pe_high is not None:
                    collected_data.append({'symbol': pe_symbol, 'token': pe_token, 'high': pe_high})

            # self.logger.write(f"{ce_symbol} => {ce_high} | {pe_symbol} => {pe_high}")

            time.sleep(2)

        # Write all collected data to CSV at once using pandas
        df = pd.DataFrame(collected_data,columns=['symbol', 'token', 'high'])
        df.to_csv(multi_option_data_file_path, index=False, columns=['symbol', 'token', 'high'])

        self.logger.write("✅ Fetching of ltp for multiple options completed successfully")

    def get_multi_option_data_collection(self, hours, minutes, seconds, future_price_data_dict):
        """
        Wait till specific time, then start fetch_multi_options_data.
        """
        target = get_target_time(hours, minutes, seconds)

        while True:
            now = get_ist_now()
            remaining = target - now
            if remaining.total_seconds() <= 0:
                self.logger.write("⏰ Target time reached! Fetching multi-option data...")
                self.fetch_multi_options_data(future_price_data_dict)
                break
            else:
                print(f"Time remaining: {str(remaining).split('.')[0]}", end='\r', flush=True)
            time.sleep(1)

    # Helper functions
    def generate_strike_list(self, base_strike, count,strike_gap):
        return [base_strike + i * strike_gap for i in range(-count, count + 1)]

    def get_symbols_and_tokens(self, expiry, strike_list, option_type):
        mgr = SymbolTokenManager(self.smartApi)
        result = []
        for strike in strike_list:
            symbol = f"{self.stock_name}{expiry}{strike}{option_type}"
            token = mgr.find_token_from_csv(symbol)
            result.append((symbol, token))
        return result








