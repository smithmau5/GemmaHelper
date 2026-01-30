import subprocess
import time

def test_router_local():
    print("TEST: Routing 'Summarize this' to LOCAL...")
    result = subprocess.run(
        ["python3", "ag_hybrid_router.py", "Summarize this log file for me."], 
        capture_output=True, text=True
    )
    if "Routing to LOCAL" in result.stdout:
        print("PASS: Correctly routed to LOCAL.")
    else:
        print(f"FAIL: Expected LOCAL, got:\n{result.stdout}")
        return False
        
    if "error calling Local Ollama" in result.stdout:
        print("FAIL: Local Ollama call failed (is the server running/model pulled?)")
        return False
        
    return True

def test_router_cloud():
    print("\nTEST: Routing 'Plan a microservices architecture' to CLOUD...")
    result = subprocess.run(
        ["python3", "ag_hybrid_router.py", "Plan a complex microservices architecture."], 
        capture_output=True, text=True
    )
    if "Routing to CLOUD" in result.stdout:
        print("PASS: Correctly routed to CLOUD.")
        return True
    else:
        print(f"FAIL: Expected CLOUD, got:\n{result.stdout}")
        return False

if __name__ == "__main__":
    print("=== Hybrid Router Verification ===")
    if test_router_local() and test_router_cloud():
        print("\n[SUCCESS] Bridge is ACTIVE and routing correctly.")
    else:
        print("\n[FAILURE] Verification failed.")
