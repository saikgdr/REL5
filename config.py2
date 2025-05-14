import os

# Base directory of your project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data folders
DATA_DIR = os.path.join(BASE_DIR, "data")
CURRENT_DIR = os.path.join(DATA_DIR, "current")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")
ORDERS_DIR = os.path.join(DATA_DIR, "orders")

# Input CSV file
input_stock_name_and_quantity_file_path = os.path.join(DATA_DIR, "input_stock_name_and_quantity.csv")

# Scripmaster path
scrip_master_file_name = 'scripmaster.csv'
scripmaster_csv_file_path = os.path.join(CURRENT_DIR, scrip_master_file_name)


# Entry value file paths
entry_value_filename = "entry_values.csv"
entry_value_file_path = os.path.join(CURRENT_DIR, entry_value_filename)

## File to save data
multi_option_data_file_name= "multi_options_data.csv"
multi_option_data_file_path = os.path.join(CURRENT_DIR, multi_option_data_file_name)

# Logs directory
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Add your AngelOne credentials also here (api key, username, pwd, totp token)

login_api_key = 'm0hyTXbG'
login_username = 'AAAB622217'
login_pwd = '2244'
login_token="2HMTADJVMDC5QDVN7NEAHRANPY"

##------------------------Orders----------------------------------------##
gtt_orders_count_list=10

## First order file to save data
first_orders_file_name= "first_orders.csv"
first_orders_file_path = os.path.join(ORDERS_DIR, first_orders_file_name)

first_success_order_file_name= "first_success_orders.csv"
first_success_order_file_path = os.path.join(ORDERS_DIR, first_success_order_file_name)

second_orders_placed_file_name= "second_orders_placed.csv"
second_orders_placed_file_path = os.path.join(ORDERS_DIR, second_orders_placed_file_name)


##------------------ Time control------------------------------------------

## order end time
order_endtime_hr=23
order_endtime_min=59

## strat time control 9hr:15min:0sec (option data target time)
option_data_target_hr=9
option_data_target_min=15
option_data_target_sec=0

## end time control 9hr:19min:53sec (Multi option fetch data)
multi_option_fetch_data_hr=20
multi_option_fetch_data_min=26
multi_option_fetch_data_sec=53
