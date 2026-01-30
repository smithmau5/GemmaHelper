import http.server
import socketserver
import webbrowser
import os
import sys
import threading
import time
import json
import requests
import datetime

PORT = 8501
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
HOME_DIR = os.path.expanduser("~")
GLOBAL_CONFIG_DIR = os.path.join(HOME_DIR, ".config", "gemma-bridge")
STATS_FILE = os.path.join(GLOBAL_CONFIG_DIR, "usage_stats.json")
HEALTH_API_URL = "http://localhost:11434/api/tags"
CIRCUIT_BREAKER_COOLDOWN = 300

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/dashboard.html')
            self.end_headers()
            return
        elif self.path == '/usage_stats.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            try:
                if os.path.exists(STATS_FILE):
                    with open(STATS_FILE, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    self.wfile.write(b'{}')
            except Exception as e:
                 print(f"Error serving stats: {e}")
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass

def ingest_legacy_logs(stats):
    legacy_file = os.path.expanduser("~/gemma_savings.log")
    if not os.path.exists(legacy_file):
        return False
    
    changed = False
    try:
        with open(legacy_file, "r") as f:
            lines = f.readlines()
            
        # Parse and merge
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Simple dedup based on raw line content stored in metadata or recreating the line
            # Better: Check matching timestamp + tokens
            try:
                # Format: Fri Jan 30 05:15:33 PM EST 2026: Saved 31 tokens (Gemma 1B) - Test Ping
                parts = line.split(": Saved ")
                if len(parts) < 2: continue
                
                date_str_raw = parts[0]
                rest = parts[1]
                
                # Extract tokens
                tokens_str = rest.split(" tokens")[0]
                tokens = int(tokens_str)
                
                # Extract Message
                if ") - " in rest:
                    message = rest.split(") - ")[1]
                else:
                    message = "Legacy Log Task"

                # Parse Date - Remove Timezone (EST/EDT)
                # "Fri Jan 30 05:15:33 PM EST 2026"
                d_tokens = date_str_raw.split()
                if len(d_tokens) == 7: # Has Timezone
                    d_tokens.pop(5) 
                
                clean_date = " ".join(d_tokens)
                dt = datetime.datetime.strptime(clean_date, "%a %b %d %I:%M:%S %p %Y")
                iso_time = dt.isoformat()
                
                # Check for duplicates in history
                is_duplicate = False
                for event in stats.get("history", []):
                    # Check if source is legacy match OR if timestamp is identical
                    # Since legacy log has 1-second precision, exact match on parsed time might fail if ISO has microseconds
                    # We check if ISO starts with the legacy time string (up to seconds)
                    if event.get("metadata", {}).get("original_line") == line:
                        is_duplicate = True
                        break
                    
                    # Also check fuzzy time match to avoid re-importing things that were migrated differently
                    event_dt = datetime.datetime.fromisoformat(event["timestamp"])
                    if abs((event_dt - dt).total_seconds()) < 2 and event["tokens"] == tokens and event["route"] == "local":
                         is_duplicate = True
                         break
                
                if not is_duplicate:
                    print(f"[*] Importing legacy log: {message}")
                    stats["history"].append({
                        "timestamp": iso_time,
                        "route": "local",
                        "tokens": tokens,
                        "latency": 0,
                        "prompt_preview": message,
                        "metadata": {
                            "source": "legacy_log_file",
                            "original_line": line
                        }
                    })
                    stats["total_local_tokens"] += tokens
                    changed = True
            except Exception as e:
                # print(f"Log Parse Error: {e}")
                pass
                
    except Exception as e:
        print(f"[!] Legacy Ingest Error: {e}")
        
    return changed

def watchdog_loop():
    print("[*] Watchdog: Proactive health monitoring started.")
    while True:
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, "r") as f:
                    stats = json.load(f)
                
                save_needed = False
                
                # 1. Legacy Log Ingestion
                if ingest_legacy_logs(stats):
                    save_needed = True

                current_health = stats.get("health", "Healthy")
                last_fail = stats.get("last_fail_time", 0)
                cooldown_elapsed = time.time() - last_fail
                
                # 2. Proactive Recovery Check
                if current_health in ["Degraded", "Retrying"]:
                    try:
                        # Heartbeat check
                        resp = requests.get(HEALTH_API_URL, timeout=3)
                        is_alive = resp.status_code == 200
                    except:
                        is_alive = False
                    
                    if is_alive and cooldown_elapsed > CIRCUIT_BREAKER_COOLDOWN:
                        print(f"[*] Watchdog: Service recovered. Resetting status to Healthy.")
                        stats["health"] = "Healthy"
                        stats["fail_count"] = 0
                        
                        # Add Event
                        stats["events"] = stats.get("events", [])
                        stats["events"].append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "level": "SUCCESS",
                            "message": "Watchdog: Local service heartbeat recovered. Auto-resetting circuit."
                        })
                        stats["events"] = stats["events"][-50:]
                        save_needed = True
                        
                    elif is_alive and current_health == "Degraded":
                        # If alive but still in cooldown, move to Half-Open/Retrying
                        print("[*] Watchdog: Service alive, waiting for cooldown.")
                        stats["health"] = "Retrying"
                        save_needed = True
                
                if save_needed:
                    stats["history"] = sorted(stats["history"], key=lambda x: x["timestamp"]) # Sort by time
                    with open(STATS_FILE, "w") as f:
                        json.dump(stats, f, indent=4)
            
        except Exception as e:
            print(f"[!] Watchdog Error: {e}")
            
        time.sleep(5)

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"[*] Bridge Monitor running at http://localhost:{PORT}")
            httpd.serve_forever()
    except OSError as e:
        print(f"[!] Error starting server: {e}")
        sys.exit(1)

def main():
    if not os.path.exists(STATS_FILE):
        print("[!] Warning: usage_stats.json not found.")

    # Start Watchdog
    threading.Thread(target=watchdog_loop, daemon=True).start()
    
    # Start Server
    threading.Thread(target=start_server, daemon=True).start()

    time.sleep(1)
    url = f"http://localhost:{PORT}/dashboard.html"
    print(f"[*] Opening {url}...")
    # webbrowser.open(url) # Uncomment for local use

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Stopping Bridge Monitor.")
        sys.exit(0)

if __name__ == "__main__":
    main()
