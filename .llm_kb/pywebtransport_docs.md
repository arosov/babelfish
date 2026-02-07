Directory structure:
└── wtransport-pywebtransport/
    ├── README.md
    └── docs/
        ├── index.md
        └── api-reference/
            ├── client.md
            ├── config.md
            ├── connection.md
            ├── constants.md
            ├── events.md
            ├── exceptions.md
            ├── index.md
            ├── manager.md
            ├── messaging.md
            ├── serializer.md
            ├── server.md
            ├── session.md
            ├── stream.md
            ├── types.md
            └── utils.md

================================================
FILE: README.md
================================================
<div align="center">
  <img
    src="https://raw.githubusercontent.com/wtransport/pywebtransport/main/docs/assets/favicon.svg"
    alt="PyWebTransport Logo"
    width="100"
  />

# PyWebTransport

_An async-native WebTransport stack for Python_

  <br />

[![PyPI version](https://badge.fury.io/py/pywebtransport.svg)](https://pypi.org/project/pywebtransport/)
[![Python Version](https://img.shields.io/pypi/pyversions/pywebtransport)](https://pypi.org/project/pywebtransport/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/wtransport/pywebtransport/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/wtransport/pywebtransport/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wtransport/pywebtransport/branch/main/graph/badge.svg)](https://codecov.io/gh/wtransport/pywebtransport)
[![Docs](https://app.readthedocs.org/projects/pywebtransport/badge/?version=latest)](https://python.wtransport.org/)

</div>

## Features

- **Sans-I/O Architecture**: Powered by an ownership-driven Rust state machine decoupled from the I/O runtime.
- **Transport Primitives**: Full implementation of bidirectional streams, unidirectional streams, and unreliable datagrams.
- **Structured Concurrency**: Deterministic lifecycle management for connections and streams via asynchronous context managers.
- **Zero-Copy I/O**: End-to-end support for buffer protocols and `memoryview` to minimize data copying overhead.
- **Typed Messaging**: Integrated transmission of Python objects via pluggable serializers (`JSON`, `MsgPack`, `Protobuf`).
- **Application Framework**: Includes `ServerApp` with routing and middleware, plus a composable client suite for connection resilience and fleet management.

## Installation

```bash
pip install pywebtransport
```

## Quick Start

### Server

```python
import asyncio

from pywebtransport import Event, ServerApp, ServerConfig, WebTransportSession, WebTransportStream
from pywebtransport.types import EventType
from pywebtransport.utils import generate_self_signed_cert

generate_self_signed_cert(hostname="localhost")

app = ServerApp(config=ServerConfig(certfile="localhost.crt", keyfile="localhost.key"))


@app.route(path="/")
async def echo_handler(session: WebTransportSession) -> None:
    async def on_datagram(event: Event) -> None:
        if isinstance(event.data, dict) and (data := event.data.get("data")):
            await session.send_datagram(data=b"ECHO: " + data)

    async def on_stream(event: Event) -> None:
        if isinstance(event.data, dict) and (stream := event.data.get("stream")):
            if isinstance(stream, WebTransportStream):
                asyncio.create_task(handle_stream(stream))

    session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=on_datagram)
    session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)

    try:
        await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
    finally:
        session.events.off(event_type=EventType.DATAGRAM_RECEIVED, handler=on_datagram)
        session.events.off(event_type=EventType.STREAM_OPENED, handler=on_stream)


async def handle_stream(stream: WebTransportStream) -> None:
    try:
        data = await stream.read_all()
        await stream.write_all(data=b"ECHO: " + data, end_stream=True)
    except Exception:
        pass


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=4433)
```

### Client

```python
import asyncio
import ssl

from pywebtransport import ClientConfig, WebTransportClient
from pywebtransport.types import EventType


async def main() -> None:
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    async with WebTransportClient(config=config) as client:
        session = await client.connect(url="https://127.0.0.1:4433/")

        await session.send_datagram(data=b"Hello, Datagram!")

        event = await session.events.wait_for(event_type=EventType.DATAGRAM_RECEIVED)
        if isinstance(event.data, dict) and (data := event.data.get("data")):
            print(f"Datagram: {data!r}")

        stream = await session.create_bidirectional_stream()
        await stream.write_all(data=b"Hello, Stream!", end_stream=True)

        response = await stream.read_all()
        print(f"Stream: {response!r}")

        await session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

## Interoperability

**Infrastructure**

- [**Public Instance**](https://interop.wtransport.org): `https://interop.wtransport.org`, _Native Dual-Stack_
- [**Container Image**](https://github.com/wtransport/pywebtransport/pkgs/container/interop-server): `ghcr.io/wtransport/interop-server:latest`, _UDP Port 4433_

**Endpoints**

- **/echo**: Bidirectional stream and datagram reflection.
- **/stats**: Current session statistics and negotiated parameters.
- **/status**: Global server health and aggregate metrics.

## Sponsors

<div>
  <br />
  <a href="https://www.fastly.com/" target="_blank" rel="noopener noreferrer">
    <img
      src="https://raw.githubusercontent.com/wtransport/pywebtransport/main/docs/assets/sponsor-fastly.svg"
      alt="Fastly"
      width="110"
    />
  </a>
</div>

## License

Distributed under the terms of the Apache License 2.0. See [`LICENSE`](https://github.com/wtransport/pywebtransport/blob/main/LICENSE) for details.



================================================
FILE: docs/index.md
================================================
---
hide:
  - navigation
  - toc
---

<div style="text-align: center">
  <h1>
    <img src="assets/favicon.svg" alt="PyWebTransport" width="120" />
  </h1>
  <p>
    <em>An async-native WebTransport stack for Python</em>
  </p>
</div>

---

## Overview

**PyWebTransport** implements the WebTransport protocol over QUIC and HTTP/3. It provides a deterministic state machine for streams and datagrams, alongside a high-level application framework designed for standards compliance and strict concurrency safety.

## Features

- **Sans-I/O Architecture**: Powered by an ownership-driven Rust state machine decoupled from the I/O runtime.
- **Transport Primitives**: Full implementation of bidirectional streams, unidirectional streams, and unreliable datagrams.
- **Structured Concurrency**: Deterministic lifecycle management for connections and streams via asynchronous context managers.
- **Zero-Copy I/O**: End-to-end support for buffer protocols and `memoryview` to minimize data copying overhead.
- **Typed Messaging**: Integrated transmission of Python objects via pluggable serializers (`JSON`, `MsgPack`, `Protobuf`).
- **Application Framework**: Includes `ServerApp` with routing and middleware, plus a composable client suite for connection resilience and fleet management.

## Interoperability

**Infrastructure**

- [**Public Instance**](https://interop.wtransport.org): `https://interop.wtransport.org`, _Native Dual-Stack_
- [**Container Image**](https://github.com/wtransport/pywebtransport/pkgs/container/interop-server): `ghcr.io/wtransport/interop-server:latest`, _UDP Port 4433_

**Endpoints**

- **/echo**: Bidirectional stream and datagram reflection.
- **/stats**: Current session statistics and negotiated parameters.
- **/status**: Global server health and aggregate metrics.

## API Reference

- [**Full Reference**](api-reference/index.md): Comprehensive documentation organized into the **Application Framework**, **Transport Layer**, and **Shared Primitives**.

## Community

- [**GitHub**](https://github.com/wtransport/pywebtransport): Source code and issue tracker.
- [**PyPI**](https://pypi.org/project/pywebtransport/): Package distribution.

## License

Distributed under the terms of the Apache License 2.0. See [`LICENSE`](https://github.com/wtransport/pywebtransport/blob/main/LICENSE) for details.



================================================
FILE: docs/api-reference/client.md
================================================
# Client API

::: pywebtransport.client.client
::: pywebtransport.client.reconnecting
::: pywebtransport.client.fleet



================================================
FILE: docs/api-reference/config.md
================================================
# Configuration API

::: pywebtransport.config



================================================
FILE: docs/api-reference/connection.md
================================================
# Connection API

::: pywebtransport.connection



================================================
FILE: docs/api-reference/constants.md
================================================
# Constants API

::: pywebtransport.constants



================================================
FILE: docs/api-reference/events.md
================================================
# Events API

::: pywebtransport.events



================================================
FILE: docs/api-reference/exceptions.md
================================================
# Exceptions API

::: pywebtransport.exceptions



================================================
FILE: docs/api-reference/index.md
================================================
# API Reference

Technical reference for the PyWebTransport public interface.

## Overview

The API is organized into three **hierarchical layers**: the **Application Framework** for high-level integration, the **Transport Layer** for protocol state management, and **Shared Primitives** for data structures and configuration.

## Application Framework

High-level abstractions for application development, routing, and object-level transmission.

| Module                          | Description                                                     | Key Components                                              |
| :------------------------------ | :-------------------------------------------------------------- | :---------------------------------------------------------- |
| **[Client](client.md)**         | Client-side state orchestration and connectivity management.    | `WebTransportClient`, `ClientFleet`, `ReconnectingClient`   |
| **[Server](server.md)**         | Server-side application logic, request routing, and middleware. | `ServerApp`, `WebTransportServer`, `RequestRouter`          |
| **[Messaging](messaging.md)**   | Typed object transmission over streams and datagrams.           | `StructuredStream`, `StructuredDatagramTransport`           |
| **[Serializer](serializer.md)** | Pluggable serialization protocols for typed messaging.          | `JSONSerializer`, `MsgPackSerializer`, `ProtobufSerializer` |

## Transport Layer

Low-level components managing the WebTransport protocol state machine, lifecycle, and I/O boundaries.

| Module                          | Description                                                | Key Components                                                              |
| :------------------------------ | :--------------------------------------------------------- | :-------------------------------------------------------------------------- |
| **[Session](session.md)**       | WebTransport session lifecycle and multiplexing control.   | `WebTransportSession`                                                       |
| **[Stream](stream.md)**         | Bidirectional and unidirectional stream I/O primitives.    | `WebTransportStream`, `WebTransportSendStream`, `WebTransportReceiveStream` |
| **[Connection](connection.md)** | Underlying QUIC connection state and transport parameters. | `WebTransportConnection`                                                    |
| **[Manager](manager.md)**       | Resource lifecycle management and concurrency control.     | `ConnectionManager`, `SessionManager`                                       |

## Shared Primitives

Cross-cutting types, exceptions, and configuration data classes used throughout the stack.

| Module                          | Description                                                  | Key Components                          |
| :------------------------------ | :----------------------------------------------------------- | :-------------------------------------- |
| **[Configuration](config.md)**  | Immutable configuration data classes for endpoints.          | `ClientConfig`, `ServerConfig`          |
| **[Events](events.md)**         | Asynchronous event emission primitives.                      | `EventEmitter`, `Event`, `EventHandler` |
| **[Types](types.md)**           | Type aliases, protocols, and enumerations.                   | `StreamId`, `SessionId`, `StreamState`  |
| **[Exceptions](exceptions.md)** | Protocol error hierarchy and exception handling.             | `WebTransportError`, `StreamError`      |
| **[Constants](constants.md)**   | Protocol constants, error codes, and default values.         | `ErrorCodes`                            |
| **[Utils](utils.md)**           | Auxiliary utilities for timing and operational measurements. | `Timer`                                 |



================================================
FILE: docs/api-reference/manager.md
================================================
# Manager API

::: pywebtransport.manager.connection
::: pywebtransport.manager.session



================================================
FILE: docs/api-reference/messaging.md
================================================
# Messaging API

::: pywebtransport.messaging.datagram
::: pywebtransport.messaging.stream



================================================
FILE: docs/api-reference/serializer.md
================================================
# Serializer API

::: pywebtransport.serializer.json
::: pywebtransport.serializer.msgpack
::: pywebtransport.serializer.protobuf



================================================
FILE: docs/api-reference/server.md
================================================
# Server API

::: pywebtransport.server


================================================
FILE: docs/api-reference/session.md
================================================
# Session API

::: pywebtransport.session



================================================
FILE: docs/api-reference/stream.md
================================================
# Stream API

::: pywebtransport.stream



================================================
FILE: docs/api-reference/types.md
================================================
# Types API

::: pywebtransport.types



================================================
FILE: docs/api-reference/utils.md
================================================
# Utils API

::: pywebtransport.utils
::: pywebtransport.client.utils


