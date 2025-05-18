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

class OrderFetcher:
    def __init__(self, smartApi, logger=None):
        self.smartApi = smartApi
        self.logger = logger or self._setup_default_logger()

    def _setup_default_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def get_open_orders(self):
        try:
            orders = self.smartApi.orderBook()
            if orders and orders['data']:
                self.logger.write("Successfully fetched open orders")
                # Save orders to file with timestamp
                timestamp = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y%m%d_%H%M%S')
                filename = f'data/orders/orders_{timestamp}.json'
                with open(filename, 'w') as f:
                    json.dump(orders, f, indent=4)
                self.logger.write(f"Orders saved to {filename}")
                return orders['data']
            else:
                self.logger.write("No open orders found")
                return []
        except DataException as e:
            self.logger.write(f"Error fetching open orders: {str(e)}", error=True)
            return []
        except Exception as e:
            self.logger.write(f"Unexpected error fetching orders: {str(e)}", error=True)
            return []

    def fetch_gtt_list_fallback(self):
        try:
            headers = {
                'Authorization': f'Bearer {self.smartApi.access_token}',
                'Content-Type': 'application/json'
            }

            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/gtt/v1/getgtt"
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                gtt_data = response.json()
                tz = pytz.timezone("Asia/Kolkata")
                today = datetime.now(tz).date()

                todays_gtts = [
                    gtt for gtt in gtt_data['data']
                    if datetime.fromtimestamp(gtt['created_on'], tz).date() == today
                ]

                timestamp_str = datetime.now(tz).strftime("%Y-%m-%d_%H-%M")
                filename = f"gttList_{timestamp_str}.txt"
                with open(filename, "w") as file:
                    json.dump(todays_gtts, file, indent=2)

                self.logger.write(f"Saved {len(todays_gtts)} GTT entries to {filename}")
            else:
                self.logger.write(f"Failed to fetch GTT list: {response.text}", error=True)
        except Exception as e:
            self.logger.write(f"Error in fallback GTT fetch: {str(e)}", error=True)

def main():
    # Setup logging
    logger = LoggerManager()
    
    # Initialize and login to Angel One
    global smartApi, order_fetcher
    angel_client = AngelOneClient(logger)
    smartApi = angel_client.login()
    order_fetcher = OrderFetcher(smartApi, logger)
    if smartApi:
        # Fetch open orders
        order_fetcher.get_open_orders()  # Correct
        if orders:
            logger.write("Open Orders:")
            for order in orders:
                logger.write(json.dumps(order, indent=4))
        
        # Fetch GTT list
        order_fetcher.fetch_gtt_list_fallback()
    else:
        logger.write("Failed to initialize SmartAPI", error=True)

if __name__ == "__main__":
    main()
import requests

def fetch_gtt_list_fallback(smartApi):
    try:
        headers = {
            'Authorization': f'Bearer {smartApi.jwt_token}',
            'Content-Type': 'application/json'
        }

        url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/gtt/v1/getgtt"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            gtt_data = response.json()
            tz = pytz.timezone("Asia/Kolkata")
            today = datetime.now(tz).date()

            todays_gtts = [
                gtt for gtt in gtt_data['data']
                if datetime.fromtimestamp(gtt['created_on'], tz).date() == today
            ]

            timestamp_str = datetime.now(tz).strftime("%Y-%m-%d_%H-%M")
            filename = f"gttList_{timestamp_str}.txt"
            with open(filename, "w") as file:
                json.dump(todays_gtts, file, indent=2)

            print(f"\nSaved {len(todays_gtts)} GTT entries to {filename}")
        else:
            print(f"Failed to fetch GTT list: {response.text}")
    except Exception as e:
        print(f"Error in fallback GTT fetch: {str(e)}")


#********************************************************************#
def save_todays_gtt_list(smartApi):
    try:
        response = smartApi.gtt_lists()

        tz = pytz.timezone("Asia/Kolkata")
        today = datetime.now(tz).date()
        todays_gtts = []

        for gtt in response['data']:
            created_time = datetime.fromtimestamp(gtt['created_on'], tz).date()
            if created_time == today:
                todays_gtts.append(gtt)

        # Generate filename with current date and time
        timestamp_str = datetime.now(tz).strftime("%Y-%m-%d_%H-%M")
        filename = f"gttList_{timestamp_str}.txt"

        with open(filename, "w") as file:
            json.dump(todays_gtts, file, indent=2)

        print(f"\nSaved {len(todays_gtts)} GTT entries to {filename}")
    except Exception as e:
        print(f"Error fetching or saving GTT list: {str(e)}")


#********************************************************************#

order_fetcher.get_open_orders(smartApi)
order_fetcher.fetch_gtt_list_fallback(smartApi)

