# Initial Concept

The name of this project is babelfish. It's going to be a local backend server for a speech to text system wide solution with a Kotlin frontend (Kotlin being out of this scope).\nThis project is going to use Python since most of the libraries we're going to use are python wrappers for native libraries / engines.\nThe plan is to build an audio to text pipeline with top of the line techniques and opensource software.\nVAD -> tiny STT + Shadow STT -> LLM -> Text output All of that with real time progress on each step to be rendered by the frontend.\nThe one aspect of the code architecture I want to stress is that quite a few elements of the pipelines may be optional or have multiple altenatives (like nvdia / amd / cpu accell).\nThe other aspect that's important to me is that, at the end of the line, I'd like this backend to be usable in a simple uv one liner (in part for distribution purposes).

# Product Definition - Babelfish

## Vision
Babelfish is a high-performance, local backend server designed to power system-wide speech-to-text (STT) solutions. It bridges the gap between raw audio input and refined text output by orchestrating a sophisticated, modular pipeline of top-of-the-line open-source engines, all while maintaining a minimal footprint and maximum privacy.

## Target Audience
- **Individual Power Users:** Desktop users seeking a private, low-latency alternative to cloud-based STT.
- **Privacy-Conscious Developers:** Engineers building desktop integrations (like the Kotlin frontend) who require a reliable local bridge for speech processing.

## Core Goals
- **Modular Pipeline Architecture:** A flexible "VAD -> STT -> LLM" chain where every component is swappable or optional.
- **Real-time Progress Reporting:** Low-latency streaming of the processing state at every stage, allowing frontends to render partial results and pipeline status immediately.
- **Effortless Distribution:** Packaging the entire solution for execution via a simple `uv` one-liner, ensuring portability and ease of setup for end-users.

## Key Features
- **Hardware Agnostic Acceleration:** Built-in support for NVIDIA (CUDA), AMD (ROCm), and CPU execution, with automated discovery of available resources.
- **Dual STT Strategy:** Support for "Tiny STT" for immediate feedback alongside "Shadow STT" for high-accuracy refinement.
- **Transparent Configuration:** A centralized configuration system (YAML/TOML) that allows for explicit overrides of the automated discovery and pipeline behavior.
- **Local-First Design:** Zero external dependencies for core processing, ensuring data never leaves the user's machine.