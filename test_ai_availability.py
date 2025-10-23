#!/usr/bin/env python3
"""
Test script to verify AI availability time checking matches expected behavior
"""

from datetime import datetime
from unittest.mock import patch
import sys

# Import the is_training_time function from ai.py
sys.path.insert(0, '/srv/MiniChessVovka')
import ai

def test_all_hours():
    """Test is_training_time() for all 24 hours"""
    
    print("=" * 60)
    print("AI Availability Time Check Test (Python)")
    print("=" * 60)
    print()
    print("Testing ai.is_training_time() for all 24 hours:")
    print()
    
    expected_available = set(range(2, 10))  # Hours 2-9 (inclusive)
    
    for hour in range(24):
        # Create a mock datetime with specific hour
        mock_time = datetime(2025, 10, 23, hour, 0, 0)
        
        with patch('ai.datetime') as mock_datetime:
            mock_datetime.now.return_value = mock_time
            is_available = ai.is_training_time()
        
        expected = hour in expected_available
        status = "✓ AVAILABLE" if is_available else "✗ OFFLINE"
        match = "✓" if is_available == expected else "✗ MISMATCH!"
        
        print(f"Hour {hour:02d}:00 UTC - {status:15} {match}")
        
        if is_available != expected:
            print(f"  ERROR: Expected {expected}, got {is_available}")
            return False
    
    print()
    print("=" * 60)
    print("Current Real Time Test:")
    print("=" * 60)
    
    current_time = datetime.now()
    current_hour = current_time.hour
    is_available = ai.is_training_time()
    
    print(f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Current Hour: {current_hour}")
    print(f"Working Hours: 02:00-10:00 UTC")
    print()
    
    if is_available:
        print("Status: ✓ AI IS AVAILABLE")
        remaining = 10 - current_hour
        print(f"Available for {remaining} more hours (until 10:00 UTC)")
    else:
        print("Status: ✗ AI IS OFFLINE")
        if current_hour < 2:
            next_hours = 2 - current_hour
            print(f"Will be available in {next_hours} hours (at 02:00 UTC)")
        else:
            next_hours = 24 - current_hour + 2
            print(f"Will be available in {next_hours} hours (at 02:00 UTC tomorrow)")
    
    print()
    print("=" * 60)
    print("Expected Behavior:")
    print("=" * 60)
    print("  Hours 02-09: AI AVAILABLE")
    print("  Hours 00-01, 10-23: AI OFFLINE")
    print()
    print("✓ All tests passed! Time checking logic is correct.")
    print()
    
    return True

if __name__ == "__main__":
    try:
        success = test_all_hours()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
