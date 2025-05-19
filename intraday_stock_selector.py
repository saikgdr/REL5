import os
import pandas as pd
import numpy as np
import requests
import time
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
import warnings
import io
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_selector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class IntradayStockSelector:
    def __init__(self):
        # Remove target time as it's no longer needed
        self.data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Complete list of NSE F&O stocks (216 stocks) with updated symbols
        self.nifty_stocks = [
            "AARTIIND", "ABB", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ACC", "ADANIENT", "ADANIPORTS", 
            "ALKEM", "AMBUJACEM", "APOLLOHOSP", "APOLLOTYRE", "ASHOKLEY", "ASIANPAINT", "ASTRAL", 
            "ATUL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", 
            "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BANKBARODA", "BATAINDIA", "BEL", "BERGEPAINT", 
            "BHARATFORG", "BHARTIARTL", "BHEL", "BIOCON", "BOSCHLTD", "BPCL", "BRITANNIA", "BSOFT", 
            "CANBK", "CANFINHOME", "CHAMBLFERT", "CHOLAFIN", "CIPLA", "COALINDIA", "COFORGE", "COLPAL", 
            "CONCOR", "COROMANDEL", "CROMPTON", "CUB", "CUMMINSIND", "DABUR", "DALBHARAT", "DEEPAKNTR", 
            "DELTACORP", "DIVISLAB", "DIXON", "DLF", "DRREDDY", "EICHERMOT", "ESCORTS", "EXIDEIND", 
            "FEDERALBNK", "GAIL", "GLENMARK", "GMRAIRPORT", "GNFC", "GODREJCP", "GODREJPROP", "GRANULES", 
            "GRASIM", "GSPL", "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", 
            "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "HONAUT", "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDEA", "IDFCFIRSTB", "IEX", 
            "IGL", "INDHOTEL", "INDIACEM", "INDIAMART", "INDIGO", "INDUSINDBK", "INDUSTOWER", "INFY", 
            "INTELLECT", "IOC", "IPCALAB", "IRCTC", "ITC", "JINDALSTEL", "JKCEMENT", "JSWSTEEL", 
            "JUBLFOOD", "KOTAKBANK", "LALPATHLAB", "LAURUSLABS", "LICHSGFIN", "LT", "LTIM", 
            "LTTS", "LUPIN", "M&M", "M&MFIN", "MANAPPURAM", "MARICO", "MARUTI", 
            "MCX", "METROPOLIS", "MFSL", "MGL", "MOTHERSON", "MPHASIS", "MRF", "MUTHOOTFIN", 
            "NAM-INDIA", "NATIONALUM", "NAUKRI", "NAVINFLUOR", "NESTLEIND", "NMDC", "NTPC", "OBEROIRLTY", 
            "OFSS", "ONGC", "PAGEIND", "PEL", "PERSISTENT", "PETRONET", "PFC", "PIDILITIND", "PIIND", 
            "PNB", "POLYCAB", "POWERGRID", "PVRINOX", "RAIN", "RAMCOCEM", "RBLBANK", "RECLTD", "RELIANCE", 
            "SAIL", "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SIEMENS", "SRF", "SUNPHARMA", 
            "SUNTV", "SYNGENE", "TATACHEM", "TATACOMM", "TATACONSUM", "TATAMOTORS", "TATAPOWER", "TATASTEEL", 
            "TCS", "TECHM", "TITAN", "TORNTPHARM", "TORNTPOWER", "TRENT", "TVSMOTOR", "UBL", "ULTRACEMCO", 
            "UPL", "VEDL", "VOLTAS", "WHIRLPOOL", "WIPRO", "ZEEL", "ZYDUSLIFE", "ADANIPOWER", "CESC", 
            "INDHOTEL", "INDIAMART", "IRCTC", "JUBLFOOD", "MARICO", "MPHASIS", "NESTLEIND", 
            "OFSS", "PAGEIND", "PERSISTENT", "PIIND", "SBICARD", "SBILIFE", "SHREECEM", "SIEMENS", "SYNGENE", 
            "TATACOMM", "TATACONSUM", "TVSMOTOR", "UBL", "VOLTAS", "WHIRLPOOL", "ZYDUSLIFE"
        ]
        
        # Filter out banned stocks for today
        self.filter_banned_stocks()
        
        # Selection criteria weights
        self.weights = {
            'pre_market_change': 0.3,
            'volume_ratio': 0.2,
            'price_momentum': 0.2,
            'volatility': 0.15,
            'gap_up_down': 0.15
        }
        
        # Add weights for falling stocks (PE options)
        self.falling_weights = {
            'pre_market_change': 0.3,  # Higher negative change is better for PE
            'volume_ratio': 0.2,       # Higher volume is still good
            'price_momentum': 0.2,     # Higher negative momentum is better for PE
            'volatility': 0.15,        # Same volatility preference
            'gap_up_down': 0.15        # Higher negative gap is better for PE
        }
    
    def filter_banned_stocks(self):
        """Filter out stocks that are banned for F&O trading today"""
        try:
            # Fetch the list of banned stocks from NSE website or a reliable API
            banned_stocks = self.get_banned_stocks()
            
            if banned_stocks:
                # Remove banned stocks from the list
                original_count = len(self.nifty_stocks)
                self.nifty_stocks = [stock for stock in self.nifty_stocks if stock not in banned_stocks]
                logger.info(f"Filtered out {original_count - len(self.nifty_stocks)} banned stocks")
                logger.info(f"Banned stocks for today: {', '.join(banned_stocks)}")
            else:
                logger.info("No stocks are banned for today")
        except Exception as e:
            logger.error(f"Error filtering banned stocks: {e}")
            logger.info("Proceeding with all stocks")
    
    def get_banned_stocks(self):
        """Get the list of stocks banned for F&O trading today"""
        try:
            # Use the NSE archives URL for banned stocks
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Get the F&O ban list from NSE archives
            response = requests.get('https://nsearchives.nseindia.com/content/fo/fo_secban.csv', headers=headers)
            
            if response.status_code == 200:
                # Read CSV content
                csv_content = response.content.decode('utf-8')
                df = pd.read_csv(io.StringIO(csv_content))
                
                # Extract the symbol column (adjust column name if needed)
                banned_stocks = df['Symbol'].tolist() if 'Symbol' in df.columns else []
                logger.info(f"Found {len(banned_stocks)} banned stocks")
                return banned_stocks
            
            logger.warning("Could not fetch banned stocks from NSE archives")
            return []
                
        except Exception as e:
            logger.error(f"Error fetching banned stocks: {e}")
            return []

    def fetch_premarket_data(self):
        """Fetch pre-market data for Nifty stocks"""
        logger.info("Fetching pre-market data...")
        
        premarket_data = {}
        
        def fetch_stock_data(symbol):
            try:
                # Add .NS suffix for NSE stocks
                ticker = yf.Ticker(f"{symbol}.NS")
                
                # Get pre-market data (if available) or previous day's data
                hist = ticker.history(period="2d")
                
                if len(hist) < 1:
                    return None
                
                current = hist.iloc[-1]
                previous = hist.iloc[-2] if len(hist) > 1 else current
                
                return {
                    'symbol': symbol,
                    'current_price': current['Close'],
                    'previous_close': previous['Close'],
                    'pre_market_change': ((current['Close'] - previous['Close']) / previous['Close']) * 100,
                    'volume': current['Volume'],
                    'avg_volume': hist['Volume'].mean(),
                    'high': current['High'],
                    'low': current['Low'],
                    'open': current['Open']
                }
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                return None
        
        # Use ThreadPoolExecutor to fetch data in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(fetch_stock_data, self.nifty_stocks))
        
        # Filter out None results and convert to DataFrame
        valid_results = [r for r in results if r is not None]
        if valid_results:
            df = pd.DataFrame(valid_results)
            df.to_csv(os.path.join(self.data_dir, "premarket_data.csv"), index=False)
            logger.info(f"Fetched pre-market data for {len(valid_results)} stocks")
            return df
        else:
            logger.error("Failed to fetch pre-market data for any stocks")
            return None
    
    def calculate_metrics(self, df):
        """Calculate additional metrics for stock selection"""
        if df is None or len(df) == 0:
            return None
        
        logger.info("Calculating selection metrics...")
        
        # Calculate volume ratio (current volume / average volume)
        df['volume_ratio'] = df['volume'] / df['avg_volume']
        
        # Calculate price momentum (% change)
        df['price_momentum'] = df['pre_market_change']
        
        # Calculate volatility (high-low range as % of open)
        df['volatility'] = ((df['high'] - df['low']) / df['open']) * 100
        
        # Calculate gap up/down (open vs previous close)
        df['gap_up_down'] = ((df['open'] - df['previous_close']) / df['previous_close']) * 100
        
        # NOW filter out stocks with significant gaps (both up and down)
        gap_threshold = 0.75  # Define threshold for significant gaps (e.g., 1.5%)
        logger.info(f"Filtering out stocks with gaps greater than {gap_threshold}%")
        
        # Count before filtering
        count_before = len(df)
        
        # Filter out stocks with significant gaps
        df = df[abs(df['gap_up_down']) < gap_threshold]
        
        # Count after filtering
        count_after = len(df)
        logger.info(f"Filtered out {count_before - count_after} stocks with significant gaps")
        
        if count_after == 0:
            logger.warning("No stocks left after gap filtering! Using a higher threshold.")
            # If no stocks left, try with a higher threshold
            gap_threshold = 3.0  # Higher threshold
            df = df[abs(df['gap_up_down']) < gap_threshold]
            logger.info(f"Using higher threshold ({gap_threshold}%), {len(df)} stocks remaining")
        
        return df
    
    def rank_stocks(self, df, direction='rising'):
        """Rank stocks based on weighted criteria
        
        Parameters:
        -----------
        df : DataFrame
            DataFrame containing stock data
        direction : str
            'rising' for CE options, 'falling' for PE options
        """
        if df is None or len(df) == 0:
            return None
        
        logger.info(f"Ranking stocks based on criteria for {direction} stocks...")
        
        # Choose weights based on direction
        weights = self.weights if direction == 'rising' else self.falling_weights
        
        # Normalize each metric to 0-1 scale
        for metric in weights.keys():
            if metric in df.columns:
                if direction == 'rising':
                    # For rising stocks (CE options)
                    if metric in ['pre_market_change', 'price_momentum', 'volume_ratio', 'gap_up_down']:
                        # Higher is better for rising stocks
                        df[f'{metric}_score'] = (df[metric] - df[metric].min()) / (df[metric].max() - df[metric].min() + 1e-10)
                    elif metric == 'volatility':
                        # Moderate values are better
                        mean_vol = df[metric].mean()
                        df[f'{metric}_score'] = 1 - abs(df[metric] - mean_vol) / (df[metric].max() - df[metric].min() + 1e-10)
                else:
                    # For falling stocks (PE options)
                    if metric in ['pre_market_change', 'price_momentum', 'gap_up_down']:
                        # Lower is better for falling stocks (invert the score)
                        df[f'{metric}_score'] = 1 - (df[metric] - df[metric].min()) / (df[metric].max() - df[metric].min() + 1e-10)
                    elif metric == 'volume_ratio':
                        # Higher volume is still better
                        df[f'{metric}_score'] = (df[metric] - df[metric].min()) / (df[metric].max() - df[metric].min() + 1e-10)
                    elif metric == 'volatility':
                        # Moderate values are better
                        mean_vol = df[metric].mean()
                        df[f'{metric}_score'] = 1 - abs(df[metric] - mean_vol) / (df[metric].max() - df[metric].min() + 1e-10)
        
        # Calculate weighted score
        df['total_score'] = 0
        for metric, weight in weights.items():
            if f'{metric}_score' in df.columns:
                df['total_score'] += df[f'{metric}_score'] * weight
        
        # Rank stocks by total score
        df_ranked = df.sort_values('total_score', ascending=False).reset_index(drop=True)
        
        return df_ranked
    
    def select_best_stocks(self):
        """Select the best stocks for both CE and PE options trading"""
        start_time = time.time()
        logger.info(f"Starting stock selection process at {datetime.datetime.now().strftime('%H:%M:%S')}")
        
        # Fetch pre-market data
        df = self.fetch_premarket_data()
        
        # Calculate metrics
        df = self.calculate_metrics(df)
        
        if df is None or len(df) == 0:
            logger.error("Failed to get stock data")
            return None, None
        
        # Rank stocks for CE options (rising)
        df_ranked_ce = self.rank_stocks(df, direction='rising')
        
        # Rank stocks for PE options (falling)
        df_ranked_pe = self.rank_stocks(df, direction='falling')
        
        best_ce_stock = None
        best_pe_stock = None
        
        # Get today's date for file naming
        today_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        if df_ranked_ce is not None and len(df_ranked_ce) > 0:
            # Select the top-ranked stock for CE
            best_ce_stock = df_ranked_ce.iloc[0]
            
            # Save the ranked list for CE with date
            df_ranked_ce.to_csv(os.path.join(self.data_dir, f"ranked_stocks_ce_{today_date}.csv"), index=False)
            
            # Create a detailed report for CE with date
            with open(os.path.join(self.data_dir, f"best_ce_stock_report_{today_date}.txt"), "w") as f:
                f.write(f"Best Stock for CE Options Trading (Rising): {best_ce_stock['symbol']}\n")
                f.write(f"Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"Current Price: {best_ce_stock['current_price']:.2f}\n")
                f.write(f"Pre-market Change: {best_ce_stock['pre_market_change']:.2f}%\n")
                f.write(f"Volume Ratio: {best_ce_stock['volume_ratio']:.2f}\n")
                f.write(f"Volatility: {best_ce_stock['volatility']:.2f}%\n")
                f.write(f"Gap Up/Down: {best_ce_stock['gap_up_down']:.2f}% (Low gap preferred)\n")
                f.write(f"Total Score: {best_ce_stock['total_score']:.4f}\n\n")
                f.write("Top 5 Stocks for CE:\n")
                for i in range(min(5, len(df_ranked_ce))):
                    stock = df_ranked_ce.iloc[i]
                    f.write(f"{i+1}. {stock['symbol']} - Score: {stock['total_score']:.4f}, Change: {stock['pre_market_change']:.2f}%, Gap: {stock['gap_up_down']:.2f}%\n")
            
            logger.info(f"Selected {best_ce_stock['symbol']} as the best stock for CE options trading")
        
        if df_ranked_pe is not None and len(df_ranked_pe) > 0:
            # Select the top-ranked stock for PE
            best_pe_stock = df_ranked_pe.iloc[0]
            
            # Save the ranked list for PE with date
            df_ranked_pe.to_csv(os.path.join(self.data_dir, f"ranked_stocks_pe_{today_date}.csv"), index=False)
            
            # Create a detailed report for PE with date
            with open(os.path.join(self.data_dir, f"best_pe_stock_report_{today_date}.txt"), "w") as f:
                f.write(f"Best Stock for PE Options Trading (Falling): {best_pe_stock['symbol']}\n")
                f.write(f"Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"Current Price: {best_pe_stock['current_price']:.2f}\n")
                f.write(f"Pre-market Change: {best_pe_stock['pre_market_change']:.2f}%\n")
                f.write(f"Volume Ratio: {best_pe_stock['volume_ratio']:.2f}\n")
                f.write(f"Volatility: {best_pe_stock['volatility']:.2f}%\n")
                f.write(f"Gap Up/Down: {best_pe_stock['gap_up_down']:.2f}% (Low gap preferred)\n")
                f.write(f"Total Score: {best_pe_stock['total_score']:.4f}\n\n")
                f.write("Top 5 Stocks for PE:\n")
                for i in range(min(5, len(df_ranked_pe))):
                    stock = df_ranked_pe.iloc[i]
                    f.write(f"{i+1}. {stock['symbol']} - Score: {stock['total_score']:.4f}, Change: {stock['pre_market_change']:.2f}%, Gap: {stock['gap_up_down']:.2f}%\n")
            
            logger.info(f"Selected {best_pe_stock['symbol']} as the best stock for PE options trading")
        
        logger.info(f"Total processing time: {time.time() - start_time:.2f} seconds")
        
        return best_ce_stock['symbol'] if best_ce_stock is not None else None, best_pe_stock['symbol'] if best_pe_stock is not None else None

if __name__ == "__main__":
    print("=" * 50)
    print("Intraday Stock Selector for Options Trading")
    print("=" * 50)
    
    # Define today_date here
    today_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    selector = IntradayStockSelector()
    
    # Run immediately without time check
    print("Running stock selection...")
    best_ce_stock, best_pe_stock = selector.select_best_stocks()
    
    if best_ce_stock or best_pe_stock:
        if best_ce_stock:
            print(f"\n✅ Best stock for CE options trading (Rising): {best_ce_stock}")
            print(f"Detailed report saved in: {os.path.join(selector.data_dir, f'best_ce_stock_report_{today_date}.txt')}")
        
        if best_pe_stock:
            print(f"\n✅ Best stock for PE options trading (Falling): {best_pe_stock}")
            print(f"Detailed report saved in: {os.path.join(selector.data_dir, f'best_pe_stock_report_{today_date}.txt')}")
    else:
        print("\n❌ Failed to select stocks. Check the logs for details.")