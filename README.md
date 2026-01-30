# GemmaHelper: Hybrid Inference Bridge V3

A robust, self-healing bridge for Antigravity that routes routine tasks to local Gemma 3 models while falling back to Gemini Cloud for complex reasoning. Designed for 4-core / 8GB RAM Linux systems.

## Features
- **Smart Routing**: Classifies tasks (summarize/format vs. plan/architect) to save cloud tokens.
- **Self-Healing Watchdog**: Automatically restarts Ollama if the service hangs or times out.
- **Real-Time Dashboard**: Monitor token usage, inference speed (TPS), and system health events.
- **Circuit Breaker**: Prevents system lockup by falling back to Cloud if local latency spikes.

## Prerequisites
1. **Ollama**: The engine for local inference.
2. **Python 3.8+**: To run the router and monitor.
3. **Gemma 3 Models**: Optimized for local hardware.

## Quick Start

### 1. Install Ollama
If on Linux, run:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull the Models
The bridge is optimized for the **1B** model to preserve RAM, but can utilize **4B** for better local reasoning.
```bash
ollama pull gemma3:1b  # Fast, low RAM (Recommended for 8GB systems)
ollama pull gemma3:4b  # Smarter, higher resource cost
```

### 3. Install Python Dependencies
```bash
pip install requests
```

### 4. Run the Bridge Monitor
The monitor provides a visual dashboard and handles system recovery.
```bash
python3 bridge_monitor.py
```
View the dashboard at: `http://localhost:8501/dashboard.html`

## Configuration
The system is fully configurable via `antigravity_config.json`. You can adjust timeouts, endpoints, and routing rules without modifying code.

### Key Settings
- **`routing_rules`**: Define which keywords trigger local vs. cloud routing.
- **`inference.num_thread`**: Adjust CPU usage (Default: 2).
- **`inference.timeout_seconds`**: Set local timeout (Default: 25s).
- **`reliability`**: Configure circuit breaker sensitivity.

```json
{
    "routing_rules": {
        "local_keywords": ["summarize", "format", "check"],
        "cloud_keywords": ["reason", "plan", "design"]
    }
}
```

## Usage
The router can be called manually or used as an Antigravity plugin:
```bash
python3 ag_hybrid_router.py "Summarize this long list: [item1, item2...]"
```

### Unified Logging
To log external or internal cloud activity to the dashboard without routing:
```bash
python3 ag_hybrid_router.py --log-only "Internal prompt description" --metadata '{"source": "antigravity-internal"}'
```

## Maintenance
- **System Events**: Check the dashboard "Health Events" log to see when the Watchdog has performed self-healing.
- **Manual Reset**: If the system is stuck in "Degraded" mode, the Watchdog will auto-reset after 5 minutes once it detects a successful heartbeat.

## Maintaining Architecture (GEMINI.md)
The `GEMINI.md` file serves as the **Governance Layer** for Antigravity. It tells the AI exactly which tasks should be offloaded locally.
- **Update Rules**: If you add new local capabilities or change model endpoints, ensure `GEMINI.md` is updated so Antigravity knows to use them.
- **Context Maps**: Keep the "Usage Pattern" section updated with any new structural mapping strategies you develop.
