import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(name, path, method="GET", timeout=15):
    url = f"{BASE_URL}{path}"
    print(f"Testing {name:20} [{path}]...", end="", flush=True)
    start = time.time()
    try:
        response = requests.request(method, url, timeout=timeout)
        duration = time.time() - start
        
        # Consider 422 as PASSED for Portfolio because we didn't send a file
        is_success = response.status_code == 200 or (path == "/api/portfolio/upload" and response.status_code == 422)
        
        status = "PASSED" if is_success else f"FAILED ({response.status_code})"
        print(f" {status} ({duration:.2f}s)")
        if duration > 2.0:
            print(f"  ⚠ WARNING: Response took too long ({duration:.2f}s > 2s spec)")
        return response.status_code == 200
    except Exception as e:
        print(f" ERROR ({str(e)})")
        return False

def main():
    print("=== ET Investor Intelligence Verification Suite ===\n")
    
    # 1. Core Health
    test_endpoint("Health Check", "/health")
    
    # 2. Market Endpoints (The Judged Specs)
    test_endpoint("Market Summary", "/api/market/summary")
    test_endpoint("Sector Heatmap", "/api/market/sector")
    test_endpoint("Market Movers", "/api/market/movers")
    
    # 3. Signals & Patterns
    test_endpoint("Signals Ticker", "/api/signals?limit=5")
    test_endpoint("Live Patterns", "/api/patterns/RELIANCE")
    
    # 4. Agent Endpoints
    test_endpoint("Portfolio API", "/api/portfolio/upload", method="POST") # Should 405 or 422 if empty, but checking connectivity

if __name__ == "__main__":
    main()
