import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
from SmartApi.smartExceptions import DataException
from angel_client import AngelOneClient
from logger_manager import LoggerManager

class PositionExitManager:
    def __init__(self, smartApi, logger=None):
        self.smartApi = smartApi
        self.logger = logger or self._setup_default_logger()

    def _setup_default_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def get_open_positions(self):
        """Fetch all open positions from the trading account."""
        try:
            response = self.smartApi.position()
            if response['message'] == 'SUCCESS' and response['data']:
                return response['data']
            self.logger.write("No open positions found.")
            return []
        except DataException as e:
            self.logger.write(f"Error fetching positions: {str(e)}", error=True)
            return None
        except Exception as e:
            self.logger.write(f"Unexpected error while fetching positions: {str(e)}", error=True)
            return None

    def exit_position(self, position):
        """Exit a single position with proper error handling."""
        try:
            # Prepare order parameters
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": position['tradingsymbol'],
                "symboltoken": position['symboltoken'],
                "transactiontype": "SELL" if position['netqty'] > 0 else "BUY",
                "exchange": position['exchange'],
                "ordertype": "MARKET",
                "producttype": position['producttype'],
                "quantity": abs(int(position['netqty'])),
                "triggerprice": 0
            }

            # Place exit order
            response = self.smartApi.placeOrder(order_params)
            if response['status']:
                self.logger.write(f"Successfully placed exit order for {position['tradingsymbol']}")
                return True
            else:
                self.logger.write(f"Failed to place exit order for {position['tradingsymbol']}: {response['message']}", error=True)
                return False

        except Exception as e:
            self.logger.write(f"Error exiting position {position['tradingsymbol']}: {str(e)}", error=True)
            return False

    def exit_all_positions(self):
        """Exit all open positions in the account."""
        positions = self.get_open_positions()
        if positions is None:
            self.logger.write("Failed to fetch positions. Exiting.", error=True)
            return False

        if not positions:
            self.logger.write("No positions to exit.")
            return True

        success_count = 0
        total_positions = len(positions)

        for position in positions:
            if int(position['netqty']) != 0:  # Only exit if there's an open quantity
                if self.exit_position(position):
                    success_count += 1

        self.logger.write(f"Successfully exited {success_count} out of {total_positions} positions")
        return success_count == total_positions

def main():
    # Setup logging
    logger = LoggerManager()
    
    # Initialize and login to Angel One
    angel_client = AngelOneClient(logger)
    smartApi = angel_client.login()
    
    # Initialize position manager and exit positions
    position_manager = PositionExitManager(smartApi, logger)
    position_manager.exit_all_positions()

if __name__ == "__main__":
    main()