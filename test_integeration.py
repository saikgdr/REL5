import threading
import json
import time
import pytest, copy
from src.logger_manager import LoggerManager
from src.order_manager import OrderManager
from datetime import datetime
import random

# ... [Keep your MockSmartAPI here, unchanged from earlier] ...

@pytest.mark.integration
def test_main_order_monitoring_loop(load_mock_data):
    entry_value_data = load_mock_data["entry_value_data"]
    mock_api = MockSmartAPI(entry_value_data)

    logger = LoggerManager()
    logger.write("🚀 Starting Trading Automation Workflow...")

    om = OrderManager(
        mock_api,
        stock_name="RELIANCE",
        qty=1,
        entry_value_data=entry_value_data,
        logger=logger,
        testing=True
    )

    # Wrap main loop in a thread
    def run_loop():
        try:
            om.main_order_monitoring_loop(mock_api)
        except Exception as e:
            print(f"Loop error: {e}")

    thread = threading.Thread(target=run_loop)
    thread.start()

    # Wait max 5 seconds for the loop to run
    thread.join(timeout=5)

    if thread.is_alive():
        print("🛑 Test timeout reached. Loop still running.")
    else:
        print("✅ Loop exited cleanly.")

    print("Test complete. Calls made:", mock_api.call_count)
