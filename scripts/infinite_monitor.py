#!/usr/bin/env python3
"""
Infinite Monitoring Loop

This script runs forever, monitoring deployment and continuing work.
It will not stop until explicitly killed or the objective is achieved.
"""

import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone

IMESSAGE_TOOL = Path.home() / ".local/bin/imessR"
LOG_FILE = Path("/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/logs/iteration91_apply.log")

def send_message(msg: str):
    """Send iMessage"""
    try:
        if IMESSAGE_TOOL.exists():
            subprocess.run([str(IMESSAGE_TOOL), msg], timeout=10, capture_output=True)
    except:
        pass

def get_progress():
    """Get deployment progress"""
    if not LOG_FILE.exists():
        return "waiting", 0, 0
    
    with open(LOG_FILE) as f:
        content = f.read()
    
    import re
    created = len(re.findall(r"Creation complete", content))
    errors = len(re.findall(r"Error:", content))
    
    if "Apply complete!" in content:
        match = re.search(r"Apply complete! Resources: (\d+) added", content)
        if match:
            return "complete", int(match.group(1)), errors
    
    return "in_progress", created, errors

def main():
    """Main infinite loop"""
    print("🔄 Starting infinite monitoring loop...")
    send_message("🔄 Infinite monitoring loop started - will continue until objective achieved")
    
    last_created = 0
    last_update = time.time()
    cycle = 0
    
    while True:
        cycle += 1
        status, created, errors = get_progress()
        
        now = time.time()
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        
        print(f"[{timestamp}] Cycle {cycle}: {status}, {created} created, {errors} errors")
        
        # Send updates
        if status == "complete":
            send_message(f"🎉 DEPLOYMENT COMPLETE! {created} resources created. Proceeding to verification...")
            print("Deployment complete! Continuing to verification phase...")
            # Don't exit - continue to next phase
            time.sleep(300)  # Wait 5 minutes before checking if there's more work
            
        elif created > last_created + 50 or (now - last_update > 300 and created > last_created):
            percent = int(created * 100 / 619) if created < 619 else 100
            send_message(f"⏳ Progress: {created}/619 ({percent}%), {errors} errors")
            last_created = created
            last_update = now
        
        # Small sleep between checks
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
