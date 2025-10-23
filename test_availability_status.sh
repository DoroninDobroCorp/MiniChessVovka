#!/bin/bash
# Test script to verify AI availability status logic at different times

# Function to check if current time is in AI training window (2 AM - 10 AM UTC)
is_training_time() {
    local test_hour=$1
    [ "$test_hour" -ge 2 ] && [ "$test_hour" -lt 10 ]
}

# Function to get next availability window
get_next_availability() {
    local test_hour=$1
    
    if [ "$test_hour" -lt 2 ]; then
        echo "Available in $((2 - test_hour)) hours (at 02:00 UTC)"
    elif [ "$test_hour" -ge 10 ]; then
        echo "Available in $((24 - test_hour + 2)) hours (at 02:00 UTC tomorrow)"
    else
        echo "Available now until 10:00 UTC (in $((10 - test_hour)) hours)"
    fi
}

echo "================================"
echo "AI Availability Status Test"
echo "================================"
echo ""
echo "Testing time checking logic for all 24 hours:"
echo ""

for hour in {0..23}; do
    printf "Hour %02d:00 UTC - " "$hour"
    
    if is_training_time "$hour"; then
        echo "✓ AVAILABLE - $(get_next_availability $hour)"
    else
        echo "✗ OFFLINE - $(get_next_availability $hour)"
    fi
done

echo ""
echo "================================"
echo "Current Real Time Test:"
echo "================================"
current_hour=$(date -u +%H | sed 's/^0*//')
[ -z "$current_hour" ] && current_hour=0
current_time=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

echo "Current Time: $current_time"
echo "Current Hour: $current_hour"
echo "Working Hours: 02:00-10:00 UTC"
echo ""

if is_training_time "$current_hour"; then
    echo "Status: ✓ AI IS AVAILABLE"
    echo "$(get_next_availability $current_hour)"
else
    echo "Status: ✗ AI IS OFFLINE"
    echo "$(get_next_availability $current_hour)"
fi

echo ""
echo "================================"
echo "Expected Behavior:"
echo "================================"
echo "  Hours 02-09: AI AVAILABLE"
echo "  Hours 00-01, 10-23: AI OFFLINE"
echo ""
