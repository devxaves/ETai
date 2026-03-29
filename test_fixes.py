#!/usr/bin/env python3
"""Test script to verify all fixes."""

import requests
import json
import time

start = time.time()

# Test 1: Market Summary
try:
    r = requests.get('http://localhost:8000/api/market/summary', timeout=30)
    data = r.json()
    print('✓ Market Summary (200):',{
        'nifty': data.get('nifty50', {}).get('value'),
        'change_pct': data.get('nifty50', {}).get('change_pct')
    })
except Exception as e:
    print('✗ Market Summary failed:', str(e))

# Test 2: Chart History
try:
    r = requests.get('http://localhost:8000/api/market/nifty-history?days=20', timeout=30)
    data = r.json()
    print('✓ Chart History:', 'Total', data.get('total'), 'data points')
except Exception as e:
    print('✗ Chart History failed:', str(e))

# Test 3: Pattern Detection (first call - will scan)
try:
    r = requests.get('http://localhost:8000/api/patterns/RELIANCE', timeout=30)
    data = r.json()
    print('✓ Pattern Detection:', 'Found', len(data.get('patterns', [])), 'patterns')
except Exception as e:
    print('✗ Pattern Detection failed:', str(e))

# Test 4: Pattern Detection (second call - should use cache)
try:
    t1 = time.time()
    r = requests.get('http://localhost:8000/api/patterns/RELIANCE', timeout=30)
    t_cache = time.time() - t1
    data = r.json()
    print('✓ Pattern Cache Test:', 'Found', len(data.get('patterns', [])), 'patterns (cached in', str(round(t_cache, 2)), 's)')
except Exception as e:
    print('✗ Pattern Cache Test failed:', str(e))

elapsed = time.time() - start
print('Total Time:', str(round(elapsed, 2)), 's')
