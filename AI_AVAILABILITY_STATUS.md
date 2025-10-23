# MiniChessVovka AI Availability Status

## Summary

The health dashboards have been updated to display accurate AI availability information based on the time-based restrictions implemented in the codebase.

## Time-Based Restrictions

### Working Hours
- **Active Window:** 02:00 - 10:00 UTC (8-hour window)
- **Timezone:** UTC +0000
- **Implementation:** Python code in `ai.py`

### Code Location

**File:** `/srv/MiniChessVovka/ai.py`

**Function (Lines 66-69):**
```python
def is_training_time():
    """Check if current time is between 2 AM and 10 AM"""
    current_hour = datetime.now().hour
    return 2 <= current_hour < 10
```

**Enforcement (Lines 796-799):**
```python
if not is_training_time():
    current_time = datetime.now().strftime('%H:%M')
    print(f"AI is outside training hours (2 AM - 10 AM). Current time: {current_time}")
    return None if return_top_n == 1 else []
```

## Updated Dashboard Files

### 1. `training_dashboard.sh`
- Added real-time AI availability status display
- Shows current UTC time
- Indicates working hours (02:00-10:00 UTC)
- Displays availability status with visual indicators
- Shows time remaining or time until next availability

### 2. `check_training_health.sh`
- Added AI availability section at the top of health check
- Color-coded status indicators:
  - Green: AI AVAILABLE
  - Red: AI OFFLINE
- Shows next availability window with countdown

## Test Results

### Test Scripts Created

1. **`test_availability_status.sh`** - Bash time logic verification
2. **`test_ai_availability.py`** - Python ai.py function verification

### Test Output Summary

All tests **PASSED** ✓

**Bash Test Results:**
- Hours 00-01: ✗ OFFLINE (correct)
- Hours 02-09: ✓ AVAILABLE (correct)
- Hours 10-23: ✗ OFFLINE (correct)

**Python Test Results:**
- All 24 hours tested against expected behavior: ✓ PASS
- Current time (07:46 UTC): ✓ AVAILABLE (correct)
- Time remaining: 3 hours until 10:00 UTC (correct)

## Dashboard Features

### Real-Time Information
- Current UTC time display
- AI availability status indicator
- Working hours reference (02:00-10:00 UTC)
- Time-to-availability countdown

### Status Indicators
- **✓ AI AVAILABLE**: Within working hours (02:00-10:00 UTC)
- **✗ AI OFFLINE**: Outside working hours

### Availability Messages
When **AVAILABLE**:
- "Available now until 10:00 UTC (in X hours)"

When **OFFLINE** (before 02:00):
- "Available in X hours (at 02:00 UTC)"

When **OFFLINE** (after 10:00):
- "Available in X hours (at 02:00 UTC tomorrow)"

## Usage

### View Live Dashboard
```bash
./training_dashboard.sh
```

### Check Health Status
```bash
./check_training_health.sh
```

### Run Tests
```bash
# Test bash time logic
./test_availability_status.sh

# Test Python ai.py function
python3 test_ai_availability.py
```

## Time Conversion Reference

**UTC Working Hours:** 02:00 - 10:00

| Timezone | Working Hours |
|----------|--------------|
| UTC | 02:00 - 10:00 |
| PST (UTC-8) | 18:00 - 02:00 (prev day) |
| PDT (UTC-7) | 19:00 - 03:00 (prev day) |
| EST (UTC-5) | 21:00 - 05:00 (prev day) |
| EDT (UTC-4) | 22:00 - 06:00 (prev day) |
| CET (UTC+1) | 03:00 - 11:00 |
| JST (UTC+9) | 11:00 - 19:00 |

## Implementation Notes

1. **Server Timezone:** The server runs in UTC (Etc/UTC)
2. **Python Implementation:** Uses `datetime.now().hour` to check local server time
3. **Consistency:** Both dashboard scripts use identical logic to Python code
4. **Testing:** Comprehensive tests verify accuracy across all 24 hours
5. **Visual Feedback:** Color-coded indicators and clear status messages

## Verification

Current system verification (2025-10-23 07:46 UTC):
- ✓ Server timezone: UTC +0000
- ✓ Current hour: 7 (within 2-10 range)
- ✓ AI Status: AVAILABLE
- ✓ Remaining time: 3 hours
- ✓ Dashboard display: Accurate
- ✓ All tests: PASSED

---
*Last Updated: 2025-10-23*
*Status: All dashboards updated and tested ✓*
