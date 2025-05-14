import time
import random
from logzero import logger
import pandas as pd
from config import scripmaster_csv_file_path


class SymbolTokenManager:
    def __init__(self, smartApi):
        self.smartApi = smartApi
        self.cache = {}  # In-memory cache for tokens

    def find_token_from_csv(self,symbol,csv_path=scripmaster_csv_file_path):
        try:
            df = pd.read_csv(csv_path)
            match = df[df['symbol'] == symbol]
            if not match.empty:
                return int(match.iloc[0]['token'])
            else:
                return None
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return None

    def find_token(self, trading_symbol, exchange="NFO", max_retries=5, base_delay=2):
        # Return cached token if available
        if trading_symbol in self.cache:
            return self.cache[trading_symbol]

        for attempt in range(max_retries):
            try:
                time.sleep(base_delay * (2 ** attempt) + random.uniform(0, 0.5))  # backoff + jitter
                result = self.smartApi.searchScrip(exchange, trading_symbol)
                for item in result.get('data', []):
                    if item['tradingsymbol'] == trading_symbol:
                        token = int(item['symboltoken'])
                        self.cache[trading_symbol] = token
                        return token
                logger.warning(f"[{trading_symbol}] Token not found on attempt {attempt + 1}")
            except Exception as e:
                if 'exceeding access rate' in str(e).lower():
                    logger.warning(f"Rate limit hit for {trading_symbol}, retrying...")
                else:
                    logger.error(f"Error while fetching token for {trading_symbol}: {e}")
                    break

        logger.error(f"Failed to get token for {trading_symbol} after {max_retries} attempts")
        return 0  # Return fallback 0 if not found
