import os
import csv
import pytz
import time
from datetime import datetime
import pandas as pd
from config import *
from src.utils import fetch_ltp,create_gtt_order,cancel_gtt_order,round_to_0_05,modify_gtt_sl,roundof,modify_gtt_trigger,pending_orders_count,read_orders_as_list_of_dicts,backup_orders_folder_files
from src.flow_control import flow_control
from src.orders_logic_control import second_set_of_gtt_orders_creation
from SmartApi.smartExceptions import DataException

class OrderManager:
    def __init__(self, smartApi, stock_name, qty,entry_value_data,logger,testing=False):
        self.smartApi = smartApi
        self.stock_name = stock_name.upper()
        self.qty = qty
        self.lotsize = None
        self.logger = logger
        self.entry_value_data_dict = self.get_entry_values_data() if entry_value_data is None else entry_value_data
        self.first_order_data_dict = {}
        self.first_success_order_data_dict={}
        self.second_orders_data_list=[]
        self.testing = testing
        self.first_orders_placed = flow_control['first_orders_placed']
        self.gtt_order_book_status = flow_control['gtt_order_book_status']
        self.second_order_status = flow_control['second_order_status']
        self.monitor_second_order_status = flow_control['monitor_second_order_status']
        self.monitor_third_orders_flag = flow_control['monitor_third_orders_flag']
        self.cancelled_sl_orders = False

    def first_orders(self):
        current_pending_orders = pending_orders_count(self.smartApi,self.logger)
        self.logger.write(f"Current Pending Orders: {current_pending_orders}")
        current_gtt_pending_orders = self.gtt_active_orders_count()
        self.logger.write(f"Current GTT Pending Orders: {current_gtt_pending_orders}")
        order_status = False

        if current_gtt_pending_orders == 0 and current_pending_orders == 0:
            ce_current_ltp = fetch_ltp(self.smartApi,self.entry_value_data_dict['ce_symbol'], self.entry_value_data_dict['ce_token'],self.logger)
            pe_current_ltp = fetch_ltp(self.smartApi,self.entry_value_data_dict['pe_symbol'], self.entry_value_data_dict['pe_token'],self.logger)

            if ce_current_ltp is not None and pe_current_ltp is not None:
                if ce_current_ltp <= self.entry_value_data_dict['ce_entry_limit'] and pe_current_ltp <= self.entry_value_data_dict['pe_entry_limit']:
                    self.logger.write(f"{self.entry_value_data_dict['ce_symbol']}'s Current LTP: {ce_current_ltp} is less than entry price: {self.entry_value_data_dict['ce_entry_limit']} and {self.entry_value_data_dict['pe_symbol']}'s Current LTP: {pe_current_ltp} is less than entry price: {self.entry_value_data_dict['pe_entry_limit']}")
                    ce_order1_rule_id = create_gtt_order(self.smartApi, "ce_order1", self.entry_value_data_dict['ce_symbol'], self.entry_value_data_dict['ce_token'],
                                     self.entry_value_data_dict['ce_entry_price'], self.entry_value_data_dict['ce_entry_limit'],
                                     "BUY", self.entry_value_data_dict['lot_size'] * self.qty, self.logger)

                    self.logger.write(f"CE Order Rule ID: {ce_order1_rule_id}")
                    if ce_order1_rule_id is None: # if ce order is not created we are handle from this step
                        return order_status

                    pe_order1_rule_id = create_gtt_order(self.smartApi, "pe_order1", self.entry_value_data_dict['pe_symbol'],
                                                        self.entry_value_data_dict['pe_token'],
                                                        self.entry_value_data_dict['pe_entry_price'],
                                                        self.entry_value_data_dict['pe_entry_limit'],
                                                        "BUY", self.entry_value_data_dict['lot_size'] * self.qty,self.logger)

                    self.logger.write(f"PE Order Rule ID: {pe_order1_rule_id}")
                    if pe_order1_rule_id is None and ce_order1_rule_id is not None: # if pe order is not created we are handle from this step and also we cancelling the ce order.
                        cancel_gtt_order(self.smartApi,ce_order1_rule_id,self.entry_value_data_dict['ce_token'],self.logger)
                        return order_status

                    # creating first orders list
                    orders_list = [
                        {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "order_name": "ce_order1",
                            "symbol": self.entry_value_data_dict['ce_symbol'],
                            "token": self.entry_value_data_dict['ce_token'],
                            "rule_id": ce_order1_rule_id,
                            "triggered_price":self.entry_value_data_dict['ce_entry_price'],
                            "limit_price":self.entry_value_data_dict['ce_entry_limit'],
                        },
                        {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "order_name": "pe_order1",
                            "symbol": self.entry_value_data_dict['pe_symbol'],
                            "token": self.entry_value_data_dict['pe_token'],
                            "rule_id": pe_order1_rule_id,
                            "triggered_price":self.entry_value_data_dict['pe_entry_price'],
                            "limit_price":self.entry_value_data_dict['pe_entry_limit'],
                        }
                    ]

                    self.save_orders_in_csv_file(orders_list,first_orders_file_path)

                    ## update this first order data to global variable
                    if len(self.first_order_data_dict) == 0:
                        self.first_order_data_dict['ce_order1'] = {'rule_id':ce_order1_rule_id}
                        self.first_order_data_dict['pe_order1'] = {'rule_id': pe_order1_rule_id}

                    self.logger.write("CE Order sent")
                    self.logger.write("PE Order Sent")
                    self.logger.write("--------------First order created successfully------------------")
                    order_status = True
                else:
                    self.logger.write(f"{self.entry_value_data_dict['ce_symbol']}'s Current LTP: {ce_current_ltp} is greater than {self.entry_value_data_dict['ce_entry_limit']}. Not placing the CE Order")
                    self.logger.write(f"{self.entry_value_data_dict['pe_symbol']}'s Current LTP: {pe_current_ltp} is greater than {self.entry_value_data_dict['pe_entry_limit']}. Not placing the PE Order")
            else:
                self.logger.write("WARNING: Unable to fetch LTP values from the SmartAPI")

        if current_gtt_pending_orders == 2:
            order_status = False
            self.logger.write("ERROR: Manually delete the GTT Orders in UI")

        return order_status

    def save_orders_in_csv_file(self,order_records: list,save_file_path):
        """
        Save order records to a CSV file using Pandas.
        Always overwrite the file with the fresh records.

        :param order_records: List of dictionaries with order details.
        """
        if not order_records:
            self.logger.write("WARNING: No orders to save.")
            return

        # Create a DataFrame directly
        df = pd.DataFrame(order_records)

        # Save DataFrame to CSV (overwrite mode)
        df.to_csv(save_file_path, index=False)

        self.logger.write(f"✅ {len(order_records)} orders saved successfully to {save_file_path}")

    def get_entry_values_data(self):

        """
        Read entry values from a CSV file and return a structured dictionary.
        """
        try:
            df = pd.read_csv(entry_value_file_path)

            if df.empty:
                self.logger.write(f"ERROR: File {entry_value_file_path} is empty.")
                return None

            # Use only the first row (assuming it's single row data)
            row = df.iloc[0]

            # Prepare output dictionary
            output = {
                "timestamp": row['timestamp'],
                "ce_symbol": row['ce_symbol'],
                "ce_token": int(row['ce_token']),
                "pe_symbol": row['pe_symbol'],
                "pe_token": int(row['pe_token']),
                "ce_entry_price": float(row['ce_entry_price']),
                "ce_entry_limit": float(row['ce_entry_limit']),
                "pe_entry_price": float(row['pe_entry_price']),
                "pe_entry_limit": float(row['pe_entry_limit']),
                "ce_strike": int(row['ce_strike']),
                "pe_strike": int(row['pe_strike']),
                "expiry": row['expiry'],
                "lot_size": int(row['lot_size'])
            }

            return output

        except Exception as e:
            self.logger.write(f"ERROR: Failed to read and process {entry_value_file_path}: {str(e)}")
            return None

    def gtt_active_orders_count(self):
        """
        ##PayLoad
        {
         "status": [
              "NEW",
              "CANCELLED",
              "ACTIVE",
              "SENTTOEXCHANGE",
              "FORALL"
         ],
         "page": 1,
         "count": 10
        }
     """
        try:
            status = [
                "NEW",
                "ACTIVE",
            ]
            response = self.smartApi.gttLists(status, 1, gtt_orders_count_list)

            if response["message"] == "SUCCESS":
                # for i in response["data"]:
                    # self.logger.write(f"Stock Name: {i['tradingsymbol']} status: {i['status']}")
                return len(response["data"])
            else:
                self.logger.write("Failed to fetch GTT details or no GTT data available.")
                return -1
        except Exception as e:
            self.logger.write(f"Error fetching GTT active order count: {e}")
            return None

    def read_first_placed_orders(self,file_path: str) -> dict:
        """
        Read the first placed orders CSV from a given file path
        and return as a structured nested dictionary.
        """
        if not os.path.isfile(file_path):
            self.logger.write(f"ERROR: File not found: {file_path}")
            return None
        try:
            df = pd.read_csv(file_path)

            if df.empty:
                self.logger.write(f"ERROR: No records in {file_path}")
                return None

            # Build nested dictionary
            orders_dict = {}

            for idx, row in df.iterrows():
                if idx == 0:
                    order_key = "ce_order1"
                elif idx == 1:
                    order_key = "pe_order1"
                else:
                    order_key = f"order{idx + 1}"

                orders_dict[order_key] = {
                    "rule_id": row['rule_id'],  # Important: mapping unique_order_id => rule_id
                }

            return orders_dict

        except Exception as e:
            self.logger.write(f"ERROR: Failed to read and parse {file_path}: {str(e)}")
            return None

    def check_status_of_first_two_gtt_orders_in_orderbook(self):
        order_status = False
        if len(self.first_order_data_dict) == 0:
            self.first_order_data_dict=self.read_first_placed_orders(first_orders_file_path)
            if self.first_order_data_dict is None:
                return order_status
        ce_order_rule_id = self.first_order_data_dict["ce_order1"]["rule_id"]
        pe_order_rule_id = self.first_order_data_dict["pe_order1"]["rule_id"]
        ce_unique_order_id= f"GTTV3_prod_{ce_order_rule_id}"
        pe_unique_order_id = f"GTTV3_prod_{pe_order_rule_id}"

        orderbook_response = self.smartApi.orderBook()
        time.sleep(0.3)
        orderbook_response_data = orderbook_response['data']
        # Format today's date
        today_str = datetime.now().strftime("%d-%b-%Y")

        if orderbook_response_data is not None:
            data=orderbook_response['data']
            todays_filtered_order_book_data = [record for record in data if record.get("updatetime", "").startswith(today_str)]
            for order in todays_filtered_order_book_data:
                if order.get('uniqueorderid') == ce_unique_order_id or ce_unique_order_id in order.get('uniqueorderid'):
                    ce_order_status = order.get('status').lower() in ['triggered', 'complete']
                    if ce_order_status:
                        time.sleep(0.1)  ## need to modify
                        cancel_gtt_order(self.smartApi,pe_order_rule_id,self.entry_value_data_dict['pe_token'],self.logger)
                        ce_success_order_list = [
                            {"order_name":"ce_order1",
                             "entered_price":order["averageprice"],
                             "symbol":order["tradingsymbol"],
                             "token":order["symboltoken"]}
                        ]
                        self.save_orders_in_csv_file(ce_success_order_list,first_success_order_file_path)

                        ## update this first success ce order data to global variable
                        if len(self.first_success_order_data_dict) == 0:
                            self.first_success_order_data_dict = {"order_name":"ce_order1",
                             "entered_price":order["averageprice"],
                             "symbol":order["tradingsymbol"],
                             "token":order["symboltoken"]}
                        order_status = True
                        self.logger.write(f"-------------- First CE order Executed, cancelled PE order {pe_order_rule_id} --------------")
                        break
                    self.logger.write(f"CE Order Status: {ce_order_status}")

                if order.get('uniqueorderid') == pe_unique_order_id or pe_unique_order_id in order.get('uniqueorderid'):
                    pe_order_status = order.get('status').lower() in ['triggered', 'complete']
                    if pe_order_status:
                        time.sleep(0.1)  ## need to modify
                        cancel_gtt_order(self.smartApi,ce_order_rule_id,self.entry_value_data_dict['ce_token'],self.logger)
                        pe_success_order_list = [
                            {"order_name": "pe_order1",
                             "entered_price": order["averageprice"],
                             "symbol": order["tradingsymbol"],
                             "token": order["symboltoken"]}
                        ]
                        self.save_orders_in_csv_file(pe_success_order_list, first_success_order_file_path)

                        ## update this first success pe order data to global variable
                        if len(self.first_success_order_data_dict) == 0:
                            self.first_success_order_data_dict = {"order_name": "pe_order1",
                                                                  "entered_price": order["averageprice"],
                                                                  "symbol": order["tradingsymbol"],
                                                                  "token": order["symboltoken"]}
                        order_status = True
                        self.logger.write(f"--------------First PE order status was success and cancelled CE order {ce_order_rule_id}----------------------------")
                        break
                    self.logger.write(f"PE Order Status: {pe_order_status}")
        return order_status

    def second_set_of_orders(self):
        if len(self.first_success_order_data_dict)==0:
            df = pd.read_csv(first_success_order_file_path)

            if len(df) == 0:
                self.logger.write(f"ERROR: There was no data in first success order file {first_success_order_file_path}")
                raise Exception (f"ERROR: There was no data in first success order file {first_success_order_file_path}")

            for i in df.index:
                self.first_success_order_data_dict['order_name'] = df.loc[i,"order_name"]
                self.first_success_order_data_dict['symbol'] =  df.loc[i,"symbol"]
                self.first_success_order_data_dict['token'] = df.loc[i,"token"]
                self.first_success_order_data_dict['entered_price'] = df.loc[i,"entered_price"]

        trade_name, trading_symbol, symbol_token, entered_price = (self.first_success_order_data_dict['order_name'],
                                                                   self.first_success_order_data_dict['symbol'],
                                                                   self.first_success_order_data_dict['token'],
                                                                   self.first_success_order_data_dict['entered_price'])

        order_status = False
        if trade_name in ["ce_order1", "pe_order1"]:
            trigger_price1,limit_price1,sl_price,sl_trigger_price,qty1,qty2,qty3 = second_set_of_gtt_orders_creation(entered_price,self.entry_value_data_dict['lot_size'],self.qty)

            # self.logger.write final calculated values
            self.logger.write(f"Target 1: Trigger ={trigger_price1} Price={limit_price1},Qty={qty1}")
            self.logger.write(f"Stop-loss price:{sl_price}, Stop-loss trigger: {sl_trigger_price}")

            # Place the 3 GTT OCO orders (example function call)

            gtt_order1_rule_id=create_gtt_order(self.smartApi,"gtt_order1", trading_symbol, symbol_token, trigger_price1, limit_price1, "SELL", qty1,self.logger)
            if gtt_order1_rule_id is None:
                self.logger.write(f"Error: GTT Order1 creation was failed.")
                return order_status

            gtt_sl_order1_rule_id=create_gtt_order(self.smartApi,"gtt_sl_order1", trading_symbol, symbol_token, sl_trigger_price, sl_price, "SELL",qty1,self.logger)
            if gtt_sl_order1_rule_id is None:
                cancel_gtt_order(self.smartApi,gtt_order1_rule_id,self.first_success_order_data_dict['token'],self.logger)
                self.logger.write(f"Error:GTT SL Order1 creation was failed so cancelling the GTT Order 1 as well.")
                return order_status

            gtt_sl_order2_rule_id=create_gtt_order(self.smartApi,"gtt_sl_order2", trading_symbol, symbol_token, sl_trigger_price, sl_price, "SELL",qty2,self.logger)
            if gtt_sl_order2_rule_id is None:
                cancel_gtt_order(self.smartApi, gtt_order1_rule_id, self.first_success_order_data_dict['token'],self.logger)
                cancel_gtt_order(self.smartApi, gtt_sl_order1_rule_id, self.first_success_order_data_dict['token'],self.logger)
                self.logger.write(f"Error:GTT SL Order2 creation was failed so cancelling the GTT Order 1 and GTT SL order1 as well.")
                return order_status

            gtt_sl_order3_rule_id=create_gtt_order(self.smartApi,"gtt_sl_order3", trading_symbol, symbol_token, sl_trigger_price, sl_price, "SELL",qty3,self.logger)
            if gtt_sl_order3_rule_id is None:
                cancel_gtt_order(self.smartApi, gtt_order1_rule_id, self.first_success_order_data_dict['token'],self.logger)
                cancel_gtt_order(self.smartApi, gtt_sl_order1_rule_id, self.first_success_order_data_dict['token'],self.logger)
                cancel_gtt_order(self.smartApi, gtt_sl_order2_rule_id, self.first_success_order_data_dict['token'],self.logger)
                self.logger.write(f"Error: GTT SL Order3 creation was failed so cancelling all Four GTT Orders.")
                return order_status

            second_order_payload = [
                {"order_name":"gtt_order1",
                 "symbol":trading_symbol,
                 "token":symbol_token,
                 "trigger_price":trigger_price1,
                 "limit_price":limit_price1,
                 "transaction_type":"SELL",
                 "quantity":qty1,
                 "rule_id":gtt_order1_rule_id},

                {"order_name": "gtt_sl_order1",
                "symbol": trading_symbol,
                "token": symbol_token,
                "trigger_price": sl_trigger_price,
                "limit_price": sl_price,
                "transaction_type": "SELL",
                "quantity": qty1,
                "rule_id": gtt_sl_order1_rule_id},

                {"order_name": "gtt_sl_order2",
                 "symbol": trading_symbol,
                 "token": symbol_token,
                 "trigger_price": sl_trigger_price,
                 "limit_price": sl_price,
                 "transaction_type": "SELL",
                 "quantity": qty2,
                 "rule_id": gtt_sl_order2_rule_id},

                {"order_name": "gtt_sl_order3",
                 "symbol": trading_symbol,
                 "token": symbol_token,
                 "trigger_price": sl_trigger_price,
                 "limit_price": sl_price,
                 "transaction_type": "SELL",
                 "quantity": qty3,
                 "rule_id": gtt_sl_order3_rule_id}

            ]
            self.save_orders_in_csv_file(second_order_payload,second_orders_placed_file_path)
            self.second_orders_data_list = second_order_payload
            order_status = True
            self.logger.write("-----------Second set of orders was created successfully-------------------")
            self.logger.write(f"{'--' * 100}")
        return order_status

    def monitor_second_orders(self):
        order_status=False
        # Ensure rule_ids_dict is a dictionary
        if len(self.second_orders_data_list) == 0:
            order_list=read_orders_as_list_of_dicts(second_orders_placed_file_path,self.logger)
            if order_list is None or len(order_list) == 0:
                raise TypeError(f"There was no data in second order placed csv file {second_orders_placed_file_path}")
            else:
                self.second_orders_data_list=order_list

        # Access the dictionary using string keys
        gtt_order1_info = self.second_orders_data_list[0]
        if len(gtt_order1_info) == 0:
            self.logger.write("gtt_order1 not found in rule_ids_dict")
            return order_status

        gtt_sl_order1_info = self.second_orders_data_list[1]
        gtt_sl_order2_info = self.second_orders_data_list[2]
        gtt_sl_order3_info = self.second_orders_data_list[3]
        gtt_order1_flag = True
        gtt_sl_order1_flag = True

        END_TIME = datetime.now(pytz.timezone("Asia/Kolkata")).replace(hour=order_endtime_hr, minute=order_endtime_min,
                                                                       second=0, microsecond=0)
        while True:
            # end time logic need to add
            if datetime.now(pytz.timezone("Asia/Kolkata")) >= END_TIME:
                self.logger.write(f"Time has reached the END_TIME {END_TIME}, exiting the workflow.")
                # self.cancel_all_orders()  # Add logic to cancel all orders here
                break  # Exit the loop
            try:
                self.logger.write(f"STEP4 in Orders: Monitoring second set at {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                time.sleep(0.5)
                rule_id1 = gtt_order1_info["rule_id"]
                rule_sl_id1 = gtt_sl_order1_info["rule_id"]
                rule_sl_id2 = gtt_sl_order2_info["rule_id"]
                rule_sl_id3 = gtt_sl_order3_info["rule_id"]

                if gtt_order1_flag:
                    gtt_order1_info_from_api = self.smartApi.gttDetails(rule_id1)
                    # self.logger.write(f"GTT Status: {gtt_order1_info_from_api}")
                    gtt_order1_status = gtt_order1_info_from_api["data"]["status"]

                    gtt_sl_order2_info_from_api = self.smartApi.gttDetails(rule_sl_id2)
                    gtt_sl_order3_info_from_api = self.smartApi.gttDetails(rule_sl_id3)

                    qtty2 = gtt_sl_order2_info_from_api["data"]["qty"]
                    qtty3 = gtt_sl_order3_info_from_api["data"]["qty"]

                    ### added the following line to check if the gtt_sl_order1_status is None
                    # gtt_order1_status = None
                    if gtt_order1_status is None or gtt_order1_status == 'SENTTOEXCHANGE':  
                        cancel_gtt_order(self.smartApi,rule_sl_id1,gtt_sl_order1_info['token'],self.logger)
                        modify_gtt_sl(self.smartApi,rule_sl_id2,gtt_sl_order2_info['token'], self.first_success_order_data_dict['entered_price'], qtty2,self.logger)
                        modify_gtt_sl(self.smartApi,rule_sl_id3,gtt_sl_order3_info['token'],self.first_success_order_data_dict['entered_price'], qtty3,self.logger)
                        gtt_order1_flag = False
                        order_status=True
                        self.logger.write(f"---GTT Order1 is executed. so cancelled GTT SL Order1 and Modified the GTT SL Order2 from "
                                          f"{gtt_sl_order2_info['trigger_price']} to {self.first_success_order_data_dict['entered_price']} "
                                          f"and SL Order3 from {gtt_sl_order3_info['trigger_price']} to {self.first_success_order_data_dict['entered_price']} ")
                        self.logger.write(f"{'--' * 100}")
                        break

                if gtt_sl_order1_flag:
                    gtt_sl_order1_info_from_api = self.smartApi.gttDetails(rule_sl_id1)
                    # self.logger.write(f"GTT Status: {gtt_sl_order1_info_from_api}")
                    gtt_sl_order1_status = gtt_sl_order1_info_from_api["data"]["status"]
                    ### added the following line to check if the gtt_sl_order1_status is None
                    # gtt_sl_order1_status = None
                    if gtt_sl_order1_status is None or gtt_sl_order1_status == 'SENTTOEXCHANGE':
                        cancel_gtt_order(self.smartApi,rule_id1,gtt_order1_info['token'],self.logger)
                        gtt_sl_order1_flag = False
                        order_status=True
                        self.cancelled_sl_orders = True
                        self.logger.write("-----GTT SL Order1 is executed so cancelled GTT Order1 and assuming SL Order2 "
                                          "and SL Order3 is also existed BY ANGEL One Broker APP---")
                        self.logger.write(f"{'--'*100}")
                        break

            except Exception as e:
                self.logger.write(f"Error in monitor loop: {e}")
                time.sleep(2)
                ##break
        return order_status

    def monitor_third_orders(self):  ### Imran Thougghts :: CHECK IF ORDER IS ALIVE THEN PROCEED WITH MODIFICATIONS OTHERWISE BREAK
        order_status=True
        assumption_value = roundof(1.15)
        assumption_third_order = roundof(1.35)
        gtt_sl_order2_status = True
        gtt_sl_order3_status = True
        trading_symbol = self.first_success_order_data_dict["symbol"]
        symbol_token = self.first_success_order_data_dict["token"]
        entered_price = self.first_success_order_data_dict["entered_price"]
        rule_sl_id2 = self.second_orders_data_list[2]["rule_id"]   ## This is nothing but SL order2
        rule_sl_id3 = self.second_orders_data_list[3]["rule_id"]   ## This is nothing but SL order3
        sl_token_id2 = self.second_orders_data_list[2]['token']
        sl_token_id3 = self.second_orders_data_list[3]['token']
        previous_sl_order2 = self.first_success_order_data_dict['entered_price']
        previous_sl_order3 = self.first_success_order_data_dict['entered_price']

        END_TIME = datetime.now(pytz.timezone("Asia/Kolkata")).replace(hour=order_endtime_hr, minute=order_endtime_min, second=0, microsecond=0)
        while True:
            # end time logic need to add
            if datetime.now(pytz.timezone("Asia/Kolkata")) >= END_TIME:
                self.logger.write(f"Time has reached the END_TIME {END_TIME}, exiting the workflow.")
                # self.cancel_all_orders()  # Add logic to cancel all orders here
                break  # Exit the loop
            try:
                time.sleep(0.5)
                modified_sl_order2_value = roundof(assumption_value - 0.1)
                modified_sl_order3_value = roundof(assumption_third_order - 0.2) # Imran modified on 15 May when it is not setting up correct SL
                ltp_response = self.smartApi.ltpData(exchange="NFO", tradingsymbol=trading_symbol, symboltoken=symbol_token)
                ltp_response = ltp_response["data"]["ltp"]
                self.logger.write(f"STEP5 in Orders: Monitoring THIRD set:")

                if gtt_sl_order2_status is not None and gtt_sl_order2_status != 'SENTTOEXCHANGE':
                    gtt_sl_order2_info_from_api = self.smartApi.gttDetails(rule_sl_id2)
                    gtt_sl_order2_status = gtt_sl_order2_info_from_api["data"]["status"]
                    qtty2 = gtt_sl_order2_info_from_api["data"]["qty"]
                    self.logger.write(f"        LTP: {ltp_response} , waiting for {assumption_value} % price: {roundof(entered_price * assumption_value)}") 
                
                if gtt_sl_order3_status is not None and gtt_sl_order3_status != 'SENTTOEXCHANGE':
                    gtt_sl_order3_info_from_api = self.smartApi.gttDetails(rule_sl_id3)
                    gtt_sl_order3_status = gtt_sl_order3_info_from_api["data"]["status"]
                    qtty3 = gtt_sl_order3_info_from_api["data"]["qty"]
                    self.logger.write(f"        LTP: {ltp_response} , waiting for {assumption_third_order} % price: {roundof(entered_price * assumption_third_order)}")
                
                self.logger.write(f"        SL Order2 Status: {gtt_sl_order2_status}.        SL Order3 Status: {gtt_sl_order3_status}.")
                
                if assumption_value == assumption_third_order and ltp_response >= entered_price * assumption_value:
                    self.logger.write(f"Third order Assumption Value Reached {assumption_third_order}") ## starts with 1.35, 1.55 and son on

                    if gtt_sl_order3_status in ["NEW", "ACTIVE"] and gtt_sl_order2_status in ["NEW", "ACTIVE"]:
                        self.logger.write(f"-----------Both GTT SL Order2 and GTT SL order3 status are active state so modifying both sl order values-----")
                        modify_gtt_sl(self.smartApi,rule_sl_id2,sl_token_id2,roundof(entered_price * modified_sl_order2_value), qtty2, self.logger)
                        modify_gtt_sl(self.smartApi,rule_sl_id3,sl_token_id3,roundof(entered_price * modified_sl_order3_value), qtty3, self.logger)

                        self.logger.write(
                            f"    Modified the SL Order 2 trigger value to entered price: {entered_price}:"
                            f"    Modified_sl_order2_value: {modified_sl_order2_value} from {previous_sl_order2} to {roundof(entered_price * modified_sl_order2_value)}")

                        self.logger.write(
                            f"    Modified the SL Order 3 trigger value to entered price: {entered_price}:"
                            f"    Modified_sl_order3_value: {modified_sl_order3_value} from {previous_sl_order3} to {roundof(entered_price * modified_sl_order3_value)}")

                        self.logger.write(f"Current assumption value: {assumption_value} and Third order assumption value {assumption_third_order}")

                        assumption_value = roundof(assumption_value + 0.1)
                        assumption_third_order = roundof(assumption_third_order + 0.2)
                        previous_sl_order2 = roundof(entered_price * modified_sl_order2_value)
                        previous_sl_order3 = roundof(entered_price * modified_sl_order3_value)

                        self.logger.write(f"Modified the assumption value to {assumption_value} and THIRD order assumption value to {assumption_third_order}")
                        self.logger.write(f"{'--'*100}")

                    elif gtt_sl_order3_status in ["NEW", "ACTIVE"]:
                        self.logger.write(f"-----------Only GTT SL Order3 are active state and GTT SL order2 in-active state so modifying sl order3 values-----")
                        modify_gtt_sl(self.smartApi,rule_sl_id3,sl_token_id3, roundof(entered_price * modified_sl_order3_value), qtty3, self.logger)

                        self.logger.write(
                            f"Current Modified the SL Order 3 trigger value to entered price: {entered_price}"
                            f" modified_sl_value: {modified_sl_order3_value}, from {previous_sl_order3} to {roundof(entered_price * modified_sl_order3_value)}")

                        self.logger.write(f"Current assumption value:{assumption_value}, Third order assumption value: {assumption_third_order}")

                        ## assumption_value = roundof(assumption_value + 0.1)
                        assumption_third_order = roundof(assumption_third_order + 0.2)
                        previous_sl_order3 = roundof(entered_price * modified_sl_order3_value)

                        self.logger.write(f"Modified Third order assumption value: {assumption_third_order}")
                        self.logger.write(f"{'--' * 100}")

                    elif (gtt_sl_order2_status is None or gtt_sl_order2_status == 'SENTTOEXCHANGE') and (gtt_sl_order3_status is None or gtt_sl_order3_status == 'SENTTOEXCHANGE'):
                        self.logger.write(f"-----------BOTH SL Orders are executed so existing and restarting the orders-----")
                        order_status = True
                        break

                elif ltp_response >= entered_price * assumption_third_order and (gtt_sl_order2_status is None or gtt_sl_order2_status == 'SENTTOEXCHANGE') and (gtt_sl_order3_status is not None or gtt_sl_order3_status != 'SENTTOEXCHANGE'):   ## stars with 1.1 and goes on
                    if gtt_sl_order3_status in ["NEW", "ACTIVE"]:
                        self.logger.write(f"-----------Only GTT SL Order3 are active state and GTT SL order2 in-active state so modifying sl order3 values-----")
                        modify_gtt_sl(self.smartApi,rule_sl_id3,sl_token_id3,roundof(entered_price * modified_sl_order3_value),qtty3,self.logger)

                        self.logger.write(f"Current Modified the SL Order 3 triggered value: entered price {entered_price}:"
                                          f" modified_sl_value: {modified_sl_order3_value},  from {previous_sl_order3} to {roundof(entered_price * modified_sl_order3_value)}")

                        self.logger.write(f"Current assumption_third_order value:{assumption_third_order}")

                        assumption_third_order = roundof(assumption_third_order + 0.2)
                        previous_sl_order3 = roundof(entered_price * modified_sl_order3_value)

                        self.logger.write(f"Modified the assumption_third_order value to {assumption_third_order}")
                        self.logger.write(f"{'--' * 100}")

                elif ltp_response >= entered_price * assumption_value and (gtt_sl_order2_status is not None or gtt_sl_order2_status != 'SENTTOEXCHANGE'):   ## stars with 1.15 and goes on
                    if gtt_sl_order2_status in ["NEW", "ACTIVE"]:
                        self.logger.write(f"---------BOTH GTT SL Order2 and SL Order3 are active state But sl_order3 assumption not matched so only modifying sl order2 value-----")
                        modify_gtt_sl(self.smartApi,rule_sl_id2,sl_token_id2,roundof(entered_price * modified_sl_order2_value),qtty2,self.logger)

                        self.logger.write(f"Current Modified the SL Order 2 triggered value: entered price {entered_price}:"
                                          f" modified_sl_value: {modified_sl_order2_value} from  {previous_sl_order2} to {roundof(entered_price * modified_sl_order2_value)}" )

                        self.logger.write(f"Current assumption value:{assumption_value}")

                        assumption_value = roundof(assumption_value + 0.1)
                        previous_sl_order2 = roundof(entered_price * modified_sl_order2_value)

                        self.logger.write(f"Modified the assumption value to {assumption_value}")
                        self.logger.write(f"{'--' * 100}")

                elif (gtt_sl_order2_status is None or gtt_sl_order2_status == 'SENTTOEXCHANGE') and (gtt_sl_order3_status is None or gtt_sl_order3_status == 'SENTTOEXCHANGE'):
                    order_status = True
                    self.logger.write(f"-----------BOTH SL Orders are executed so existing and restarting the orders-----")
                    break

            except Exception as e:
                self.logger.write(f"Error in monitor loop:", error=True, exc=e)
                time.sleep(2)
                ##break
        return order_status

    def restart_orders(self,mock_api):
        # exit()
        # Flags to track the progress of order processing
        self.first_orders_placed = True     ## True means enabled
        self.gtt_order_book_status = False
        self.second_order_status = False
        self.monitor_second_order_status = False
        self.monitor_third_orders_flag = False
        self.cancelled_sl_orders = False

        self.logger.write(f"All orders flag values reset for next iteration")
        # backup_orders_folder_files()
        self.logger.write("✅ All Order Backup files are taken backup")
        self.first_order_data_dict = {}
        self.first_success_order_data_dict = {}
        self.second_orders_data_list = []

        flow_control['placing_first_order'] = True
        flow_control['first_order_status_checking'] = True
        flow_control['second_set_of_orders'] = True
        flow_control['monitoring_second_orders'] = True
        flow_control['monitoring_third_orders'] = True

        if self.testing:
            mock_api.rule_id_store = {}
            mock_api.order_book = []
            mock_api.gtt_list = []
            mock_api.first_two_rule_ids = []
            mock_api.ltp_cache = {}  # Stores last known LTP per symbol token


    def main_order_monitoring_loop(self,mock_api=None):
        """
        Main loop to monitor and manage order statuses.
        """
        # Set the end time to 23:59:00 in Asia/Kolkata timezone
        END_TIME = datetime.now(pytz.timezone("Asia/Kolkata")).replace(hour=order_endtime_hr, minute=order_endtime_min, second=0, microsecond=0)

        self.logger.write(f"******** Started orders Monitoring from main_order_monitoring_loop at {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}********")
        condition = datetime.now(pytz.timezone("Asia/Kolkata")) < END_TIME
        print(datetime.now(pytz.timezone("Asia/Kolkata")))
        print(END_TIME)
        while condition:
            try:
                if datetime.now(pytz.timezone("Asia/Kolkata")) >= END_TIME:
                    self.logger.write(f"Time has reached the END_TIME {END_TIME}, exiting the workflow.")
                    # self.cancel_all_orders()  # Add logic to cancel all orders here
                    break  # Exit the loop

                if self.first_orders_placed and flow_control['placing_first_order']:
                    self.logger.write(f"STEP1 IN ORDERS: Placing First set of orders at {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    first_order_status=self.first_orders()
                    if first_order_status:
                        self.first_orders_placed = False
                        self.gtt_order_book_status = True
                        flow_control['placing_first_order']=False

                elif  self.gtt_order_book_status and flow_control['first_order_status_checking']:
                    self.logger.write(f"STEP2 IN ORDERS: Monitoring CE and PE orders, time is: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    gtt_order_book_status = self.check_status_of_first_two_gtt_orders_in_orderbook()
                    if gtt_order_book_status:
                        self.gtt_order_book_status = False
                        self.second_order_status = True
                        flow_control['first_order_status_checking']=False

                elif  self.second_order_status and flow_control['second_set_of_orders']:
                    self.logger.write(f"STEP3 IN ORDERS: Placing second set of gtt orders at {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    second_order_status = self.second_set_of_orders()
                    if second_order_status:
                        self.second_order_status = False
                        self.monitor_second_order_status=True
                        flow_control['second_set_of_orders']=False

                elif  self.monitor_second_order_status and flow_control['monitoring_second_orders']:
                    self.logger.write(f"STEP4 IN ORDERS: Monitoring second set, at: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    monitor_second_order_status = self.monitor_second_orders()
                    if monitor_second_order_status:
                        if self.cancelled_sl_orders:
                            self.logger.write("************ Ended: GTT SL Order1 Executed So restarting the orders again ************")
                            self.restart_orders(mock_api)
                        else:
                            self.monitor_second_order_status = False
                            self.monitor_third_orders_flag = True
                            flow_control['monitoring_second_orders']=False

                elif  self.monitor_third_orders_flag and flow_control['monitoring_third_orders']:
                    self.logger.write(f"STEP5 IN ORDERS: Monitoring third set (Trailing orders) at {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    monitor_third_orders_flag = self.monitor_third_orders()
                    if monitor_third_orders_flag:
                        self.logger.write("************ Ended: All orders processed successfully Restarting the Orders.*******************")
                        self.restart_orders(mock_api)

            except DataException as e:
                self.logger.write("Access denied because of exceeding access rate is reached so waiting for 2 sec to retry the smart APIs")
                time.sleep(2)

            except Exception as e:
                self.logger.write(f"Error occurred in order processing:", error=True, exc=e)
                # Optionally, log the error using a logger
                # logger.error(f"Order processing failed: {str(e)}")
                ##break  # Exit the loop on exception
                time.sleep(2)

            time.sleep(0.5)  # Wait for 0.5 second before the next iteration
        self.logger.write(f"************ Ended: End Time is reached {END_TIME}, exiting workflow. ******************")
