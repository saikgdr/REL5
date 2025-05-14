import time
from src.logger_manager import LoggerManager
from src.utils import Utils

def main():
    from src.flow_control import flow_control
    start_time = time.time()  # <-- Start timing

    # Step 0: Setup logging
    logger = LoggerManager()
    logger.write("🚀 Starting Trading Automation Workflow...")

    # Step 1: Initialize Utils (load stock name and qty)
    utils = Utils(logger,flow_control['take_backup'])
    utils.initialize()
    logger.write(f"📈 Stock selected: {utils.stock_name}")
    logger.write(f"📦 Quantity selected: {utils.qty}")

    # Step 2: Execute full trading steps
    utils.run_steps()

    logger.write("✅ MAIN Workflow execution completed.")

    end_time = time.time()  # <-- End timing
    elapsed_time = end_time - start_time
    logger.write(f"⏱️ Total time taken: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()