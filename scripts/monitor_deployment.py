#!/usr/bin/env python3
"""
Monitor Terraform deployment progress and send status updates
"""

import subprocess
import time
import re
from pathlib import Path

IMESSAGE_TOOL = Path.home() / ".local/bin/imessR"
LOG_FILE = Path("/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/logs/iteration91_apply.log")

def send_message(msg: str):
    """Send iMessage notification"""
    try:
        if IMESSAGE_TOOL.exists():
            subprocess.run([str(IMESSAGE_TOOL), msg], timeout=10, capture_output=True)
            print(f"📱 {msg}")
    except:
        pass

def get_progress():
    """Parse log file for progress"""
    if not LOG_FILE.exists():
        return None, 0, 0
    
    with open(LOG_FILE) as f:
        content = f.read()
    
    # Look for creation progress
    creating = len(re.findall(r"Creating\.\.\.", content))
    created = len(re.findall(r"Creation complete after", content))
    errors = len(re.findall(r"Error:", content))
    
    # Look for final summary
    if "Apply complete!" in content:
        match = re.search(r"Apply complete! Resources: (\d+) added", content)
        if match:
            return "complete", int(match.group(1)), errors
    
    return "in_progress", created, errors

def main():
    """Monitor deployment"""
    last_created = 0
    last_update_time = time.time()
    
    send_message("🔄 Monitoring deployment progress...")
    
    while True:
        status, created, errors = get_progress()
        
        if status == "complete":
            send_message(f"🎉 Deployment COMPLETE! {created} resources created, {errors} errors")
            break
        
        # Send update every 5 minutes or when significant progress is made
        now = time.time()
        if created > last_created + 50 or (now - last_update_time > 300 and created > last_created):
            send_message(f"⏳ Progress: {created}/619 resources created ({created*100//619}%), {errors} errors")
            last_created = created
            last_update_time = now
        
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
