#!/usr/bin/env python3
"""
Real-time dashboard for monitoring Madrox network status.
Tails the debug log and shows live instance states.
"""

import json
import time
from pathlib import Path
from datetime import datetime

def clear_screen():
    """Clear terminal screen."""
    print("\033[2J\033[H", end="")

def print_dashboard():
    """Print live dashboard from monitoring history."""
    clear_screen()

    print("=" * 100)
    print(f"  MADROX NETWORK MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)

    # Check if history file exists
    history_file = Path("network_monitor_history.json")

    if not history_file.exists():
        print("\n  Waiting for monitoring data... (file not yet created)")
        return

    try:
        with open(history_file) as f:
            history = json.load(f)

        if not history:
            print("\n  Waiting for first status snapshot...")
            return

        # Get latest snapshot
        latest = history[-1]

        print(f"\n  Last Update: {latest['timestamp']}")
        print(f"  Total Snapshots: {len(history)}")
        print(f"  Active Instances: {len(latest['instances'])}")
        print("\n" + "-" * 100)

        # Print instance table
        print(f"\n  {'Instance':<25} {'Role':<20} {'State':<12} {'Uptime':<10} {'Msgs':<8} {'Parent':<20}")
        print("  " + "-" * 95)

        for inst in sorted(latest['instances'], key=lambda x: x['name']):
            name = inst['name'][:24]
            role = inst['role'][:19] if inst['role'] else "N/A"
            state = inst['state']
            uptime = f"{inst['uptime_seconds']}s"
            msgs = str(inst['message_count'])
            parent = inst['parent_id'][:19] if inst['parent_id'] else "-"

            # Color code states
            if state == 'idle':
                state_display = f"\033[93m{state}\033[0m"  # Yellow
            elif state == 'busy':
                state_display = f"\033[92m{state}\033[0m"  # Green
            elif state == 'error':
                state_display = f"\033[91m{state}\033[0m"  # Red
            else:
                state_display = state

            print(f"  {name:<25} {role:<20} {state_display:<20} {uptime:<10} {msgs:<8} {parent:<20}")

        # Check for stuck states
        print("\n" + "-" * 100)
        print("\n  ALERTS:")

        alerts = []
        for inst in latest['instances']:
            if inst['state'] == 'busy' and inst['uptime_seconds'] > 120:
                alerts.append(f"    ⚠️  {inst['name']} busy for {inst['uptime_seconds']}s - possible stuck state")

            if inst['state'] == 'idle' and inst['message_count'] == 0:
                alerts.append(f"    ⚠️  {inst['name']} idle with no messages processed")

            if inst['recent_output_count'] == 0 and inst['message_count'] > 0:
                alerts.append(f"    ⚠️  {inst['name']} has no recent output")

        if alerts:
            for alert in alerts:
                print(alert)
        else:
            print("    ✓ No alerts detected")

        # Show recent activity
        print("\n" + "-" * 100)
        print("\n  RECENT ACTIVITY:")

        for inst in latest['instances']:
            if inst['last_output']:
                output = inst['last_output']
                timestamp = output.get('timestamp', 'N/A')
                content = output.get('content', '')[:80]
                print(f"    {inst['name']}: [{timestamp}] {content}")

    except json.JSONDecodeError:
        print("\n  Error reading monitoring data (file being written)")
    except Exception as e:
        print(f"\n  Error: {e}")

    print("\n" + "=" * 100)
    print("  Press Ctrl+C to exit")
    print("=" * 100)

def main():
    """Main monitoring loop."""
    try:
        while True:
            print_dashboard()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

if __name__ == "__main__":
    main()
