import json
import time
import pytest,copy
from unittest.mock import MagicMock
from src.logger_manager import LoggerManager
from datetime import datetime


from src.order_manager import OrderManager
import random

@pytest.fixture
def load_mock_data():
    with open("test_input_data.json", "r") as file:
        return json.load(file)


class MockSmartAPI:


    def __init__(self, mock_data):
        self.mock_data = mock_data
        self.call_count = {
            "gttLists": 0,
            "orderBook": 0,
            "gttDetails": 0,
            "ltpData": 0
        }
        self.entry_value_data = mock_data
        self.rule_id_store = {}
        self.order_book = []
        self.gtt_list = []
        self.first_two_rule_ids = []
        self.ltp_cache = {}
        self.ltp_direction = {}  # per token direction
        self.rule_status_history = {}  # ✅ Added to track how many times each rule_id is checked

    def gttCreateRule(self, payload):
        rule_id = str(random.randint(5000000, 5999999))
        payload['rule_id'] = rule_id
        self.rule_id_store[rule_id] = payload

        gtt_order = {
            "rule_id": rule_id,
            "tradingsymbol": payload['tradingsymbol'].upper(),
            "status": "NEW",
            "triggerprice": payload['triggerprice'],
            "price": payload['price'],
            "qty": payload['qty']
        }
        self.gtt_list.append(gtt_order)

        self.first_two_rule_ids.append(rule_id)
        if len(self.first_two_rule_ids) == 2:
            triggered_rule_id = random.choice(self.first_two_rule_ids)
            triggered_payload = self.rule_id_store[triggered_rule_id]
            order = {
                "uniqueorderid": f"GTTV3_prod_{triggered_rule_id}",
                "status": "TRIGGERED",
                "averageprice": triggered_payload['triggerprice'],
                "tradingsymbol": triggered_payload['tradingsymbol'].upper(),
                "symboltoken": triggered_payload['symboltoken'],
                "updatetime": datetime.now().strftime("%d-%b-%Y %H:%M:%S")
            }
            self.order_book.append(order)
        return rule_id

    def gttCancelRule(self, payload):
        rule_id = payload.get("id")
        if rule_id in self.rule_id_store:
            self.rule_id_store[rule_id]["status"] = "CANCELLED"
            for gtt_order in self.gtt_list:
                if gtt_order["rule_id"] == rule_id:
                    gtt_order["status"] = "CANCELLED"
            return {"message": "cancelled"}
        else:
            return {"message": "Rule ID not found"}

    def gttModifyRule(self, payload):
        rule_id = payload.get("rule_id")
        if rule_id in self.rule_id_store:
            rule = self.rule_id_store[rule_id]
            rule["price"] = payload["price"]
            rule["triggerprice"] = payload["triggerprice"]
            for gtt_order in self.gtt_list:
                if gtt_order["rule_id"] == rule_id:
                    gtt_order["triggerprice"] = payload["triggerprice"]
                    gtt_order["price"] = payload["price"]
            return {"message": "modified"}
        else:
            return {"message": "Rule ID not found"}

    def gttDetails(self, rule_id):
        if rule_id not in self.rule_id_store:
            return {"message": "Rule ID not found", "status": False, "data": []}

        rule_data = copy.deepcopy(self.rule_id_store[rule_id])
        order_name = rule_data.get("order_name", "")
        rule_data["status"] = rule_data.get("status", "NEW").upper()
        print(f"rule_data: {rule_data}")

        self.rule_status_history.setdefault(rule_id, 0)
        print(self.rule_status_history[rule_id])
        # Status transition logic
        if order_name == "gtt_order1":
            if self.rule_status_history[rule_id] >= 2:
                rule_data["status"] = None

        elif order_name == "sl_order1":
            for rid, data in self.rule_id_store.items():
                if data.get("order_name") == "gtt_order1" and data.get("status") is None:
                    rule_data["status"] = "CANCELLED"

        elif order_name == "sl_order2":
            # First check: show ACTIVE, second check: make None
            print(self.rule_status_history[rule_id])
            if self.rule_status_history[rule_id] == 0:
                rule_data["status"] = "ACTIVE"
                # Initialize status history tracker

                self.rule_status_history[rule_id] += 1
            elif self.rule_status_history[rule_id] == 1:
                rule_data["status"] = None

        elif order_name == "sl_order3":
            # Only proceed if sl_order2 is None already
            sl2_triggered = any(
                d.get("order_name") == "sl_order2" and d.get("status") is None
                for d in self.rule_id_store.values()
            )
            if sl2_triggered:
                if self.rule_status_history[rule_id] == 0:
                    rule_data["status"] = "ACTIVE"
                    # Initialize status history tracker
                    self.rule_status_history.setdefault(rule_id, 0)
                    self.rule_status_history[rule_id] += 1
                elif self.rule_status_history[rule_id] == 1:
                    rule_data["status"] = None

        # Save the updated status back
        self.rule_id_store[rule_id]["status"] = rule_data["status"]

        return {"message": "SUCCESS", "data": rule_data}

    def orderBook(self):
        return {"message": "SUCCESS", "data": self.order_book, "status": True}

    def gttLists(self, status, pages, gtt_orders_count_list):
        self.call_count["gttLists"] += 1
        active_orders = [o for o in self.gtt_list if o["status"].upper() in ["ACTIVE", "NEW"]]
        return {"message": "SUCCESS", "data": active_orders}

    def ltpData(self, exchange, tradingsymbol, symboltoken):

        symboltoken = str(symboltoken)

        # Determine base entry price
        if int(symboltoken) == self.entry_value_data["ce_token"]:
            base_price = self.entry_value_data["ce_entry_price"]
        else:
            base_price = self.entry_value_data["pe_entry_price"]

        # Initialize cache if first time
        if symboltoken not in self.ltp_cache:
            self.ltp_cache[symboltoken] = base_price

        prev_ltp = self.ltp_cache[symboltoken]

        # Default behavior
        percent_change = random.uniform(0.01, 0.03)
        direction = random.choice([-1, 1])

        # Find all rules linked to this symboltoken
        related_rules = [
            rule for rule in self.rule_id_store.values()
            if str(rule.get("symboltoken")) == symboltoken
        ]
        order_names = [rule.get("order_name") for rule in related_rules]
        rule_status_map = {rule.get("order_name"): rule.get("status") for rule in related_rules}

        # Modify LTP behavior based on rule conditions
        if "sl_order3" in order_names and rule_status_map.get("sl_order2") is None:
            # Strong uptrend when sl_order2 is done
            percent_change = random.uniform(0.07, 0.1)
            direction = 1

        elif "sl_order2" in order_names and rule_status_map.get("sl_order1") in [None, "CANCELLED"]:
            # Uptrend begins for sl_order2
            percent_change = random.uniform(0.06, 0.09)
            direction = 1

        elif any(name in ["gtt_order1", "sl_order1"] for name in order_names):
            # Very slow, realistic movement for initial orders
            percent_change = random.uniform(0.005, 0.015)
            direction = random.choice([-1, 1])

        # Apply change
        change = round(prev_ltp * percent_change * direction, 2)
        new_ltp = max(0.01, round(prev_ltp + change, 2))  # LTP should never be <= 0

        # Save updated LTP
        self.ltp_cache[symboltoken] = new_ltp

        return {
            "data": {"ltp": new_ltp},
            "status": True
        }

@pytest.mark.integration
def test_main_order_monitoring_loop(load_mock_data):
    # Inject required entry data
    entry_value_data = load_mock_data["entry_value_data"]
    mock_api = MockSmartAPI(entry_value_data)
    # Step 0: Setup logging
    logger = LoggerManager()
    logger.write("🚀 Starting Trading Automation Workflow...")


    # Initialize OrderManager with mocked API and input
    om = OrderManager(mock_api, stock_name="RELIANCE", qty=1, entry_value_data=entry_value_data,logger=logger,testing=True)

    # Run main loop for one cycle only (force early exit with time or mock state)
    try:
        om.main_order_monitoring_loop(mock_api)
    except Exception as e:
        print(f"Test interrupted due to: {e}")

    print("Test complete. Calls made:", mock_api.call_count)
