import pandas as pd
from config import *
from datetime import datetime, timedelta
import pytz,shutil
import numpy as np
from collections import Counter
    

def round_to_0_05(value: float) -> float:
    """
    Round a float to the nearest 0.05 increment.
    """
    return round(value * 20) / 20.0


def retry_on_network_error(max_retries=3, base_delay=1):
    import time, random, requests, http.client, urllib3
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract logger from kwargs or use the first arg if it's a class instance with logger
            logger = kwargs.get('logger')
            if not logger and args and hasattr(args[0], 'logger'):
                logger = args[0].logger

            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, http.client.RemoteDisconnected,
                        requests.exceptions.RequestException,
                        urllib3.exceptions.ProtocolError,
                        urllib3.exceptions.ReadTimeoutError,
                        urllib3.exceptions.ConnectTimeoutError) as e:
                    retries += 1
                    delay = min(base_delay * (2 ** retries) + random.uniform(0, 1), 60)
                    if logger:
                        logger.write(f"[Retry {retries}] {func.__name__} failed: {e}, retrying in {delay:.1f}s")
                    time.sleep(delay)
            
            if logger:
                logger.write(f"{func.__name__} failed after {max_retries} retries.", error=True)
            raise
        return wrapper
    return decorator

def get_ist_now():
    """
    Get current time in Asia/Kolkata timezone.
    """
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def get_target_time(hours, minutes, seconds):
    """
    Generate target time in Asia/Kolkata timezone.
    """
    now = get_ist_now()
    target_time = now.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)
    ##target_time += timedelta(days=1)  # set for next day if already past
    return target_time

def get_options_data(smartApi,stock_name,future_price_data_dict):
    """
    Fetch basic CE/PE options data (ATM).
    """
    from src.symbol_token import SymbolTokenManager

    # First fetch future price required data
    futures_price = future_price_data_dict['futures_price']
    strike_gap = future_price_data_dict['strike_gap']
    nearest_expiry = future_price_data_dict['expiry']
    lot_size = future_price_data_dict['lot_size']

    ce_strike = int((futures_price // strike_gap) * strike_gap)
    pe_strike = int(((futures_price + (strike_gap - 1)) // strike_gap) * strike_gap)

    ce_symbol = f"{stock_name}{nearest_expiry}{ce_strike}CE"
    pe_symbol = f"{stock_name}{nearest_expiry}{pe_strike}PE"

    token_mgr = SymbolTokenManager(smartApi)
    ce_token = token_mgr.find_token_from_csv(ce_symbol)
    pe_token = token_mgr.find_token_from_csv(pe_symbol)

    return {
        'ce_symbol': ce_symbol,
        'pe_symbol': pe_symbol,
        'ce_strike': ce_strike,
        'pe_strike': pe_strike,
        'expiry': nearest_expiry,
        'ce_token': ce_token,
        'pe_token': pe_token,
        "lot_size": lot_size
    }

def backup_file(current_file_path,current_file_name):
    """
    Backup yesterday's scripmaster file to backup folder.
    """
    if os.path.exists(current_file_path):
        backup_filename = f"yesterday_{current_file_name}"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        shutil.move(current_file_path, backup_path)

def backup_current_folder_files():
    """
    Backup all files from data/current/ into data/backup/
    with timestamp added to filenames.
    """
    # Ensure backup folder exists
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # List all files in current directory
    for current_file_name in os.listdir(CURRENT_DIR):
        current_file_path = os.path.join(CURRENT_DIR, current_file_name)
        backup_file(current_file_path,current_file_name)

def fetch_ltp(smartApi,symbol, token,logger):
    try:
        params = {"exchange": "NFO", "tradingsymbol": symbol, "symboltoken": token}
        data = smartApi.ltpData(**params)
        return data['data']['ltp'] if data.get('status') else None
    except Exception as e:
        logger.write(f"Error fetching LTP for {symbol}: {e}")
        return None

def fetch_high(smartApi,symbol, token,logger):
    try:
        params = {"exchange": "NFO", "tradingsymbol": symbol, "symboltoken": token}
        data = smartApi.ltpData(**params)
        return data['data']['high'] if data.get('status') else None
    except Exception as e:
        logger.write(f"Error fetching LTP for {symbol}: {e}")
        return None


def create_gtt_order(smartApi,order_name, trading_symbol, symbol_token, trigger_price, limit_price,transaction_type, quantity,logger):
    """
    Create a GTT order with proper type conversion for numeric values

    Args:
        order_name (str): Name of the GTT order
        trading_symbol (str): Trading symbol for the order
        symbol_token (str): Symbol token for the order
        trigger_price (float): Trigger price for the order
        price (float): Order price
        last_traded_price (float): Last traded price
        quantity (int): Order quantity
    """
    try:
        trigger_price = float(trigger_price)
        limit_price = float(limit_price)
        quantity = int(quantity)
        symbol_token = int(symbol_token)  # Convert token to string as required by API

        gtt_payload = {
            "tradingsymbol": trading_symbol,
            "symboltoken": symbol_token,
            "exchange": "NFO",
            "producttype": "CARRYFORWARD",
            "transactiontype": transaction_type,
            "price": limit_price,   ## is nothing but add some limit value to the entry price
            "qty": quantity,
            "triggerprice": trigger_price, ## is nothing but entry pice
            "disclosedqty": 0,
            "timeperiod": 1,  ## If possible need to make it valid for 1 day, now it is valid till expiry day
            ##'order_name':order_name
        }
        for key, value in gtt_payload.items():
            if isinstance(value, (np.int64, np.int32, np.float64, np.float32)):
                gtt_payload[key] = value.item()

        rule_id = smartApi.gttCreateRule(gtt_payload)
        logger.write(f"GTT Order '{order_name}' created successfully. Rule ID: {rule_id}")
        return rule_id
    except Exception as e:
        logger.write(f"Error creating GTT order '{order_name}': {e}")
        return None

def cancel_gtt_order(smartApi,rule_id,token,logger):
    payload =     {
     "id": str(rule_id),
     "symboltoken": str(token),
     "exchange": "NFO"
    }
    try:
        response = smartApi.gttCancelRule(payload)
        logger.write(f"Cancelled GTT: {rule_id}")
    except Exception as e:
        logger.write(f"Failed to Cancel {rule_id}: {e}")

def modify_gtt_sl(smartApi,rule_id,token, new_sl, qtty,logger):
    new_sl_trigger = round_to_0_05(new_sl * 0.995)
    payload = {"exchange": "NFO",
               "id": str(rule_id),
               "price": str(new_sl_trigger), ## limit price 26.45
               "qty": qtty,
               "symboltoken": str(token),
               "triggerprice": new_sl ## trigger price 26.6
               }
    try:
        response = smartApi.gttModifyRule(payload)
        logger.write(f"SL updated for Rule ID {rule_id}")
    except Exception as e:
        logger.write(f"Failed to update SL for Rule ID {rule_id}: {e}")

def roundof(value):
    rounded = round(value, 2)
    formatted = "{:.2f}".format(rounded)
    final_float = float(formatted)
    return final_float

def modify_gtt_trigger(smartApi,rule_id,token, new_price, qtty,logger):
    new_trigger = round_to_0_05(new_price * 0.995)
    payload = {"exchange": "NFO",
               "id": str(rule_id),
               "price": str(new_price),
               "qty": qtty,
               "symboltoken": str(token),
               "triggerprice": new_trigger
               }
    try:
        response = smartApi.gttModifyRule(payload)
        logger.write(f"Target updated for Rule ID {rule_id}")
    except Exception as e:
        logger.write(f"Failed to update target for Rule ID {rule_id}: {e}")

def pending_orders_count(smartApi,logger):
    try:
        order_data = smartApi.orderBook()
        ##self.logger.write("Order data:", order_data)

        if order_data.get('status') and isinstance(order_data.get('data'), list):
            orders = order_data['data']

            # Count order statuses
            status_counts = Counter(order.get('orderstatus') for order in orders)

            # Calculate pending orders
            pending = status_counts.get('trigger pending', 0) + status_counts.get('open', 0)
            return pending
        else:
            logger.write("Error fetching order book.")
            return 0

    except Exception as e:
        logger.write(f"Error fetching orders book for count: {e}")
        return 0

def read_orders_as_list_of_dicts(file_path: str,logger):
    """
    Reads the given CSV file and returns the content as a list of dictionaries.
    Each row becomes a dictionary.
    """

    try:
        # Read CSV into DataFrame
        df = pd.read_csv(file_path)

        # Convert DataFrame to list of dicts
        orders_list = df.to_dict(orient="records")

        return orders_list

    except Exception as e:
        logger.write(f"❌ ERROR: Failed to process {file_path}: {str(e)}")
        return None

def backup_orders_folder_files():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for current_file_name in os.listdir(ORDERS_DIR):
        current_file_path = os.path.join(ORDERS_DIR, current_file_name)
        backup_file(current_file_path, current_file_name)

class Utils:
    """
    Shared utilities and state manager for the trading workflow.
    """
    def __init__(self,logger,backup):
        self.stock_name = None
        self.qty = None
        self.smartApi = None
        self.logger=logger
        self.backup=backup

    def initialize(self):
        """
        Load stock_name and qty from input CSV.
        """
        if self.backup:
            backup_current_folder_files()
            self.logger.write("✅ All Backup files are taken backup")
            backup_orders_folder_files()
            self.logger.write("✅ All Order Backup files are taken backup")
        self.stock_name = self.get_stock_name()
        self.qty = self.get_qty()

    @staticmethod
    def get_stock_name(file_path: str = input_stock_name_and_quantity_file_path) -> str:
        """
        Read stock_name from the input CSV file.
        """
        df = pd.read_csv(file_path)
        return df['stock_name'][0]

    @staticmethod
    def get_qty(file_path: str = input_stock_name_and_quantity_file_path) -> int:
        """
        Read quantity from the input CSV file.
        """
        df = pd.read_csv(file_path)
        return int(df['qty'][0])
    
    def run_steps(self):
        from src.angel_client import AngelOneClient
        from src.options_data import OptionsDataManager
        from src.order_manager import OrderManager
        from src.scrip_master import ScripMasterManager
        from src.entry_value_data_collection import EntryValuesData
        from src.flow_control import flow_control
        #
        entry_value_data_dict = None

        try:

            # # Step 1: Setup ScripMaster data
            if flow_control['scrip_master_file_download']:
                scrip_manager = ScripMasterManager(self.stock_name,self.logger)
                scrip_manager.setup_scripmaster()

            # Step 2: Login
            if flow_control['angle_login']:
                client = AngelOneClient(self.logger)
                self.smartApi = client.login()

            # # Step 3: Fetch scrip master data and collecting future price
            if flow_control['scrip_master_file_download'] and flow_control['fetch_scrip_master_data_and_calculate_future_price']:
                future_price_dict_data = scrip_manager.get_scrip_master_data_and_along_with_future_price(self.smartApi,self.stock_name)


            # # Step 4: creating multi optional data file
            if flow_control['scrip_master_file_download'] and flow_control['fetch_scrip_master_data_and_calculate_future_price'] and flow_control['multi_optional_data']:
                options_mgr = OptionsDataManager(self.smartApi, self.stock_name,self.logger)
                options_mgr.get_multi_option_data_collection(option_data_target_hr,option_data_target_min,option_data_target_sec,future_price_dict_data)

            # # Step 5: create  entry values data file
            if flow_control['entry_value_creations'] and  flow_control['scrip_master_file_download'] and flow_control['fetch_scrip_master_data_and_calculate_future_price']:
                entry_values_mgr = EntryValuesData(self.smartApi, self.stock_name,self.qty,self.logger)
                entry_value_data_dict = entry_values_mgr.entry_values_data(future_price_dict_data)

            # # Step 6: Place Orders
            if flow_control['angle_login'] and flow_control['orders']:
                order_mgr = OrderManager(self.smartApi, self.stock_name, self.qty,entry_value_data_dict,self.logger)
                order_mgr.main_order_monitoring_loop()

        except ValueError as e:
            self.logger.write(f"❌ ERROR:: {e}")

        except Exception as e:
            self.logger.write(f"❌ ERROR while processing run steps:", error=True, exc=e)




        


