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
DIRECTORY = os.getcwd()
HOME_DIR = os.path.expanduser("~")
GLOBAL_CONFIG_DIR = os.path.join(HOME_DIR, ".config", "gemma-bridge")
STATS_FILE = os.path.join(GLOBAL_CONFIG_DIR, "usage_stats.json")
HEALTH_API_URL = "http://localhost:11434/api/tags"
CIRCUIT_BREAKER_COOLDOWN = 300

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        pass

def watchdog_loop():
    print("[*] Watchdog: Proactive health monitoring started.")
    while True:
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, "r") as f:
                    stats = json.load(f)
                
                current_health = stats.get("health", "Healthy")
                last_fail = stats.get("last_fail_time", 0)
                cooldown_elapsed = time.time() - last_fail
                
                # Proactive Recovery Check
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
                        
                        with open(STATS_FILE, "w") as f:
                            json.dump(stats, f, indent=4)
                    elif is_alive and current_health == "Degraded":
                        # If alive but still in cooldown, move to Half-Open/Retrying
                        print("[*] Watchdog: Service alive, waiting for cooldown.")
                        stats["health"] = "Retrying"
                        with open(STATS_FILE, "w") as f:
                            json.dump(stats, f, indent=4)
            
        except Exception as e:
            print(f"[!] Watchdog Error: {e}")
            
        time.sleep(10)

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
