import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pytz
import requests
from datetime import datetime
from SmartApi.smartExceptions import DataException
from src.angel_client import AngelOneClient
from src.logger_manager import LoggerManager

class OrderBookManager:
    def __init__(self, smartApi, logger=None):
        self.smartApi = smartApi
        self.logger = logger or self._setup_default_logger()

    def _setup_default_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def fetch_and_save_orders(self):
        try:
            orders = self.smartApi.orderBook()
            timestamp = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y%m%d_%H%M%S')
            filename = f'order_book_{timestamp}.txt'

            if orders and orders['data']:
                self.logger.write("Successfully fetched order book")
                # Display orders
                for order in orders['data']:
                    self.logger.write(json.dumps(order, indent=4))
                
                # Save to file
                with open(filename, 'w') as f:
                    json.dump(orders['data'], f, indent=4)
                self.logger.write(f"Orders saved to {filename}")
            else:
                self.logger.write("No orders found in order book")
                with open(filename, 'w') as f:
                    f.write("No orders found")

        except DataException as e:
            self.logger.write(f"Error fetching order book: {str(e)}", error=True)
        except Exception as e:
            self.logger.write(f"Unexpected error fetching order book: {str(e)}", error=True)

    def fetch_and_save_gtt(self):
        try:
            headers = {
                'Authorization': f'Bearer {self.smartApi.access_token}',
                'Content-Type': 'application/json'
            }

            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/gtt/v1/getgtt"
            response = requests.get(url, headers=headers)

            timestamp = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y%m%d_%H%M%S')
            filename = f'gtt_book_{timestamp}.txt'

            if response.status_code == 200:
                # Check if response has content
                if response.content:
                    try:
                        gtt_data = response.json()
                        if gtt_data and gtt_data.get('data'):
                            self.logger.write("Successfully fetched GTT list")
                            # Display GTT orders
                            for gtt in gtt_data['data']:
                                self.logger.write(json.dumps(gtt, indent=4))

                            # Save to file
                            with open(filename, 'w') as f:
                                json.dump(gtt_data['data'], f, indent=4)
                            self.logger.write(f"GTT list saved to {filename}")
                        else:
                            self.logger.write("No GTT orders found in response data")
                            with open(filename, 'w') as f:
                                f.write("No GTT orders found")
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON response: {response.text}"
                        self.logger.write(error_msg, error=True)
                        with open(filename, 'w') as f:
                            f.write(error_msg)
                else:
                    error_msg = "Empty response received from GTT API"
                    self.logger.write(error_msg, error=True)
                    with open(filename, 'w') as f:
                        f.write(error_msg)
            else:
                error_msg = f"Failed to fetch GTT list. Status code: {response.status_code}, Response: {response.text}"
                self.logger.write(error_msg, error=True)
                with open(filename, 'w') as f:
                    f.write(error_msg)

        except Exception as e:
            self.logger.write(f"Error fetching GTT list: {str(e)}", error=True)

def main():
    # Setup logging
    logger = LoggerManager()
    
    # Initialize and login to Angel One
    angel_client = AngelOneClient(logger)
    smartApi = angel_client.login()
    
    if smartApi:
        # Initialize order book manager
        order_manager = OrderBookManager(smartApi, logger)
        
        # Fetch and save order book
        order_manager.fetch_and_save_orders()
        
        # Fetch and save GTT list
        order_manager.fetch_and_save_gtt()
    else:
        logger.write("Failed to initialize SmartAPI", error=True)

if __name__ == "__main__":
    main()