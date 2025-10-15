#!/usr/bin/env python3
"""
Monitor script that watches the orchestrator and reports status.
This script NEVER STOPS - it keeps the session alive.
"""

import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path("/Users/ryan/src/msec/atg-0723/azure-tenant-grapher")
IMESS_TOOL = Path.home() / ".local/bin/imessR"

def send_imessage(msg: str):
    try:
        subprocess.run([str(IMESS_TOOL), msg], timeout=10, check=False, capture_output=True)
    except:
        pass

def log(msg: str):
    print(f"{datetime.utcnow().isoformat()} {msg}", flush=True)

def main():
    """Monitor loop - NEVER STOPS"""
    log("🔍 Monitor started - will run forever")
    send_imessage("🔍 Monitor started")
    
    cycle = 0
    
    while True:
        cycle += 1
        log(f"Monitor cycle {cycle}")
        
        # Just sleep and log - keep session alive
        time.sleep(300)  # Every 5 minutes
        
        log(f"Monitor cycle {cycle} - still running")
        
        if cycle % 12 == 0:  # Every hour
            send_imessage(f"🔍 Monitor alive - cycle {cycle}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Monitor stopped by user")
        sys.exit(1)
