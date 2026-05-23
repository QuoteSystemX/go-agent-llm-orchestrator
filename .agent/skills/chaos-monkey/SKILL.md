# Chaos Monkey Injection Skill (Master Level)

This skill defines the operational manual, CLI execution flags, and safety guidelines for actively injecting synthetic faults and simulating real-world disasters in sandbox environments.

---

## 🎯 Primary Goal
Identify single points of failure, verify reconnect behaviors, and ensure graceful degradation of agent interactions and backend services.

---

## 🛠️ CLI Flag Reference & Failure Scenarios

You can invoke `.agent/scripts/chaos/chaos_monkey.py` with specific flags to target different components of the workspace.

| Flag | Target Failure | Simulated Disaster | Recovery Expectation |
| :--- | :--- | :--- | :--- |
| `--mcp` | **MCP Server Connection** | Crashes the main MCP server process or blocks TCP port. | Agent must automatically buffer tasks and attempt reconnect within 3 attempts. |
| `--bus` | **Context Bus Integrity** | Inject invalid JSON or conflicting values into `.agent/bus/`. | The context parser must reject corrupt packets and fall back to the last valid snapshot. |
| `--latency` | **Response Delay** | Spikes request round-trip time by 5,000ms. | API handlers must trigger custom timeouts instead of hanging indefinitely. |
| `--cpu` | **CPU Resource Exhaust** | Spikes CPU load to 95% on local sandbox cores. | Task schedulers must dynamically throttle parallel jobs. |
| `--memory` | **Memory Leak** | Allocates unmanaged buffers to exhaust RAM. | Process monitors must trigger grace restarts before OOM killer. |

---

## 💻 Concrete Command Execution Examples

> [!IMPORTANT]
> **Safety Rule**: Fault injection is restricted to local sandboxes. Never run chaos commands in staging or production environments. Always verify `CHAOS_ENABLED=1` is set.

### Example 1: Simulating an MCP Port Crash
```bash
# Set environment flag and run fault injection
export CHAOS_ENABLED=1
python3 .agent/scripts/chaos/chaos_monkey.py --mcp
```
#### Expected Terminal Output:
```text
🔥 Chaos Monkey: Active!
🔥 Attack target: MCP Server (Port 8080)
🔥 Action: Injecting connection block on local loopback interface.
🔥 Status: Port 8080 is blocked. Simulated downtime: 15s.
📊 Triggering Chaos Analyzer...
```

### Example 2: Corrupting the Context Bus
```bash
# Inject invalid structures into active task bus
export CHAOS_ENABLED=1
python3 .agent/scripts/chaos/chaos_monkey.py --bus --corruption-rate=0.5
```
#### Expected Terminal Output:
```text
🦠 Chaos Monkey: Corrupting task payloads...
🦠 Action: Overwrote active_tasks.json with malformed headers.
🦠 Status: 3 bus items corrupted.
📊 Running validation checks...
```
