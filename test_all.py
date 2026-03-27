"""
test_all.py — Comprehensive API test script for ET Investor Intelligence.
Calls every endpoint and prints results. Run with: python test_all.py
"""

import requests
import json
import time
import sys
import os

BASE_URL = os.getenv("API_URL", "http://localhost:8000")

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

passed = 0
failed = 0


def test(name: str, method: str, path: str, **kwargs):
    """Run a single API test."""
    global passed, failed
    url = f"{BASE_URL}{path}"
    timeout = kwargs.pop("timeout", 30)

    try:
        if method == "GET":
            resp = requests.get(url, timeout=timeout, **kwargs)
        elif method == "POST":
            resp = requests.post(url, timeout=timeout, **kwargs)
        elif method == "DELETE":
            resp = requests.delete(url, timeout=timeout, **kwargs)
        else:
            resp = requests.get(url, timeout=timeout, **kwargs)

        if resp.status_code < 400:
            print(f"  {GREEN}✓ PASS{RESET} [{resp.status_code}] {name}")
            passed += 1
            try:
                data = resp.json()
                # Print first 200 chars of response
                preview = json.dumps(data, indent=2)[:200]
                print(f"    └─ {preview}...")
            except Exception:
                print(f"    └─ (non-JSON response, {len(resp.content)} bytes)")
            return resp
        else:
            print(f"  {RED}✗ FAIL{RESET} [{resp.status_code}] {name}")
            print(f"    └─ {resp.text[:200]}")
            failed += 1
            return resp
    except requests.ConnectionError:
        print(f"  {RED}✗ FAIL{RESET} [CONN] {name} — Cannot connect to {url}")
        failed += 1
        return None
    except requests.Timeout:
        print(f"  {YELLOW}⚠ TIMEOUT{RESET} {name} — Request timed out after {timeout}s")
        failed += 1
        return None
    except Exception as e:
        print(f"  {RED}✗ ERROR{RESET} {name} — {e}")
        failed += 1
        return None


def main():
    global passed, failed

    print(f"\n{BOLD}╔══════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║  ET Investor Intelligence — Full API Test Suite      ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════════════╝{RESET}")
    print(f"\n  Target: {BASE_URL}\n")

    # ── Health ───────────────────────────────────────────────────────────
    print(f"\n{BOLD}── Health Checks ──{RESET}")
    test("Root endpoint", "GET", "/")
    test("Health check", "GET", "/health")

    # ── Market ───────────────────────────────────────────────────────────
    print(f"\n{BOLD}── Market Endpoints ──{RESET}")
    test("Market summary", "GET", "/api/market/summary", timeout=60)
    test("Market movers (top 5)", "GET", "/api/market/movers?top_n=5", timeout=60)
    test("Sector performance", "GET", "/api/market/sector", timeout=60)

    # ── Signals ──────────────────────────────────────────────────────────
    print(f"\n{BOLD}── Signal Endpoints ──{RESET}")
    test("Get signals (limit=5)", "GET", "/api/signals?limit=5")
    test("Live demo signals", "GET", "/api/signals/live-demo")
    resp = test("Trigger manual scan", "POST", "/api/signals/scan")
    if resp and resp.status_code == 200:
        job_id = resp.json().get("job_id")
        if job_id:
            time.sleep(2)
            test(f"Check scan status ({job_id[:8]}...)", "GET", f"/api/signals/scan/{job_id}")

    # ── Patterns ─────────────────────────────────────────────────────────
    print(f"\n{BOLD}── Pattern Endpoints ──{RESET}")
    test("Scan RELIANCE patterns", "GET", "/api/patterns/RELIANCE?days=60", timeout=60)
    test("Scan symbols (TCS,INFY)", "GET", "/api/patterns/scan?symbols=TCS,INFY", timeout=60)
    test("Nifty 50 patterns cache", "GET", "/api/patterns/nifty50", timeout=120)

    # ── Portfolio / Chat ─────────────────────────────────────────────────
    print(f"\n{BOLD}── Chat & Portfolio ──{RESET}")

    session_id = None
    # Upload sample CAMS file
    sample_csv = os.path.join(os.path.dirname(__file__), "sample_cams.csv")
    if os.path.exists(sample_csv):
        with open(sample_csv, "rb") as f:
            resp = test("Upload CAMS CSV", "POST", "/api/portfolio/upload",
                        files={"file": ("sample_cams.csv", f, "text/csv")}, timeout=60)
            if resp and resp.status_code == 200:
                session_id = resp.json().get("session_id")
                print(f"    └─ Session ID: {session_id}")
    else:
        print(f"  {YELLOW}⚠ SKIP{RESET} Sample CAMS file not found at {sample_csv}")

    # Chat (non-streaming)
    if session_id:
        test("Chat (non-streaming)", "POST", "/api/chat/simple",
             json={"session_id": session_id, "message": "Is my portfolio well diversified?", "history": []},
             timeout=60)
        test("Get session", "GET", f"/api/chat/session/{session_id}")

    # ── Video ────────────────────────────────────────────────────────────
    print(f"\n{BOLD}── Video Endpoints ──{RESET}")
    resp = test("Generate video (daily wrap)", "POST", "/api/video/generate",
                json={"type": "daily_wrap", "period": "today"})
    if resp and resp.status_code == 200:
        vid_job_id = resp.json().get("job_id")
        if vid_job_id:
            time.sleep(3)
            test(f"Video status ({vid_job_id[:8]}...)", "GET", f"/api/video/status/{vid_job_id}")

    # ── Cleanup ──────────────────────────────────────────────────────────
    if session_id:
        print(f"\n{BOLD}── Cleanup ──{RESET}")
        test("Delete chat session", "DELETE", f"/api/chat/session/{session_id}")

    # ── Results ──────────────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{BOLD}{'═' * 54}{RESET}")
    print(f"  Results: {GREEN}{passed} passed{RESET} / {RED}{failed} failed{RESET} / {total} total")
    if failed == 0:
        print(f"  {GREEN}{BOLD}🎉 ALL TESTS PASSED!{RESET}")
    else:
        print(f"  {YELLOW}⚠ Some tests failed — check connectivity and API keys{RESET}")
    print(f"{BOLD}{'═' * 54}{RESET}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
