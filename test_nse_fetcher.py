import asyncio
import sys
import os

# Add the current directory to sys.path to allow imports
sys.path.append(os.getcwd())

async def test_nse_fetcher():
    try:
        from backend.data.nse_fetcher import get_live_quote, get_nifty50_quotes
        print("Import successful")
        
        print("Testing get_live_quote(^NSEI)...")
        quote = await get_live_quote("^NSEI")
        print(f"Quote: {quote}")
        
        print("Testing get_nifty50_quotes()...")
        quotes = await get_nifty50_quotes()
        print(f"Num quotes: {len(quotes)}")
        if quotes:
            print(f"First quote: {quotes[0]}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_nse_fetcher())
