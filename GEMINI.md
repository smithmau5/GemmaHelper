# Skill: Local-First Inference Bridge
> Purpose: Offload routine engineering tasks to local Gemma 3 via Ollama to conserve cloud tokens and reduce latency.

## Model Mapping
| Task Category | Primary Model | Endpoint |
| :--- | :--- | :--- |
| **Boilerplate/Scaffolding** | Gemma 3 (1B) | `http://localhost:11434` |
| **Log/Trace Summarization** | Gemma 3 (1B) | `http://localhost:11434` |
| **Code Formatting/Linting** | Gemma 3 (1B) | `http://localhost:11434` |
| **Unit Test Generation** | Gemma 3 (1B) | `http://localhost:11434` |
| **Architectural Planning** | Gemini 3 (Flash/Pro) | Cloud API |
| **Complex Debugging** | Gemini 3 (Flash/Pro) | Cloud API |

## Instructions for Antigravity
1. **Self-Triage:** For every sub-task, evaluate if it falls under the "Local" categories. If yes, you MUST attempt to use the local Ollama API first.
2. **Context Window Management:** Use Gemma 3's 128K context window for long file reads before sending a condensed summary to the cloud model.
3. **Fallback Protocol:** If the local Gemma response fails or is incoherent for three consecutive attempts, escalate the specific sub-task to Gemini Cloud.
4. **Token Budgeting:** For EVERY local task executed via Ollama, you MUST log the usage to update the dashboard by running:
   `python3 /home/flyinknut/Vibe_Projects/GemmaHelper/ag_hybrid_router.py "Task Summary" --log-only --metadata '{"source": "antigravity", "task_type": "local_inference"}'`
   (Do NOT write to log files manually).

## Usage Pattern
When preparing a multi-file refactor:
1. Use **Gemma** locally to read the files and create a structural map.
2. Pass only the **Map** to **Gemini** to decide on the refactoring logic.
3. Use **Gemma** locally to apply the repetitive changes and generate unit tests.
