# Specification - Track: push_config_on_connect_20260209

## Overview
This track implements a proactive configuration push from the Babelfish server to the client. Instead of waiting for a client request, the server will automatically send the full current configuration as soon as the client establishes its primary communication channel.

## Goals
- Improve frontend initialization speed by providing the "source of truth" configuration immediately.
- Ensure the client has the latest server-side hardware and pipeline settings without requiring an explicit polling request.

## Functional Requirements
- **Trigger:** The server must monitor for the first client-initiated bidirectional stream within a WebTransport session.
- **Push Logic:** Upon detection of this first stream, the server must immediately send the current configuration (JSON format, newline-delimited) as the first data chunk.
- **Exclusivity:** This automatic push only occurs once per session, specifically on the first bidirectional stream. Subsequent streams opened by the same client will not trigger additional pushes.
- **Message Format:** The message must follow the established format: `{"type": "config", "data": {...}, "restart_required": ...}
`.

## Non-Functional Requirements
- **Latency:** The push should happen with minimal delay after the stream is recognized.
- **Reliability:** The server must ensure the WebTransport stream is in a writable state before attempting the push.

## Acceptance Criteria
- [ ] A WebTransport client connecting to the server receives the full configuration JSON immediately after opening its first bidirectional stream.
- [ ] No explicit "get_config" command is required from the client to receive this initial data.
- [ ] Opening a second bidirectional stream in the same session does not result in a duplicate configuration push.
- [ ] Existing `update_config` and broadcast functionality remains unaffected.

## Out of Scope
- Pushing configuration on server-initiated unidirectional streams.
- Pushing configuration updates before a bidirectional stream is opened.
