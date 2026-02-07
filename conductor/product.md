# Initial Concept

The name of this project is babelfish. It's going to be a local backend server for a speech to text system wide solution with a Kotlin frontend (Kotlin being out of this scope).\nThis project is going to use Python since most of the libraries we're going to use are python wrappers for native libraries / engines.\nThe plan is to build an audio to text pipeline with top of the line techniques and opensource software.\nVAD -> tiny STT + Shadow STT -> LLM -> Text output All of that with real time progress on each step to be rendered by the frontend.\nThe one aspect of the code architecture I want to stress is that quite a few elements of the pipelines may be optional or have multiple altenatives (like nvdia / amd / cpu accell).\nThe other aspect that's important to me is that, at the end of the line, I'd like this backend to be usable in a simple uv one liner (in part for distribution purposes).

# Product Definition - Babelfish

## Vision
Babelfish is a high-performance, local backend server designed to power system-wide speech-to-text (STT) solutions, inspired by products like **BetterDictation**. It focuses on extreme low-latency, high accuracy, and fast streaming by orchestrating a modular pipeline centered around NVIDIA's Parakeet TDT.

## Target Audience
- **Power Users:** Seeking a private, ultra-low-latency alternative to cloud STT for real-time dictation.
- **App Developers:** Specifically designed as the engine for a Kotlin-based frontend, provided as a background service.

## Phased Implementation Plan
1.  **Phase 1: Streaming Foundation:** Implementing a robust single-pass pipeline using `parakeet-stream` for industry-leading latency.
2.  **Phase 2: Two-Pass Refinement:** Adding a second, high-accuracy model pass to refine the initial streaming output.
3.  **Phase 3: LLM Optimization:** Integrating a local low-latency LLM to provide context-aware text correction and optimization.

## Core Goals
- **Top-of-the-Line Latency:** Prioritizing `parakeet-stream` (TDT) over Whisper for superior real-time performance.
- **Modular Pipeline Architecture:** A flexible "VAD -> STT (Single/Two-Pass) -> LLM" chain.
- **Service-Oriented Distribution:** Packaging the server for execution as a system service (Windows Service / Systemd) via a simple `uv` command.
- **Real-time Progress Reporting:** High-speed streaming of processing state via WebTransport.

## Key Features
- **NVIDIA Parakeet Integration:** Leveraging Parakeet TDT for various quality/latency presets.
- **Hardware Agnostic Discovery:** Primary focus on Windows and Linux with CUDA acceleration.
- **Effortless Lifecycle Management:** Designed to be started/stopped/restarted by a companion Kotlin frontend.