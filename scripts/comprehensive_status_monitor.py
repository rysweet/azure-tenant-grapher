#!/usr/bin/env python3
"""
Comprehensive status monitor - tracks all autonomous operations
Reports progress every 5 minutes via iMessage
Runs forever until stopped
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

IMESSAGE_TOOL = Path.home() / ".local" / "bin" / "imessR"
PROJECT_ROOT = Path("/Users/ryan/src/msec/atg-0723/azure-tenant-grapher")
STATUS_FILE = PROJECT_ROOT / "demos" / "autonomous_loop_status.json"

def send_update(msg):
    """Send iMessage update"""
    try:
        if IMESSAGE_TOOL.exists():
            subprocess.run([str(IMESSAGE_TOOL), msg], timeout=10, capture_output=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent: {msg[:80]}...")
    except Exception as e:
        print(f"Failed to send update: {e}")

def get_process_count(pattern):
    """Count running processes matching pattern"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            timeout=5
        )
        return len(result.stdout.decode().strip().split('\n')) if result.stdout else 0
    except:
        return 0

def get_neo4j_counts():
    """Get resource counts from Neo4j"""
    try:
        from py2neo import Graph
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        if not neo4j_password:
            raise ValueError("NEO4J_PASSWORD environment variable is required")
        graph = Graph("bolt://localhost:7688", auth=("neo4j", neo4j_password))

        # Source count
        source_q = "MATCH (r:Resource) WHERE r.id CONTAINS '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/' RETURN count(r) as count"
        source_count = graph.run(source_q).data()[0]["count"]

        # Target count
        target_q = "MATCH (r:Resource) WHERE r.id CONTAINS '/subscriptions/c190c55a-9ab2-4b1e-92c4-cc8b1a032285/' RETURN count(r) as count"
        target_count = graph.run(target_q).data()[0]["count"]

        return source_count, target_count
    except Exception as e:
        print(f"Neo4j query failed: {e}")
        return 0, 0

def main():
    print("=" * 80)
    print("COMPREHENSIVE STATUS MONITOR")
    print("=" * 80)
    print("Monitoring:")
    print("  - Autonomous replication loop")
    print("  - Terraform deployments")
    print("  - Neo4j scans")
    print("  - Graph fidelity")
    print("\nReporting every 5 minutes via iMessage")
    print("=" * 80 + "\n")

    start_time = time.time()
    iteration_count = 0
    last_report_time = time.time()

    while True:
        current_time = time.time()
        runtime_mins = int((current_time - start_time) / 60)

        # Load status
        if STATUS_FILE.exists():
            with open(STATUS_FILE) as f:
                status = json.load(f)
                iteration_count = status.get("last_iteration", 0)

        # Check process counts
        terraform_procs = get_process_count("terraform apply")
        scan_procs = get_process_count("atg scan")
        loop_procs = get_process_count("autonomous_replication_loop.py")

        # Get Neo4j counts
        source_count, target_count = get_neo4j_counts()

        # Calculate coverage
        coverage_pct = (target_count / max(source_count, 1)) * 100 if source_count > 0 else 0

        # Print status
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Status Update (Runtime: {runtime_mins}m)")
        print(f"  Iteration: {iteration_count}")
        print(f"  Processes: Loop={loop_procs}, Terraform={terraform_procs}, Scan={scan_procs}")
        print(f"  Neo4j: Source={source_count}, Target={target_count} ({coverage_pct:.1f}% coverage)")

        # Send periodic update
        if (current_time - last_report_time) >= 300:  # 5 minutes
            msg = f"🤖 Auto Loop Status ({runtime_mins}m runtime):\n"
            msg += f"• Iteration {iteration_count}\n"
            msg += f"• Terraform: {terraform_procs} active\n"
            msg += f"• Neo4j: {target_count}/{source_count} resources ({coverage_pct:.0f}%)\n"
            msg += f"• Loop: {'✓ Running' if loop_procs > 0 else '✗ Stopped'}"

            send_update(msg)
            last_report_time = current_time

        # Sleep before next check
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
