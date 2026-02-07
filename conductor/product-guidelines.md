# Product Guidelines - Babelfish

## Development Philosophy
- **Modular Excellence:** Every component (VAD, STT, LLM) must adhere to a strict, standardized interface. Modularity is favored over micro-optimizations to allow for rapid engine swapping and hardware abstraction.
- **Server as the Brain:** The server is the authority on system state and configuration. It should proactively discover hardware, assess capabilities, and set sensible defaults. The UI is a view into the server's state, not the source of truth.
- **User-Centric Feedback:** Since the backend is a "headless" service for the user, the CLI output and logs are the primary user interface. They must be legible, actionable, and provide a clear sense of the system's "health."

## Technical Standards
- **Sensible Defaults & Auto-discovery:** The initialization block must autonomously identify the best GPU (by VRAM/capability) and default microphone. These defaults must be reported to the frontend but remain active unless explicitly overridden.
- **Standardized Messaging:** Real-time progress updates must follow a strict JSON schema to ensure the Kotlin frontend can reliably render state transitions across different pipeline configurations.
- **Hardware Abstraction:** Code should avoid hard-coding vendor-specific logic. Hardware acceleration (NVIDIA/AMD/CPU) should be handled through an abstraction layer that allows the core logic to remain hardware-agnostic.
- **Dependency Discipline:** As the project aims for `uv` one-liner distribution, dependencies must be carefully audited. Prefer lightweight wrappers and native libraries that can be easily bundled or auto-discovered.

## Documentation & Communication
- **Actionable Logs:** Log levels (INFO, WARN, ERROR) must be used strictly. INFO should track pipeline progress; WARN should indicate non-fatal issues (like hardware fallback); ERROR must provide a path to resolution.
- **API Transparency:** The boundary between the Python backend and the Kotlin frontend must be perfectly documented via OpenAPI/Swagger, with particular focus on the WebSocket/Streaming events.