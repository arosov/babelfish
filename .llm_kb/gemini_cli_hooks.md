# Gemini CLI Hooks Knowledge Base

Hooks are scripts or programs that Gemini CLI executes at specific points in the agentic loop, acting as "middleware" to intercept and customize behavior without modifying the CLI's source code.

## 1. Overview
Hooks run synchronously within the agent loop. When a hook event fires, Gemini CLI waits for all matching hooks to complete before continuing.

### Key Capabilities
- **Add Context:** Inject information (e.g., git history, local docs) before the model processes a request.
- **Validate Actions:** Review tool arguments and block potentially dangerous operations.
- **Enforce Policies:** Implement security scanners and compliance checks automatically.
- **Log Interactions:** Track tool usage and model responses for auditing.
- **Optimize Behavior:** Dynamically filter available tools or adjust model parameters.

## 2. Hook Lifecycle Events
Hooks are triggered by specific events in the CLI lifecycle:

| Event | Timing | Impact | Use Case |
|-------|--------|--------|----------|
| `SessionStart` | Session begins (startup/resume) | Inject Context | Load environment, initialize resources |
| `SessionEnd` | Session ends (exit/clear) | Advisory | Cleanup, save state |
| `BeforeAgent` | After prompt, before planning | Block Turn/Context | Validate prompt, inject initial context |
| `AfterAgent` | Agent loop ends | Retry/Halt | Review output, force retry |
| `BeforeModel` | Before sending to LLM | Block Turn/Mock | Modify prompts, swap models, mock replies |
| `AfterModel` | After receiving LLM response | Block Turn/Redact | Redact sensitive info, log response |
| `BeforeToolSelection` | Before LLM selects tools | Filter Tools | Filter available tools for optimization |
| `BeforeTool` | Before a tool executes | Block Tool/Rewrite | Validate arguments, block risky ops |
| `AfterTool` | After a tool executes | Block Result/Context | Process results, run tests, hide output |
| `PreCompress` | Before context compression | Advisory | Save state before truncation |
| `Notification` | System notification occurs | Advisory | Forward alerts to desktop/logging |

## 3. Global Mechanics

### The "Golden Rule" of I/O
Hooks communicate via `stdin` (Input) and `stdout` (Output).
1. **Silence is Mandatory:** Scripts **must not** print plain text to `stdout`. Only the final JSON object is allowed. Any `echo` or `print` calls before the JSON will break parsing.
2. **Debug via Stderr:** Use `stderr` for all logging and debugging (e.g., `echo "log" >&2`). Gemini CLI captures `stderr` but does not parse it.
3. **Strict JSON:** If `stdout` contains non-JSON text, parsing fails and the CLI defaults to "Allow".

### Exit Codes
The exit code determines the high-level outcome:
- **0 (Success):** `stdout` is parsed as JSON. Preferred for all logic, including intentional blocks (e.g., `{"decision": "deny"}`).
- **2 (System Block):** Critical block. The target action is aborted immediately. `stderr` is used as the rejection reason.
- **Other:** Treated as a warning. Interaction proceeds with original parameters.

### Matchers
Filters determine which specific tools or triggers fire a hook:
- **Tool Events (`BeforeTool`, `AfterTool`):** Matchers are **Regular Expressions** (e.g., `"write_.*"`).
- **Lifecycle Events:** Matchers are **Exact Strings** (e.g., `"startup"`).
- **Wildcards:** `"*"` or `""` matches everything.

## 4. Configuration
Hooks are configured in `settings.json`. Configurations are merged in this order (highest priority first):
1. **Project Settings:** `.gemini/settings.json`
2. **User Settings:** `~/.gemini/settings.json`
3. **System Settings:** `/etc/gemini-cli/settings.json`
4. **Extensions:** Hooks bundled in installed extensions.

### Configuration Schema Example
```json
{
  "hooks": {
    "BeforeTool": [
      {
        "matcher": "write_file|replace",
        "hooks": [
          {
            "name": "security-check",
            "type": "command",
            "command": "$GEMINI_PROJECT_DIR/.gemini/hooks/security.sh",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

### Hook Fields
- `type`: Only `"command"` is currently supported.
- `command`: The shell command to execute.
- `name`: Identifies the hook in logs.
- `timeout`: Execution timeout in ms (default: 60000).
- `description`: Explains the hook's purpose.

## 5. Environment Variables
Hooks run with a sanitized environment containing:
- `GEMINI_PROJECT_DIR`: Absolute path to project root.
- `GEMINI_SESSION_ID`: Unique ID for the current session.
- `GEMINI_CWD`: Current working directory.

## 6. Security
- **Permissions:** Hooks run with user privileges.
- **Fingerprinting:** Gemini CLI fingerprints project-level hooks. If a hook's name or command changes (e.g., after `git pull`), it is treated as untrusted, and the user is warned before execution.
