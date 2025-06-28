import sys
import os

HIST_DIR = ".github/prompt-history/"
REFLECT_PREFIX = "reflection--"
missing = []

# Check for at least one session file
try:
    sessions = [f for f in os.listdir(HIST_DIR) if f.endswith(".md") and not f.startswith(REFLECT_PREFIX)]
except FileNotFoundError:
    print("ERROR: .github/prompt-history/ directory does not exist.")
    sys.exit(1)

if not sessions:
    print("ERROR: No prompt history session files found in .github/prompt-history/")
    sys.exit(1)

# For each session, check for corresponding reflection if feedback detected
for session in sessions:
    session_path = os.path.join(HIST_DIR, session)
    with open(session_path, encoding="utf-8") as f:
        content = f.read()
        if any(word in content.lower() for word in ["feedback", "frustrat", "repeat", "dissatisf"]):
            reflect_file = os.path.join(HIST_DIR, f"{REFLECT_PREFIX}{session}")
            if not os.path.exists(reflect_file):
                missing.append(reflect_file)

if missing:
    print("ERROR: Missing required reflection files:", *missing)
    sys.exit(1)