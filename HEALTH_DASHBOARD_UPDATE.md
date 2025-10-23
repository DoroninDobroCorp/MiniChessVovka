# Health Dashboard Status Logic Update

## Summary
Updated the health dashboard logic to properly reflect RED/GREEN status based on time window, process state, and activity.

## Files Modified
1. **`check_training_health.sh`** - Health check script
2. **`training_dashboard.sh`** - Live dashboard script

## New Status Logic

### RED Status (Problem/Error States)
1. **Process running outside working hours (2-10 AM UTC)**
   - Status: `✗ PROBLEM - Process running outside working hours`
   - Reason: AI should not be consuming resources outside the designated window

2. **Process not running during working hours**
   - Status: `✗ PROBLEM - Process should be running during working hours`
   - Reason: AI should be actively training during the 2-10 AM UTC window

3. **Process inactive for >10 minutes during working hours**
   - Status: `✗ PROBLEM - Process inactive for Xs (>10 min threshold)`
   - Reason: Process is running but not responding/updating (hung/frozen)

### GREEN Status (Healthy States)
1. **Process active during working hours**
   - Status: `✓ HEALTHY - Process active during working hours`
   - Condition: Within 2-10 AM UTC AND process running AND last update <10 min ago

2. **Process stopped outside working hours**
   - Status: `✓ HEALTHY - Process correctly stopped outside working hours`
   - Condition: Outside 2-10 AM UTC AND process not running

## Implementation Details

### Activity Detection
- **Health File**: `/srv/MiniChessVovka/training.health`
- **Activity Threshold**: 600 seconds (10 minutes)
- **Logic**: Compares current timestamp with health file timestamp

### Process Detection
1. Checks PID file: `/srv/MiniChessVovka/training.pid`
2. Verifies process is running: `ps -p $pid`
3. Fallback: Searches for `scheduled_self_play.py` processes

### Status Display Structure
```
╔════════════════════════════════════════════════════════════════╗
║                    OVERALL HEALTH STATUS                       ║
╚════════════════════════════════════════════════════════════════╝

  ✓/✗ [STATUS MESSAGE]

🕐 TIME WINDOW:
  Current Time: [UTC timestamp]
  Working Hours: 02:00-10:00 UTC (8-hour window)
  [Within/Outside working hours message]
  [Next availability countdown]

📊 PROCESS STATUS/DETAILS:
  [Detailed process information]
  [CPU/Memory usage if running]
  [Activity status with timestamp]
```

## Testing Results

### Current Test (2025-10-23 07:55 UTC)
- **Time Window**: Within working hours (2-10 AM UTC) ✓
- **Process State**: Not running
- **Expected Status**: RED (✗)
- **Actual Status**: RED (✗) - ✓ CORRECT
- **Message**: "PROBLEM - Process should be running during working hours"

### Status Logic Matrix

| Time Window | Process Running | Process Active | Status | Message |
|-------------|----------------|----------------|--------|---------|
| 2-10 AM UTC | Yes | Yes (<10min) | 🟢 GREEN | HEALTHY - Active during working hours |
| 2-10 AM UTC | Yes | No (>10min) | 🔴 RED | PROBLEM - Inactive for Xs |
| 2-10 AM UTC | No | N/A | 🔴 RED | PROBLEM - Should be running |
| Outside 2-10 AM | No | N/A | 🟢 GREEN | HEALTHY - Correctly stopped |
| Outside 2-10 AM | Yes | Any | 🔴 RED | PROBLEM - Running outside hours |

## Benefits
1. **Clear Problem Detection**: Immediately shows when something is wrong
2. **Context-Aware Status**: Different expectations for different time windows
3. **Activity Monitoring**: Detects hung/frozen processes during working hours
4. **Resource Management**: Alerts if process is running when it shouldn't be

## Usage

### View Health Status
```bash
./check_training_health.sh
```

### View Live Dashboard
```bash
./training_dashboard.sh
```

---
*Last Updated: 2025-10-23*
*Status: Implementation complete and tested ✓*
