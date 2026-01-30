import sys
import json
import requests
import re
import datetime
import os
import time
import subprocess
import argparse

# Configuration Loader - Globalized
HOME_DIR = os.path.expanduser("~")
GLOBAL_CONFIG_DIR = os.path.join(HOME_DIR, ".config", "gemma-bridge")
CONFIG_FILE = os.path.join(GLOBAL_CONFIG_DIR, "antigravity_config.json")
STATS_FILE = os.path.join(GLOBAL_CONFIG_DIR, "usage_stats.json")

if not os.path.exists(GLOBAL_CONFIG_DIR):
    os.makedirs(GLOBAL_CONFIG_DIR)

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Error loading config: {e}. Using defaults.")
        return {}

CONFIG = load_config()
INFERENCE = CONFIG.get("inference", {})
RELIABILITY = CONFIG.get("reliability", {})
RULES = CONFIG.get("routing_rules", {})

LOCAL_API_URL = INFERENCE.get("local_endpoint", "http://localhost:11434/api/generate")
HEALTH_API_URL = INFERENCE.get("health_endpoint", "http://localhost:11434/api/tags")
LOCAL_MODEL = INFERENCE.get("local_model", "gemma3:1b")
LOCAL_TIMEOUT = INFERENCE.get("timeout_seconds", 25)
NUM_THREAD = INFERENCE.get("num_thread", 2)

CIRCUIT_BREAKER_FAIL_THRESHOLD = RELIABILITY.get("circuit_breaker_threshold", 2)
CIRCUIT_BREAKER_COOLDOWN = RELIABILITY.get("circuit_breaker_cooldown", 300)

# Moved to Configuration Loader section

def estimate_tokens(text):
    return len(text) // 4

def get_stats():
    default_stats = {
        "total_local_tokens": 0, 
        "total_cloud_tokens": 0, 
        "history": [],
        "health": "Healthy",
        "fail_count": 0,
        "last_fail_time": 0,
        "events": []
    }
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                stats = json.load(f)
                for key, val in default_stats.items():
                    if key not in stats:
                        stats[key] = val
                return stats
        except Exception:
            pass
    return default_stats

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=4)

def log_event(message, level="INFO"):
    stats = get_stats()
    stats["events"].append({
        "timestamp": datetime.datetime.now().isoformat(),
        "level": level,
        "message": message
    })
    stats["events"] = stats["events"][-50:]
    save_stats(stats)

def log_usage(prompt, response, route, latency=0, metadata=None):
    tokens = estimate_tokens(prompt + (response or ""))
    stats = get_stats()
    
    if route == "local" and response:
        stats["total_local_tokens"] += tokens
        stats["health"] = "Healthy"
        stats["fail_count"] = 0
    elif route == "cloud":
        stats["total_cloud_tokens"] += tokens
        
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "route": route,
        "tokens": tokens,
        "latency": round(latency, 2),
        "prompt_preview": prompt[:50] + "..." if len(prompt) > 50 else prompt
    }
    if metadata:
        entry["metadata"] = metadata
        
    stats["history"].append(entry)
    stats["history"] = stats["history"][-100:]
    save_stats(stats)

def check_ollama_alive():
    try:
        requests.get(HEALTH_API_URL, timeout=3)
        return True
    except:
        return False

def attempt_self_healing():
    print("[!!!] SELF-HEALING: Attempting to restart Ollama service...")
    log_event("Unresponsive service detected. Triggering self-healing restart.", "WARNING")
    try:
        # Generic restart for local Linux environments
        subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
        time.sleep(1)
        # Restarting in background
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_event("Ollama service restarted via shell execution.", "SUCCESS")
        print("[*] Recovery command sent. It may take 15-30s for the model to reload.")
    except Exception as e:
        log_event(f"Self-healing failed: {e}", "ERROR")

def classify_task(prompt):
    local_keywords = RULES.get("local_keywords", ["summariz", "format", "check", "lint"])
    cloud_keywords = RULES.get("cloud_keywords", ["reason", "plan", "design"])
    
    prompt_lower = prompt.lower()
    stats = get_stats()
    
    if stats["health"] == "Degraded":
        cooldown_elapsed = time.time() - stats["last_fail_time"]
        if cooldown_elapsed < CIRCUIT_BREAKER_COOLDOWN:
            return "cloud"
        else:
            log_event("Circuit breaker cooldown expired. Testing local service.", "INFO")
            stats["health"] = "Healthy"
            save_stats(stats)

    for kw in cloud_keywords:
        if re.search(kw, prompt_lower): return "cloud"
    for kw in local_keywords:
        if re.search(kw, prompt_lower): return "local"
    return "local"

def call_local_ollama(prompt):
    if not check_ollama_alive():
        print("[!] Local Service Offline. Starting fallback...")
        handle_local_failure(hard_crash=True)
        return None

    print(f"[*] Routing to LOCAL ({LOCAL_MODEL})...")
    start_time = time.time()
    try:
        response = requests.post(LOCAL_API_URL, json={
            "model": LOCAL_MODEL, "prompt": prompt, "stream": False,
            "options": {"num_thread": NUM_THREAD}
        }, timeout=LOCAL_TIMEOUT)
        response.raise_for_status()
        resp_text = response.json().get('response', '')
        latency = time.time() - start_time
        print(f"\n[LOCAL RESPONSE ({latency:.1f}s)]:\n{resp_text}")
        log_usage(prompt, resp_text, "local", latency)
        return resp_text
    except Exception as e:
        latency = time.time() - start_time
        print(f"[!] Local Request Failed ({latency:.1f}s): {e}")
        handle_local_failure()
        return None

def handle_local_failure(hard_crash=False):
    stats = get_stats()
    stats["fail_count"] += 1
    stats["last_fail_time"] = time.time()
    
    if hard_crash or stats["fail_count"] >= CIRCUIT_BREAKER_FAIL_THRESHOLD:
        stats["health"] = "Degraded"
        print("[!!!] CIRCUIT BREAKER TRIPPED. Triggering Watchdog...")
        attempt_self_healing()
    else:
        stats["health"] = "Retrying"
        log_event(f"Local request failed ({stats['fail_count']}/{CIRCUIT_BREAKER_FAIL_THRESHOLD})", "WARNING")
        
    save_stats(stats)

def call_cloud_gemini(prompt, metadata=None):
    print(f"[*] Routing to CLOUD (Gemini API)...")
    start_time = time.time()
    resp_text = f"processed via Gemini 1.5 Pro" # Mock
    latency = time.time() - start_time
    log_usage(prompt, resp_text, "cloud", latency, metadata)
    return resp_text

def main():
    parser = argparse.ArgumentParser(description="Antigravity Hybrid Router V3")
    parser.add_argument("prompt", nargs="*", help="The prompt to process")
    parser.add_argument("--log-only", action="store_true", help="Just log the usage to the dashboard without processing")
    parser.add_argument("--metadata", help="Optional JSON metadata for the log entry")
    parser.add_argument("--route", choices=["local", "cloud", "auto"], default="auto", help="Force a specific route (local/cloud) or auto-detect")
    
    args = parser.parse_args()
    prompt = " ".join(args.prompt)
    if not prompt: 
        return

    if args.log_only:
        meta = json.loads(args.metadata) if args.metadata else {"source": "antigravity"}
        
        # Determine route: Use explicit flag if set, otherwise default to 'cloud' for safety but warn?
        # Actually, for log-only, we should really default to 'cloud' if not specified to maintain current behavior,
        # OR use the 'auto' classification if they want.
        # But usually log-only implies the work is ALREADY DONE.
        
        actual_route = args.route
        if actual_route == "auto":
             # If they didn't specify, default to cloud for external logs as per previous behavior, 
             # UNLESS they want us to classify it? 
             # Let's assume 'cloud' default for legacy compatibility if strict route isn't provided.
             actual_route = "cloud"
        
        print(f"[*] Unified Logging: Recording {actual_route}-only event...")
        log_usage(prompt, "[External Process]", actual_route, 0, meta)
        return

    # Normal Processing Mode
    route = args.route if args.route != "auto" else classify_task(prompt)
    if route == "local":
        if call_local_ollama(prompt) is None:
            print("[*] Auto-Fallback: Retrying via Cloud...")
            call_cloud_gemini(prompt)
    else:
        call_cloud_gemini(prompt)

if __name__ == "__main__":
    main()
