Directory structure:
└── wtransport-pywebtransport/
    └── tests/
        ├── benchmark/
        │   ├── test_00_bench_server.py
        │   ├── test_01_throughput.py
        │   ├── test_02_latency.py
        │   ├── test_03_concurrency.py
        │   ├── test_04_datagrams.py
        │   └── test_05_resources.py
        ├── e2e/
        │   ├── __init__.py
        │   ├── test_00_e2e_server.py
        │   ├── test_01_basic_connection.py
        │   ├── test_02_simple_stream.py
        │   ├── test_03_concurrent_streams.py
        │   ├── test_04_data_transfer.py
        │   ├── test_05_datagrams.py
        │   ├── test_06_error_handling.py
        │   ├── test_07_advanced_features.py
        │   ├── test_08_structured_messaging.py
        │   └── test_e2e_suite.py
        ├── integration/
        │   ├── conftest.py
        │   ├── init.py
        │   ├── test_01_client_server_lifecycle.py
        │   ├── test_02_data_exchange.py
        │   ├── test_03_server_app_features.py
        │   └── test_04_resource_management_and_errors.py
        └── unit/
            ├── __init__.py
            ├── test_config.py
            ├── test_connection.py
            ├── test_constants.py
            ├── test_events.py
            ├── test_exceptions.py
            ├── test_session.py
            ├── test_stream.py
            ├── test_types.py
            ├── test_utils.py
            ├── _adapter/
            │   ├── __init__.py
            │   ├── test_base.py
            │   ├── test_client.py
            │   ├── test_pending.py
            │   ├── test_server.py
            │   └── test_utils.py
            ├── _protocol/
            │   ├── __init__.py
            │   └── test_events.py
            ├── client/
            │   ├── __init__.py
            │   ├── test_client.py
            │   ├── test_fleet.py
            │   ├── test_reconnecting.py
            │   └── test_utils.py
            ├── manager/
            │   ├── __init__.py
            │   ├── test_base.py
            │   ├── test_connection.py
            │   └── test_session.py
            ├── messaging/
            │   ├── __init__.py
            │   ├── test_datagram.py
            │   └── test_stream.py
            ├── serializer/
            │   ├── __init__.py
            │   ├── test_base.py
            │   ├── test_json.py
            │   ├── test_msgpack.py
            │   └── test_protobuf.py
            └── server/
                ├── __init__.py
                ├── test_app.py
                ├── test_cluster.py
                ├── test_middleware.py
                ├── test_router.py
                └── test_server.py

================================================
FILE: tests/benchmark/test_00_bench_server.py
================================================
"""High-performance Benchmark Server System Under Test."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Final

import uvloop

from pywebtransport import (
    ConnectionError,
    Event,
    ServerApp,
    ServerConfig,
    StreamError,
    WebTransportSession,
    WebTransportStream,
)
from pywebtransport.types import EventType
from pywebtransport.utils import generate_self_signed_cert

SERVER_HOST: Final[str] = "::"
SERVER_PORT: Final[int] = 4433
CERT_PATH: Final[Path] = Path("localhost.crt")
KEY_PATH: Final[Path] = Path("localhost.key")
CHUNK_SIZE: Final[int] = 65536
STATIC_VIEW: Final[memoryview] = memoryview(b"x" * (100 * 1024 * 1024))

logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger("bench_server")


class BenchmarkServerApp(ServerApp):

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._register_routes()

    async def handle_discard(self, session: WebTransportSession, **kwargs: Any) -> None:
        async def stream_drainer(*, stream: WebTransportStream) -> None:
            try:
                while await stream.read(max_bytes=CHUNK_SIZE):
                    pass
            except Exception:
                pass
            finally:
                if hasattr(stream, "close"):
                    await stream.close()

        async def on_stream(event: Event) -> None:
            if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                asyncio.create_task(coro=stream_drainer(stream=stream))

        async def on_dgram(event: Event) -> None:
            pass

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)
        session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=on_dgram)
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    async def handle_duplex(self, session: WebTransportSession, **kwargs: Any) -> None:
        async def stream_handler(*, stream: WebTransportStream) -> None:
            try:

                async def sender() -> None:
                    await stream.write_all(data=STATIC_VIEW[: 1024 * 1024], end_stream=False)
                    await stream.write(data=b"", end_stream=True)

                async def receiver() -> None:
                    while await stream.read(max_bytes=CHUNK_SIZE):
                        pass

                await asyncio.gather(sender(), receiver())
            except (ConnectionError, StreamError):
                pass
            except Exception:
                if not stream.is_closed:
                    await stream.close()

        async def on_stream(event: Event) -> None:
            if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                asyncio.create_task(coro=stream_handler(stream=stream))

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    async def handle_echo(self, session: WebTransportSession, **kwargs: Any) -> None:
        async def datagram_loop() -> None:
            async def on_dgram(event: Event) -> None:
                if isinstance(event.data, dict) and (data := event.data.get("data")):
                    try:
                        await session.send_datagram(data=data)
                    except Exception:
                        pass

            session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=on_dgram)

        async def stream_handler(*, stream: WebTransportStream) -> None:
            try:
                while True:
                    data = await stream.read(max_bytes=CHUNK_SIZE)
                    if not data:
                        break
                    await stream.write(data=data)

                await stream.write(data=b"", end_stream=True)
                await stream.read(max_bytes=1)

            except (ConnectionError, StreamError):
                pass
            except Exception:
                if not stream.is_closed:
                    await stream.close()

        async def stream_accept_loop() -> None:
            async def on_stream(event: Event) -> None:
                if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                    asyncio.create_task(coro=stream_handler(stream=stream))

            session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)

        t1 = asyncio.create_task(coro=datagram_loop())
        t2 = asyncio.create_task(coro=stream_accept_loop())

        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass
        finally:
            t1.cancel()
            t2.cancel()

    async def handle_latency(self, session: WebTransportSession, **kwargs: Any) -> None:
        async def stream_responder(*, stream: WebTransportStream) -> None:
            try:
                data = await stream.read_all()
                await stream.write_all(data=data, end_stream=True)
                await stream.read(max_bytes=1)
            except (ConnectionError, StreamError):
                pass
            except Exception:
                if not stream.is_closed:
                    await stream.close()

        async def on_stream(event: Event) -> None:
            if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                asyncio.create_task(coro=stream_responder(stream=stream))

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    async def handle_produce(self, session: WebTransportSession, **kwargs: Any) -> None:
        async def stream_producer(*, stream: WebTransportStream) -> None:
            try:
                cmd_bytes = await stream.read(max_bytes=128)
                try:
                    size_to_send = int(cmd_bytes)
                except ValueError:
                    return

                await stream.write_all(data=STATIC_VIEW[:size_to_send], end_stream=True)
                await stream.read(max_bytes=1)
            except (ConnectionError, StreamError):
                pass
            except Exception:
                if not stream.is_closed:
                    await stream.close()

        async def on_stream(event: Event) -> None:
            if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                asyncio.create_task(coro=stream_producer(stream=stream))

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    def _register_routes(self) -> None:
        self.route(path="/discard")(self.handle_discard)
        self.route(path="/duplex")(self.handle_duplex)
        self.route(path="/echo")(self.handle_echo)
        self.route(path="/latency")(self.handle_latency)
        self.route(path="/produce")(self.handle_produce)


async def main() -> None:
    if not CERT_PATH.exists() or not KEY_PATH.exists():
        generate_self_signed_cert(hostname="localhost", output_dir=".")

    config = ServerConfig(
        bind_host=SERVER_HOST,
        bind_port=SERVER_PORT,
        certfile=str(CERT_PATH),
        keyfile=str(KEY_PATH),
        max_connections=10000,
        max_sessions=10000,
        initial_max_data=100 * 1024 * 1024,
        initial_max_streams_bidi=10000,
        initial_max_streams_uni=10000,
        flow_control_window_size=100 * 1024 * 1024,
        max_stream_read_buffer=200 * 1024 * 1024,
        max_stream_write_buffer=200 * 1024 * 1024,
        max_event_queue_size=100000,
    )

    app = BenchmarkServerApp(config=config)

    async with app:
        await app.serve()


if __name__ == "__main__":
    try:
        uvloop.run(main())
    except KeyboardInterrupt:
        pass



================================================
FILE: tests/benchmark/test_01_throughput.py
================================================
"""Benchmark for Stream Throughput."""

import asyncio
import gc
import logging
import ssl
from collections.abc import Callable, Coroutine
from typing import Any, Final, cast

import pytest
import uvloop
from pytest_benchmark.fixture import BenchmarkFixture

from pywebtransport import ClientConfig, WebTransportClient, WebTransportSession

SERVER_URL_BASE: Final[str] = "https://127.0.0.1:4433"
WARMUP_ROUNDS: Final[int] = 5
PAYLOAD_SIZE: Final[int] = 1024 * 1024
STREAMS_PER_ROUND: Final[int] = 10
STATIC_VIEW: Final[memoryview] = memoryview(b"x" * PAYLOAD_SIZE)

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture(scope="module")
def client_config() -> ClientConfig:
    return ClientConfig(
        verify_mode=ssl.CERT_NONE,
        initial_max_data=100 * 1024 * 1024,
        initial_max_streams_bidi=1000,
        initial_max_streams_uni=1000,
        flow_control_window_size=100 * 1024 * 1024,
        max_stream_read_buffer=200 * 1024 * 1024,
        max_stream_write_buffer=200 * 1024 * 1024,
        max_event_queue_size=10000,
    )


class TestStreamThroughput:

    def test_upload_throughput(self, *, benchmark: BenchmarkFixture, client_config: ClientConfig) -> None:
        async def upload_worker(session: WebTransportSession) -> int:
            stream = await session.create_bidirectional_stream()
            await stream.write_all(data=STATIC_VIEW, end_stream=True)
            await stream.read_all()
            return PAYLOAD_SIZE

        self._run_benchmark_scenario(
            benchmark=benchmark,
            client_config=client_config,
            endpoint="/discard",
            stream_handler=upload_worker,
        )

    def test_download_throughput(self, *, benchmark: BenchmarkFixture, client_config: ClientConfig) -> None:
        cmd = str(PAYLOAD_SIZE).encode()

        async def download_worker(session: WebTransportSession) -> int:
            stream = await session.create_bidirectional_stream()
            await stream.write(data=cmd)
            received = 0
            while True:
                chunk = await stream.read(max_bytes=PAYLOAD_SIZE)
                if not chunk:
                    break
                received += len(chunk)
            await stream.close()
            return received

        self._run_benchmark_scenario(
            benchmark=benchmark,
            client_config=client_config,
            endpoint="/produce",
            stream_handler=download_worker,
        )

    def test_duplex_throughput(self, *, benchmark: BenchmarkFixture, client_config: ClientConfig) -> None:
        async def duplex_worker(session: WebTransportSession) -> int:
            stream = await session.create_bidirectional_stream()

            async def sender() -> int:
                await stream.write_all(data=STATIC_VIEW, end_stream=True)
                return PAYLOAD_SIZE

            async def receiver() -> int:
                received = 0
                while True:
                    chunk = await stream.read(max_bytes=PAYLOAD_SIZE)
                    if not chunk:
                        break
                    received += len(chunk)
                return received

            results = await asyncio.gather(sender(), receiver())
            await stream.close()
            return sum(results)

        self._run_benchmark_scenario(
            benchmark=benchmark,
            client_config=client_config,
            endpoint="/duplex",
            stream_handler=duplex_worker,
        )

    def _run_benchmark_scenario(
        self,
        *,
        benchmark: BenchmarkFixture,
        client_config: ClientConfig,
        endpoint: str,
        stream_handler: Callable[[WebTransportSession], Coroutine[Any, Any, int]],
    ) -> None:
        url = f"{SERVER_URL_BASE}{endpoint}"

        async def run_scenario() -> int:
            total_bytes = 0
            async with WebTransportClient(config=client_config) as client:
                session = await client.connect(url=url)
                tasks = [stream_handler(session) for _ in range(STREAMS_PER_ROUND)]
                results = await asyncio.gather(*tasks)
                total_bytes = sum(results)
                await session.close()
            return total_bytes

        for _ in range(WARMUP_ROUNDS):
            uvloop.run(run_scenario())
        gc.collect()

        result_bytes = benchmark(lambda: uvloop.run(run_scenario()))

        stats = cast(dict[str, Any], benchmark.stats)
        mean_time = stats["mean"]

        total_mb = result_bytes / (1024 * 1024)
        throughput = total_mb / mean_time if mean_time > 0 else 0
        benchmark.extra_info["throughput_mb_s"] = throughput



================================================
FILE: tests/benchmark/test_02_latency.py
================================================
"""Benchmark for Latency and RTT metrics."""

import asyncio
import gc
import logging
import ssl
from typing import Any, Final, cast

import pytest
import uvloop
from pytest_benchmark.fixture import BenchmarkFixture

from pywebtransport import ClientConfig, Event, WebTransportClient
from pywebtransport.types import EventType

SERVER_URL_BASE: Final[str] = "https://127.0.0.1:4433"
WARMUP_ROUNDS: Final[int] = 10
PAYLOAD_64B: Final[bytes] = b"x" * 64
PAYLOAD_1KB: Final[bytes] = b"x" * 1024

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture(scope="module")
def client_config() -> ClientConfig:
    return ClientConfig(verify_mode=ssl.CERT_NONE)


class TestLatency:

    def test_handshake_latency(self, *, benchmark: BenchmarkFixture, client_config: ClientConfig) -> None:
        url = f"{SERVER_URL_BASE}/latency"

        async def run_handshake() -> None:
            async with WebTransportClient(config=client_config) as client:
                session = await client.connect(url=url)
                await session.close()

        for _ in range(WARMUP_ROUNDS):
            uvloop.run(run_handshake())
        gc.collect()

        benchmark(lambda: uvloop.run(run_handshake()))

        stats = cast(dict[str, Any], benchmark.stats)
        benchmark.extra_info["median_ms"] = stats["median"] * 1000
        benchmark.extra_info["max_ms"] = stats["max"] * 1000
        benchmark.extra_info["min_ms"] = stats["min"] * 1000

    @pytest.mark.parametrize("payload,label", [(PAYLOAD_64B, "64b"), (PAYLOAD_1KB, "1kb")], ids=["64b", "1kb"])
    def test_request_response_latency(
        self, *, benchmark: BenchmarkFixture, client_config: ClientConfig, payload: bytes, label: str
    ) -> None:
        url = f"{SERVER_URL_BASE}/latency"

        async def run_req_res() -> None:
            async with WebTransportClient(config=client_config) as client:
                session = await client.connect(url=url)
                stream = await session.create_bidirectional_stream()
                await stream.write_all(data=payload, end_stream=True)
                await stream.read_all()
                await session.close()

        for _ in range(WARMUP_ROUNDS):
            uvloop.run(run_req_res())
        gc.collect()

        benchmark(lambda: uvloop.run(run_req_res()))

        stats = cast(dict[str, Any], benchmark.stats)
        benchmark.extra_info[f"req_res_{label}_median_ms"] = stats["median"] * 1000
        benchmark.extra_info[f"req_res_{label}_max_ms"] = stats["max"] * 1000
        benchmark.extra_info[f"req_res_{label}_min_ms"] = stats["min"] * 1000

    def test_datagram_rtt(self, *, benchmark: BenchmarkFixture, client_config: ClientConfig) -> None:
        url = f"{SERVER_URL_BASE}/echo"
        payload = PAYLOAD_64B

        async def run_dgram_rtt() -> None:
            async with WebTransportClient(config=client_config) as client:
                session = await client.connect(url=url)
                loop = asyncio.get_running_loop()
                echo_received = loop.create_future()

                async def on_dgram(event: Event) -> None:
                    if isinstance(event.data, dict):
                        data = event.data.get("data")
                        if data == payload:
                            if not echo_received.done():
                                echo_received.set_result(True)

                session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=on_dgram)
                await session.send_datagram(data=payload)
                await echo_received
                await session.close()

        for _ in range(WARMUP_ROUNDS):
            uvloop.run(run_dgram_rtt())
        gc.collect()

        benchmark(lambda: uvloop.run(run_dgram_rtt()))

        stats = cast(dict[str, Any], benchmark.stats)
        benchmark.extra_info["dgram_rtt_median_ms"] = stats["median"] * 1000
        benchmark.extra_info["dgram_rtt_max_ms"] = stats["max"] * 1000
        benchmark.extra_info["dgram_rtt_min_ms"] = stats["min"] * 1000



================================================
FILE: tests/benchmark/test_03_concurrency.py
================================================
"""Benchmark for Concurrency and Multiplexing."""

import asyncio
import gc
import logging
import ssl
from typing import Any, Final, cast

import pytest
import uvloop
from pytest_benchmark.fixture import BenchmarkFixture

from pywebtransport import ClientConfig, WebTransportClient

SERVER_URL_BASE: Final[str] = "https://127.0.0.1:4433"
WARMUP_ROUNDS: Final[int] = 3
CONCURRENT_STREAMS: Final[int] = 100
CONNECTION_COUNT: Final[int] = 50
PAYLOAD_SIZE: Final[int] = 64 * 1024
STATIC_VIEW: Final[memoryview] = memoryview(b"x" * PAYLOAD_SIZE)

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture(scope="module")
def client_config() -> ClientConfig:
    return ClientConfig(
        verify_mode=ssl.CERT_NONE,
        initial_max_data=1024 * 1024 * 1024,
        initial_max_streams_bidi=2000,
        initial_max_streams_uni=2000,
        flow_control_window_size=1024 * 1024 * 1024,
        max_event_queue_size=20000,
    )


class TestConcurrency:

    def test_multiplexing_rps(self, *, benchmark: BenchmarkFixture, client_config: ClientConfig) -> None:
        url = f"{SERVER_URL_BASE}/discard"

        async def run_multiplexing() -> None:
            async with WebTransportClient(config=client_config) as client:
                session = await client.connect(url=url)

                async def stream_worker() -> None:
                    stream = await session.create_bidirectional_stream()
                    await stream.write_all(data=STATIC_VIEW, end_stream=True)
                    await stream.read_all()
                    await stream.close()

                tasks = [asyncio.create_task(coro=stream_worker()) for _ in range(CONCURRENT_STREAMS)]
                await asyncio.gather(*tasks)

                await session.close()

        for _ in range(WARMUP_ROUNDS):
            uvloop.run(run_multiplexing())
        gc.collect()

        benchmark(lambda: uvloop.run(run_multiplexing()))

        stats = cast(dict[str, Any], benchmark.stats)
        mean_time = stats["mean"]

        rps = CONCURRENT_STREAMS / mean_time if mean_time > 0 else 0
        benchmark.extra_info["streams_per_second"] = rps

    def test_connection_rate(self, *, benchmark: BenchmarkFixture, client_config: ClientConfig) -> None:
        url = f"{SERVER_URL_BASE}/latency"

        async def run_concurrent_connections() -> None:
            async with WebTransportClient(config=client_config) as client:

                async def connect_worker() -> None:
                    session = await client.connect(url=url)
                    await session.close()

                tasks = [asyncio.create_task(coro=connect_worker()) for _ in range(CONNECTION_COUNT)]
                await asyncio.gather(*tasks)

        for _ in range(WARMUP_ROUNDS):
            uvloop.run(run_concurrent_connections())
        gc.collect()

        benchmark(lambda: uvloop.run(run_concurrent_connections()))

        stats = cast(dict[str, Any], benchmark.stats)
        mean_time = stats["mean"]
        rate = CONNECTION_COUNT / mean_time if mean_time > 0 else 0
        benchmark.extra_info["connections_per_second"] = rate



================================================
FILE: tests/benchmark/test_04_datagrams.py
================================================
"""Benchmark for Datagram Performance."""

import asyncio
import gc
import logging
import ssl
from typing import Any, Final, cast

import pytest
import uvloop
from pytest_benchmark.fixture import BenchmarkFixture

from pywebtransport import ClientConfig, WebTransportClient
from pywebtransport.types import Buffer

SERVER_URL_BASE: Final[str] = "https://127.0.0.1:4433"
WARMUP_ROUNDS: Final[int] = 5
BURST_COUNT: Final[int] = 10000
PAYLOAD_SIZE: Final[int] = 64
STATIC_VIEW_HEADER: Final[memoryview] = memoryview(b"H" * 4)
STATIC_VIEW_BODY: Final[memoryview] = memoryview(b"x" * (PAYLOAD_SIZE - 4))

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture(scope="module")
def client_config() -> ClientConfig:
    return ClientConfig(verify_mode=ssl.CERT_NONE)


class TestDatagramPerformance:

    def test_datagram_send_rate(self, *, benchmark: BenchmarkFixture, client_config: ClientConfig) -> None:
        url = f"{SERVER_URL_BASE}/discard"

        payload_scatter: list[Buffer] = [STATIC_VIEW_HEADER, STATIC_VIEW_BODY]

        async def run_burst() -> None:
            async with WebTransportClient(config=client_config) as client:
                session = await client.connect(url=url)
                tasks = [session.send_datagram(data=payload_scatter) for _ in range(BURST_COUNT)]
                await asyncio.gather(*tasks)
                await session.close()

        for _ in range(WARMUP_ROUNDS):
            uvloop.run(run_burst())
        gc.collect()

        benchmark(lambda: uvloop.run(run_burst()))

        stats = cast(dict[str, Any], benchmark.stats)
        mean_time = stats["mean"]
        pps = BURST_COUNT / mean_time if mean_time > 0 else 0
        benchmark.extra_info["send_rate_pps"] = pps



================================================
FILE: tests/benchmark/test_05_resources.py
================================================
"""Benchmark for Resource Utilization."""

import asyncio
import gc
import logging
import os
import ssl
from typing import Final

import psutil
import pytest
import uvloop
from pytest_benchmark.fixture import BenchmarkFixture

from pywebtransport import ClientConfig, WebTransportClient, WebTransportSession

SERVER_URL_BASE: Final[str] = "https://127.0.0.1:4433"
CONNECTION_COUNT: Final[int] = 1000
STABILIZATION_SECONDS: Final[float] = 5.0

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture(scope="module")
def client_config() -> ClientConfig:
    return ClientConfig(verify_mode=ssl.CERT_NONE, connect_timeout=60.0, max_connections=2000)


class TestResources:

    def test_idle_memory_footprint(self, *, benchmark: BenchmarkFixture, client_config: ClientConfig) -> None:
        url = f"{SERVER_URL_BASE}/latency"
        process = psutil.Process(os.getpid())

        def run_measurement() -> float:
            async def run_full_cycle() -> float:
                gc.collect()
                baseline_rss = float(process.memory_info().rss)

                sessions: list[WebTransportSession] = []

                async with WebTransportClient(config=client_config) as client:
                    try:
                        semaphore = asyncio.Semaphore(100)

                        async def connect_one() -> None:
                            async with semaphore:
                                session = await client.connect(url=url)
                                sessions.append(session)

                        tasks = [asyncio.create_task(connect_one()) for _ in range(CONNECTION_COUNT)]
                        await asyncio.gather(*tasks)

                        await asyncio.sleep(STABILIZATION_SECONDS)

                        gc.collect()

                        current_rss = float(process.memory_info().rss)
                        return max(0.0, current_rss - baseline_rss)

                    finally:
                        if sessions:
                            close_sem = asyncio.Semaphore(100)

                            async def close_one(s: WebTransportSession) -> None:
                                async with close_sem:
                                    if not s.is_closed:
                                        await s.close()

                            tasks = [asyncio.create_task(close_one(s)) for s in sessions]
                            await asyncio.gather(*tasks)

            return uvloop.run(run_full_cycle())

        memory_increase = benchmark.pedantic(
            target=run_measurement,
            iterations=1,
            rounds=1,
        )  # type: ignore[no-untyped-call]

        kb_per_connection = (memory_increase / 1024) / CONNECTION_COUNT
        benchmark.extra_info["memory_per_idle_connection_kb"] = kb_per_connection



================================================
FILE: tests/e2e/__init__.py
================================================
[Empty file]


================================================
FILE: tests/e2e/test_00_e2e_server.py
================================================
"""E2E test server for WebTransport streams and datagrams."""

import asyncio
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from pywebtransport import (
    ConnectionError,
    Event,
    ServerApp,
    ServerConfig,
    SessionError,
    StreamError,
    StructuredDatagramTransport,
    StructuredStream,
    TimeoutError,
    WebTransportReceiveStream,
    WebTransportSession,
    WebTransportStream,
)
from pywebtransport.constants import DEFAULT_MAX_MESSAGE_SIZE
from pywebtransport.serializer import JSONSerializer, MsgPackSerializer
from pywebtransport.types import ConnectionState, EventType, SessionState
from pywebtransport.utils import generate_self_signed_cert, get_timestamp

CERT_PATH: Final[Path] = Path("localhost.crt")
KEY_PATH: Final[Path] = Path("localhost.key")
DEBUG_MODE: Final[bool] = "--debug" in sys.argv
SERVER_HOST: Final[str] = "::"
SERVER_PORT: Final[int] = 4433
JSON_SERIALIZER = JSONSerializer()
MSGPACK_SERIALIZER = MsgPackSerializer()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)
    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)

logger = logging.getLogger("e2e_server")


@dataclass(kw_only=True)
class StatusUpdate:
    """Represents a status update message."""

    status: str
    timestamp: float


@dataclass(kw_only=True)
class UserData:
    """Represents user data structure."""

    id: int
    name: str
    email: str


class E2EServerApp(ServerApp):
    """E2E test server application with full test support."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the E2E server application."""
        super().__init__(**kwargs)
        self.server.on(event_type=EventType.CONNECTION_ESTABLISHED, handler=self._on_connection_established)
        self.server.on(event_type=EventType.SESSION_REQUEST, handler=self._on_session_request)
        self._register_handlers()
        logger.info("E2E Server initialized with full test support")

    async def _diagnostics_handler(self, session: WebTransportSession, **kwargs: Any) -> None:
        """Handle requests for server statistics on the /diagnostics path."""
        logger.info("Diagnostics request from session %s", session.session_id)
        stream: WebTransportStream | None = None
        try:
            stream_event = await session.events.wait_for(event_type=EventType.STREAM_OPENED, timeout=5.0)
            if not isinstance(stream_event.data, dict):
                logger.warning("Diagnostics handler: Received invalid stream event data.")
                return

            stream = stream_event.data.get("stream")
            if not isinstance(stream, WebTransportStream):
                logger.warning("Diagnostics handler: Client opened a non-bidirectional stream.")
                return

            diagnostics = await self.server.diagnostics()
            stats_json = json.dumps(asdict(diagnostics), indent=2).encode("utf-8")
            await stream.write(data=stats_json, end_stream=True)
            logger.info("Sent diagnostics: %s bytes", len(stats_json))
        except asyncio.TimeoutError:
            logger.error("Diagnostics handler: Client connected but never opened a stream.")
        except Exception as e:
            logger.error("Diagnostics handler error: %s", e)
        finally:
            if not session.is_closed:
                await session.close()

    async def _health_handler(self, session: WebTransportSession, **kwargs: Any) -> None:
        """Handle health check requests on the /health path."""
        logger.info("Health check from session %s", session.session_id)
        try:
            diagnostics = await self.server.diagnostics()
            stats = diagnostics.stats
            active_sessions = diagnostics.session_states.get(SessionState.CONNECTED, 0)
            active_connections = sum(v for k, v in diagnostics.connection_states.items() if k != ConnectionState.CLOSED)

            health_data = {
                "status": "healthy",
                "timestamp": time.time(),
                "uptime": (get_timestamp() - stats.start_time) if stats.start_time else 0.0,
                "active_sessions": active_sessions,
                "active_connections": active_connections,
            }
            await session.send_datagram(data=json.dumps(health_data).encode("utf-8"))
            logger.info("Sent health status: %s", health_data["status"])
        except Exception as e:
            logger.error("Health handler error: %s", e)
        finally:
            if not session.is_closed:
                await session.close()

    async def _on_connection_established(self, event: Any) -> None:
        """Handle connection established events."""
        logger.info("New connection established")

    async def _on_session_request(self, event: Any) -> None:
        """Handle session request events."""
        if isinstance(event.data, dict):
            session_id = event.data.get("session_id")
            path = event.data.get("path", "/")
            logger.info("Session request: %s for path '%s'", session_id, path)

    def _register_handlers(self) -> None:
        """Centralize registration for all server routes."""
        self.route(path="/")(echo_handler)
        self.route(path="/echo")(echo_handler)
        self.route(path="/health")(self._health_handler)
        self.route(path="/diagnostics")(self._diagnostics_handler)
        self.route(path="/structured-echo/json")(structured_echo_json_handler)
        self.route(path="/structured-echo/msgpack")(structured_echo_msgpack_handler)


MESSAGE_REGISTRY: dict[int, type[Any]] = {1: UserData, 2: StatusUpdate}


async def _structured_echo_base_handler(*, session: WebTransportSession, serializer: Any, serializer_name: str) -> None:
    """Provide the base handler logic for structured echo."""
    session_id = session.session_id
    logger.info("Structured handler started for session %s (%s)", session_id, serializer_name)

    try:
        s_stream_manager_task = asyncio.create_task(
            coro=handle_all_structured_streams(session=session, serializer=serializer)
        )
        s_datagram_task = asyncio.create_task(coro=handle_structured_datagram(session=session, serializer=serializer))
        await asyncio.gather(s_stream_manager_task, s_datagram_task, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Structured handler error for session %s: %s", session_id, e, exc_info=True)
    finally:
        logger.info("Structured handler finished for session %s", session_id)


async def echo_handler(session: WebTransportSession, **kwargs: Any) -> None:
    """Handle echoing streams and datagrams."""
    session_id = session.session_id
    logger.info("Handler started for session %s on path %s", session_id, session.path)

    try:
        datagram_task = asyncio.create_task(coro=handle_datagrams(session=session))
        stream_task = asyncio.create_task(coro=handle_incoming_streams(session=session))
        await asyncio.gather(datagram_task, stream_task, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Handler error for session %s: %s", session_id, e, exc_info=True)
    finally:
        logger.info("Handler finished for session %s", session_id)


async def handle_all_structured_streams(*, session: WebTransportSession, serializer: Any) -> None:
    """Listen for and handle all incoming streams for a structured session."""
    session_id = session.session_id

    async def stream_opened_handler(event: Event) -> None:
        if not isinstance(event.data, dict):
            return
        stream = event.data.get("stream")
        if isinstance(stream, WebTransportStream):
            asyncio.create_task(coro=handle_structured_stream(stream=stream, serializer=serializer))

    session.events.on(event_type=EventType.STREAM_OPENED, handler=stream_opened_handler)
    try:
        await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
    except (asyncio.CancelledError, ConnectionError):
        pass
    except Exception as e:
        logger.error("Structured stream manager for session %s error: %s", session_id, e, exc_info=True)
    finally:
        session.events.off(event_type=EventType.STREAM_OPENED, handler=stream_opened_handler)


async def handle_bidirectional_stream(*, stream: WebTransportStream) -> None:
    """Handle echo logic for a bidirectional stream."""
    try:
        request_data = await stream.read_all()
        echo_data = b"ECHO: " + request_data
        await stream.write_all(data=echo_data, end_stream=True)
    except (asyncio.CancelledError, ConnectionError, StreamError):
        pass
    except Exception as e:
        logger.error("Bidirectional stream %s error: %s", stream.stream_id, e, exc_info=True)
        await stream.close(error_code=1)


async def handle_datagrams(*, session: WebTransportSession) -> None:
    """Receive and echo datagrams for a session."""
    session_id = session.session_id
    logger.debug("Starting datagram handler for session %s", session_id)

    async def datagram_handler(event: Event) -> None:
        if not isinstance(event.data, dict):
            return
        data = event.data.get("data")
        if not isinstance(data, bytes):
            return

        try:
            echo_data = b"ECHO: " + data
            await session.send_datagram(data=echo_data)
        except (asyncio.CancelledError, ConnectionError, SessionError) as e:
            logger.warning("Datagram handler error for session %s: %s", session_id, e)

    session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=datagram_handler)
    try:
        await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
    except (asyncio.CancelledError, ConnectionError):
        pass
    except Exception as e:
        logger.error("Datagram handler error for session %s: %s", session_id, e, exc_info=True)
    finally:
        session.events.off(event_type=EventType.DATAGRAM_RECEIVED, handler=datagram_handler)


async def handle_incoming_streams(*, session: WebTransportSession) -> None:
    """Listen for and handle all incoming streams for a session."""
    session_id = session.session_id
    logger.debug("Starting stream handler for session %s", session_id)

    async def stream_opened_handler(event: Event) -> None:
        if not isinstance(event.data, dict):
            return
        stream = event.data.get("stream")
        if stream:
            asyncio.create_task(coro=handle_single_stream(stream=stream, session_id=session_id))

    session.events.on(event_type=EventType.STREAM_OPENED, handler=stream_opened_handler)
    try:
        await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
    except (asyncio.CancelledError, ConnectionError):
        pass
    except Exception as e:
        logger.error("Stream handler error for session %s: %s", session_id, e, exc_info=True)
    finally:
        session.events.off(event_type=EventType.STREAM_OPENED, handler=stream_opened_handler)


async def handle_receive_stream(*, stream: WebTransportReceiveStream) -> None:
    """Handle data from a receive-only stream."""
    try:
        await stream.read_all()
    except (asyncio.CancelledError, ConnectionError, StreamError):
        pass
    except Exception as e:
        logger.error("Receive stream %s error: %s", stream.stream_id, e, exc_info=True)


async def handle_single_stream(*, stream: Any, session_id: int) -> None:
    """Process a single stream based on its type."""
    stream_id = stream.stream_id

    try:
        if isinstance(stream, WebTransportStream):
            await handle_bidirectional_stream(stream=stream)
        elif isinstance(stream, WebTransportReceiveStream):
            await handle_receive_stream(stream=stream)
        else:
            logger.warning("Unknown stream type for %s", stream_id)
    except Exception as e:
        logger.error("Error processing stream %s: %s", stream_id, e, exc_info=True)
    finally:
        pass


async def handle_structured_datagram(*, session: WebTransportSession, serializer: Any) -> None:
    """Receive and echo structured datagrams for a session."""
    session_id = session.session_id
    logger.debug("Starting structured datagram handler for session %s", session_id)

    try:
        structured_datagram_transport = StructuredDatagramTransport(
            session=session, serializer=serializer, registry=MESSAGE_REGISTRY
        )
        structured_datagram_transport.initialize()

        while not session.is_closed:
            obj = await structured_datagram_transport.receive_obj()
            await structured_datagram_transport.send_obj(obj=obj)

    except (asyncio.CancelledError, ConnectionError, SessionError, TimeoutError):
        logger.debug("Structured datagram handler for session %s closing.", session_id)
    except Exception as e:
        logger.error("Structured datagram handler error for session %s: %s", session_id, e, exc_info=True)
    finally:
        logger.debug("Structured datagram handler for session %s finished.", session_id)


async def handle_structured_stream(*, stream: WebTransportStream, serializer: Any) -> None:
    """Handle echoing structured objects on a single, existing bidirectional stream."""
    raw_stream = stream
    stream_id = raw_stream.stream_id
    logger.debug("Handling structured stream %s", stream_id)

    try:
        structured_stream = StructuredStream(
            stream=raw_stream,
            serializer=serializer,
            registry=MESSAGE_REGISTRY,
            max_message_size=DEFAULT_MAX_MESSAGE_SIZE,
        )
        async for obj in structured_stream:
            logger.debug("Echoing object on stream %s: %s", stream_id, obj)
            await structured_stream.send_obj(obj=obj)
    except (asyncio.CancelledError, ConnectionError, StreamError):
        pass
    except Exception as e:
        logger.error("Structured stream %s error: %s", stream_id, e, exc_info=True)
    finally:
        if not raw_stream.is_closed:
            await raw_stream.close()


async def structured_echo_json_handler(session: WebTransportSession, **kwargs: Any) -> None:
    """Handle echoing structured objects using JSON."""
    await _structured_echo_base_handler(session=session, serializer=JSON_SERIALIZER, serializer_name="JSON")


async def structured_echo_msgpack_handler(session: WebTransportSession, **kwargs: Any) -> None:
    """Handle echoing structured objects using MsgPack."""
    await _structured_echo_base_handler(session=session, serializer=MSGPACK_SERIALIZER, serializer_name="MsgPack")


async def main() -> None:
    """Configure and start the WebTransport E2E test server."""
    logger.info("Starting WebTransport E2E Test Server...")

    if not CERT_PATH.exists() or not KEY_PATH.exists():
        logger.info("Generating self-signed certificate for %s...", CERT_PATH.stem)
        generate_self_signed_cert(hostname=CERT_PATH.stem, output_dir=".")

    config = ServerConfig(
        bind_host=SERVER_HOST,
        bind_port=SERVER_PORT,
        certfile=str(CERT_PATH),
        keyfile=str(KEY_PATH),
        log_level="DEBUG" if DEBUG_MODE else "INFO",
    )
    app = E2EServerApp(config=config)

    logger.info("Server binding to %s:%s", config.bind_host, config.bind_port)
    if DEBUG_MODE:
        logger.info("Debug mode enabled - verbose logging active")
    logger.info("Ready for E2E tests!")

    try:
        async with app:
            await app.serve()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped gracefully by user.")
    except Exception as e:
        logger.critical("Server crashed unexpectedly: %s", e, exc_info=True)
        sys.exit(1)



================================================
FILE: tests/e2e/test_01_basic_connection.py
================================================
"""E2E test for basic WebTransport connections."""

import asyncio
import logging
import socket
import ssl
import sys
import time
from typing import Final

from pywebtransport import ClientConfig, ConnectionError, TimeoutError, WebTransportClient
from pywebtransport.types import SessionState

SERVER_HOST: Final[str] = "127.0.0.1"
SERVER_PORT: Final[int] = 4433
SERVER_URL: Final[str] = f"https://{SERVER_HOST}:{SERVER_PORT}/"
DEBUG_MODE: Final[bool] = "--debug" in sys.argv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)
    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)

logger = logging.getLogger("test_basic_connection")


async def test_server_reachability() -> bool:
    """Perform a pre-check for server reachability via a simple UDP packet."""
    logger.info("Pre-check: Testing server reachability...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        try:
            sock.sendto(b"ping", (SERVER_HOST, SERVER_PORT))
            logger.info("Server port %s (UDP) is reachable.", SERVER_PORT)
            return True
        except socket.error as e:
            logger.warning("UDP probe failed: %s. This might be normal.", e)
            return True
        finally:
            sock.close()
    except Exception as e:
        logger.error("Reachability pre-check failed unexpectedly: %s", e)
        return False


async def test_basic_connection() -> bool:
    """Test the establishment of a basic WebTransport connection."""
    logger.info("Test 01: Basic WebTransport Connection")
    logger.info("=" * 50)

    config = ClientConfig(verify_mode=ssl.CERT_NONE)
    logger.info("Target server: %s", SERVER_URL)
    logger.info("Config: timeout=%ss, verify_ssl=False", config.connect_timeout)

    try:
        async with WebTransportClient(config=config) as client:
            logger.info("Client activated, attempting connection...")
            start_time = time.time()
            session = await client.connect(url=SERVER_URL)
            connect_time = time.time() - start_time

            logger.info("Connection established!")
            logger.info("   - Connection time: %.3fs", connect_time)
            logger.info("   - Session ID: %s", session.session_id)
            logger.info("   - Session state: %s", session.state.value)

            if session.state != SessionState.CONNECTED:
                logger.error("FAILED: Session not in CONNECTED state")
                return False

            logger.info("SUCCESS: Session is in CONNECTED state!")

            logger.info("Closing session...")
            await session.close()
            logger.info("Session closed successfully")
            return True
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILED: Connection error - %s", e)
        logger.error("Possible issues:")
        logger.error("   - Server not running")
        logger.error("   - Wrong server address/port")
        logger.error("   - Network connectivity problems")
        return False
    except Exception as e:
        logger.error("FAILED: Unexpected error - %s", e, exc_info=True)
        logger.error("This might be a bug in the WebTransport implementation")
        return False


async def main() -> int:
    """Run the main entry point for the basic connection test."""
    logger.info("Starting Test 01: Basic Connection")
    logger.info("")

    if not await test_server_reachability():
        logger.error("Pre-check failed. Please start the server first:")
        logger.error("   python tests/e2e/test_00_e2e_server.py")
        return 1

    logger.info("")
    success = await test_basic_connection()
    logger.info("")
    logger.info("=" * 50)

    if success:
        logger.info("TEST 01 PASSED: Basic connection successful!")
        return 0
    else:
        logger.error("TEST 01 FAILED: Basic connection failed!")
        return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user.")
        exit_code = 130
    except Exception as e:
        logger.critical("Test suite crashed with an unhandled exception: %s", e, exc_info=True)
    finally:
        sys.exit(exit_code)



================================================
FILE: tests/e2e/test_02_simple_stream.py
================================================
"""E2E test for simple bidirectional stream operations."""

import asyncio
import logging
import ssl
import sys
from collections.abc import Awaitable, Callable
from typing import Final

from pywebtransport import ClientConfig, ConnectionError, StreamError, TimeoutError, WebTransportClient

SERVER_HOST: Final[str] = "127.0.0.1"
SERVER_PORT: Final[int] = 4433
SERVER_URL: Final[str] = f"https://{SERVER_HOST}:{SERVER_PORT}/"
DEBUG_MODE: Final[bool] = "--debug" in sys.argv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)
    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)

logger = logging.getLogger("test_simple_stream")


async def test_stream_creation() -> bool:
    """Test the ability to create and inspect a bidirectional stream."""
    logger.info("Test 02A: Stream Creation")
    logger.info("-" * 30)

    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            logger.info("Connecting to %s...", SERVER_URL)
            session = await client.connect(url=SERVER_URL)
            logger.info("Connected, session ID: %s", session.session_id)

            logger.info("Creating bidirectional stream...")
            stream = await session.create_bidirectional_stream()

            logger.info("Stream created successfully!")
            logger.info("   - Stream ID: %s", stream.stream_id)

            await stream.close()
            logger.info("Stream closed.")
            return True
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Connection failed: %s", e)
        return False
    except StreamError as e:
        logger.error("FAILURE: Stream creation failed: %s", e, exc_info=True)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_simple_echo() -> bool:
    """Test sending data and receiving an echo on a single stream."""
    logger.info("Test 02B: Simple Echo")
    logger.info("-" * 30)

    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            stream = await session.create_bidirectional_stream()
            logger.info("Stream %s created for echo test.", stream.stream_id)

            test_message = b"Hello, WebTransport!"
            logger.info("Sending: %r", test_message)
            await stream.write(data=test_message, end_stream=True)

            logger.info("Waiting for echo response...")
            response_data = await stream.read_all()
            logger.info("Received response: %r", response_data)

            expected_response = b"ECHO: " + test_message
            if response_data == expected_response:
                logger.info("SUCCESS: Echo response matches expected content.")
                return True
            else:
                logger.error("FAILURE: Echo response mismatch!")
                logger.error("   - Expected: %r", expected_response)
                logger.error("   - Received: %r", response_data)
                return False
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_multiple_messages() -> bool:
    """Test sending multiple messages, each on a separate stream, within one session."""
    logger.info("Test 02C: Multiple Messages")
    logger.info("-" * 30)

    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            messages = [b"Message 1", b"Message 2", b"Message 3"]
            success_count = 0

            for i, message in enumerate(messages):
                logger.info("Processing message %d/%d: %r", i + 1, len(messages), message)
                stream = await session.create_bidirectional_stream()
                try:
                    await stream.write(data=message, end_stream=True)
                    response_data = await stream.read_all()
                    expected = b"ECHO: " + message
                    if response_data == expected:
                        logger.info("   - Echo for message %d successful.", i + 1)
                        success_count += 1
                    else:
                        logger.error("   - FAILURE: Echo for message %d mismatch!", i + 1)
                finally:
                    await stream.close()

            if success_count == len(messages):
                logger.info("SUCCESS: All %d messages echoed correctly!", len(messages))
                return True
            else:
                logger.error("FAILURE: Only %d/%d messages were successful.", success_count, len(messages))
                return False
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def main() -> int:
    """Run the main entry point for the simple stream operations test."""
    logger.info("Starting Test 02: Simple Stream Operations")

    tests: list[tuple[str, Callable[[], Awaitable[bool]]]] = [
        ("Stream Creation", test_stream_creation),
        ("Simple Echo", test_simple_echo),
        ("Multiple Messages", test_multiple_messages),
    ]
    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info("")
        try:
            if await test_func():
                logger.info("%s: PASSED", test_name)
                passed += 1
            else:
                logger.error("%s: FAILED", test_name)
        except Exception as e:
            logger.error("%s: CRASHED - %s", test_name, e, exc_info=True)
        await asyncio.sleep(1)

    logger.info("")
    logger.info("=" * 50)
    logger.info("Test 02 Results: %d/%d passed", passed, total)

    if passed == total:
        logger.info("TEST 02 PASSED: All stream operations successful!")
        return 0
    else:
        logger.error("TEST 02 FAILED: Some stream operations failed!")
        return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user.")
        exit_code = 130
    except Exception as e:
        logger.critical("Test suite crashed with an unhandled exception: %s", e, exc_info=True)
    finally:
        sys.exit(exit_code)



================================================
FILE: tests/e2e/test_03_concurrent_streams.py
================================================
"""E2E test for concurrent WebTransport stream handling."""

import asyncio
import logging
import ssl
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Final

from pywebtransport import (
    ClientConfig,
    ConnectionError,
    StreamError,
    TimeoutError,
    WebTransportClient,
    WebTransportSession,
)

SERVER_HOST: Final[str] = "127.0.0.1"
SERVER_PORT: Final[int] = 4433
SERVER_URL: Final[str] = f"https://{SERVER_HOST}:{SERVER_PORT}/"
DEBUG_MODE: Final[bool] = "--debug" in sys.argv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)
    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)

logger = logging.getLogger("test_concurrent_streams")


async def test_sequential_streams() -> bool:
    """Test creating and using multiple streams sequentially in one session."""
    logger.info("--- Test 03A: Sequential Multiple Streams ---")
    num_streams = 3
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Connected, session ID: %s", session.session_id)

            for i in range(num_streams):
                stream_num = i + 1
                logger.info("Creating and testing stream %d/%d...", stream_num, num_streams)
                stream = await session.create_bidirectional_stream()
                test_msg = f"Sequential stream {stream_num}".encode()
                await stream.write_all(data=test_msg, end_stream=True)
                response = await stream.read_all()

                expected = b"ECHO: " + test_msg
                if response != expected:
                    logger.error("FAILURE: Stream %d echo failed.", stream_num)
                    return False
                logger.info("Stream %d echo successful.", stream_num)

            logger.info("SUCCESS: All sequential streams worked correctly.")
            return True
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_concurrent_streams() -> bool:
    """Test handling multiple streams concurrently using asyncio tasks."""
    logger.info("--- Test 03B: Concurrent Streams ---")
    num_streams = 10
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    async def stream_task(*, session: WebTransportSession, task_id: int) -> bool:
        """Define the work for a single concurrent stream test."""
        try:
            stream = await session.create_bidirectional_stream()
            logger.debug("Task %d: Stream created (ID=%s)", task_id, stream.stream_id)
            test_msg = f"Concurrent stream {task_id}".encode()
            await stream.write_all(data=test_msg, end_stream=True)
            response = await stream.read_all()

            expected = b"ECHO: " + test_msg
            if response == expected:
                logger.debug("Task %d: Echo successful.", task_id)
                return True
            else:
                logger.error("Task %d: Echo failed.", task_id)
                return False
        except Exception as e:
            logger.error("Task %d: Failed with an exception: %s", task_id, e)
            return False

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Starting %d concurrent stream tasks...", num_streams)
            start_time = time.time()

            tasks = [asyncio.create_task(stream_task(session=session, task_id=i + 1)) for i in range(num_streams)]
            results = await asyncio.gather(*tasks)
            duration = time.time() - start_time
            logger.info("All tasks completed in %.2fs.", duration)

            success_count = sum(1 for result in results if result is True)
            if success_count == num_streams:
                logger.info("SUCCESS: All concurrent streams completed successfully!")
                return True
            else:
                logger.error("FAILURE: %d/%d concurrent streams failed.", num_streams - success_count, num_streams)
                return False
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_stream_lifecycle() -> bool:
    """Test the full lifecycle management of a single stream."""
    logger.info("--- Test 03C: Stream Lifecycle Management ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            stream = await session.create_bidirectional_stream()
            logger.info("Stream created: %s", stream.stream_id)

            await stream.write_all(data=b"Lifecycle test", end_stream=True)
            await stream.read_all()
            logger.info("Data exchanged.")

            try:
                await stream.write(data=b"This should fail")
                logger.error("FAILURE: Write on a half-closed stream should not succeed.")
                return False
            except StreamError:
                logger.info("SUCCESS: Write on a half-closed stream correctly failed.")
                return True
            except Exception as e:
                logger.error("FAILURE: Unexpected error on second write: %s", e)
                return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_stream_stress() -> bool:
    """Perform a stress test by rapidly creating and using streams."""
    logger.info("--- Test 03D: Stream Stress Test ---")
    num_iterations = 20
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Starting stress test with %d iterations...", num_iterations)

            start_time = time.time()
            for i in range(num_iterations):
                stream = await session.create_bidirectional_stream()
                test_msg = f"Stress test {i + 1}".encode()
                await stream.write_all(data=test_msg, end_stream=True)
                response = await stream.read_all()
                expected = b"ECHO: " + test_msg
                if response != expected:
                    logger.error("FAILURE: Iteration %d echo mismatch.", i + 1)
                    return False

            duration = time.time() - start_time
            rate = num_iterations / duration if duration > 0 else float("inf")
            logger.info("SUCCESS: %d stream operations in %.2fs (%.1f ops/s).", num_iterations, duration, rate)
            return True
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def main() -> int:
    """Run the main entry point for the concurrent streams test."""
    logger.info("--- Starting Test 03: Concurrent Streams ---")

    tests: list[tuple[str, Callable[[], Awaitable[bool]]]] = [
        ("Sequential Multiple Streams", test_sequential_streams),
        ("Concurrent Streams", test_concurrent_streams),
        ("Stream Lifecycle Management", test_stream_lifecycle),
        ("Stream Stress Test", test_stream_stress),
    ]
    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info("")
        try:
            if await test_func():
                logger.info("%s: PASSED", test_name)
                passed += 1
            else:
                logger.error("%s: FAILED", test_name)
        except Exception as e:
            logger.error("%s: CRASHED - %s", test_name, e, exc_info=True)
        await asyncio.sleep(1)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 03 Results: %d/%d passed", passed, total)

    if passed == total:
        logger.info("TEST 03 PASSED: All concurrent stream tests successful!")
        return 0
    else:
        logger.error("TEST 03 FAILED: Some concurrent stream tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user.")
        exit_code = 130
    except Exception as e:
        logger.critical("Test suite crashed with an unhandled exception: %s", e, exc_info=True)
    finally:
        sys.exit(exit_code)



================================================
FILE: tests/e2e/test_04_data_transfer.py
================================================
"""E2E test for WebTransport data transfer."""

import asyncio
import logging
import ssl
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Final

from pywebtransport import ClientConfig, ConnectionError, TimeoutError, WebTransportClient

SERVER_HOST: Final[str] = "127.0.0.1"
SERVER_PORT: Final[int] = 4433
SERVER_URL: Final[str] = f"https://{SERVER_HOST}:{SERVER_PORT}/"
DEBUG_MODE: Final[bool] = "--debug" in sys.argv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)
    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)

logger = logging.getLogger("test_data_transfer")


def generate_test_data(*, size: int) -> bytes:
    """Generate a block of test data of a specified size."""
    pattern = b"WebTransport Test Data 1234567890 " * (size // 34 + 1)
    return pattern[:size]


async def test_small_data() -> bool:
    """Test small data transfers (< 1KB)."""
    logger.info("--- Test 04A: Small Data Transfer ---")
    test_sizes = [10, 100, 500, 1000]
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            for size in test_sizes:
                logger.info("Testing %s bytes transfer...", size)
                test_data = generate_test_data(size=size)
                stream = await session.create_bidirectional_stream()

                await stream.write_all(data=test_data, end_stream=True)
                response = await stream.read_all()

                expected = b"ECHO: " + test_data
                if response != expected:
                    logger.error("FAILURE: Data mismatch for %s bytes.", size)
                    return False
                logger.info("   - %s bytes: OK", size)

            logger.info("SUCCESS: All small data transfers completed successfully.")
            return True
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_medium_data() -> bool:
    """Test medium data transfers (1KB - 64KB)."""
    logger.info("--- Test 04B: Medium Data Transfer ---")
    test_sizes = [1024, 4096, 16384, 65536]
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            for size in test_sizes:
                size_kb = size / 1024
                logger.info("Testing %.1f KB transfer...", size_kb)
                test_data = generate_test_data(size=size)
                stream = await session.create_bidirectional_stream()

                await stream.write_all(data=test_data, end_stream=True)
                response_data = await stream.read_all()

                expected = b"ECHO: " + test_data
                if response_data != expected:
                    logger.error("FAILURE: Data mismatch for %.1f KB.", size_kb)
                    return False
                logger.info("   - %.1f KB: OK", size_kb)

            logger.info("SUCCESS: All medium data transfers completed successfully.")
            return True
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_chunked_transfer() -> bool:
    """Test transferring data in multiple chunks using stream.write()."""
    logger.info("--- Test 04C: Chunked Transfer ---")
    total_size = 32768
    chunk_size = 4096
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            test_data = generate_test_data(size=total_size)
            stream = await session.create_bidirectional_stream()
            logger.info("Sending %s bytes in %s-byte chunks...", total_size, chunk_size)

            bytes_sent = 0
            for i in range(0, total_size, chunk_size):
                chunk = test_data[i : i + chunk_size]
                is_last_chunk = (i + chunk_size) >= total_size
                await stream.write(data=chunk, end_stream=is_last_chunk)
                bytes_sent += len(chunk)
            logger.info("All %s bytes sent.", bytes_sent)

            response_data = await stream.read_all()
            expected = b"ECHO: " + test_data
            if response_data != expected:
                logger.error("FAILURE: Chunked data transfer response mismatch.")
                return False

            logger.info("SUCCESS: Chunked transfer completed successfully.")
            return True
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_binary_data() -> bool:
    """Test the transfer of raw binary data to ensure no corruption."""
    logger.info("--- Test 04D: Binary Data Transfer ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            binary_data = bytes(range(256)) * 100
            logger.info("Testing transfer of %d raw binary bytes.", len(binary_data))
            stream = await session.create_bidirectional_stream()

            await stream.write_all(data=binary_data, end_stream=True)
            response_data = await stream.read_all()

            expected = b"ECHO: " + binary_data
            if response_data != expected:
                logger.error("FAILURE: Binary data was corrupted during transfer.")
                return False

            logger.info("SUCCESS: Binary data transfer completed without corruption.")
            return True
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_performance_benchmark() -> bool:
    """Perform a simple performance benchmark with a 1MB payload."""
    logger.info("--- Test 04E: Performance Benchmark (1MB) ---")
    test_size = 1024 * 1024
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            test_data = generate_test_data(size=test_size)
            stream = await session.create_bidirectional_stream()

            logger.info("Starting 1MB round-trip transfer...")
            start_time = time.time()
            await stream.write_all(data=test_data, end_stream=True)
            response_data = await stream.read_all()
            duration = time.time() - start_time

            expected = b"ECHO: " + test_data
            if response_data != expected:
                logger.error("FAILURE: Performance test data corrupted.")
                return False

            total_mb = (len(test_data) + len(response_data)) / (1024 * 1024)
            throughput = total_mb / duration if duration > 0 else float("inf")
            logger.info("SUCCESS: Benchmark completed.")
            logger.info("   - Total round-trip time: %.3fs", duration)
            logger.info("   - Aggregate throughput: %.2f MB/s", throughput)
            return True
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def main() -> int:
    """Run the main entry point for the data transfer tests."""
    logger.info("--- Starting Test 04: Data Transfer ---")

    tests: list[tuple[str, Callable[[], Awaitable[bool]]]] = [
        ("Small Data Transfer", test_small_data),
        ("Medium Data Transfer", test_medium_data),
        ("Chunked Transfer", test_chunked_transfer),
        ("Binary Data Transfer", test_binary_data),
        ("Performance Benchmark", test_performance_benchmark),
    ]
    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info("")
        try:
            if await test_func():
                logger.info("%s: PASSED", test_name)
                passed += 1
            else:
                logger.error("%s: FAILED", test_name)
        except Exception as e:
            logger.error("%s: CRASHED - %s", test_name, e, exc_info=True)
        await asyncio.sleep(1)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 04 Results: %d/%d passed", passed, total)

    if passed == total:
        logger.info("TEST 04 PASSED: All data transfer tests successful!")
        return 0
    else:
        logger.error("TEST 04 FAILED: Some data transfer tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user.")
        exit_code = 130
    except Exception as e:
        logger.critical("Test suite crashed with an unhandled exception: %s", e, exc_info=True)
    finally:
        sys.exit(exit_code)



================================================
FILE: tests/e2e/test_05_datagrams.py
================================================
import asyncio
import logging
import ssl
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Final

from pywebtransport import ClientConfig, ConnectionError, Event, TimeoutError, WebTransportClient, WebTransportError
from pywebtransport.types import EventType

SERVER_HOST: Final[str] = "127.0.0.1"
SERVER_PORT: Final[int] = 4433
SERVER_URL: Final[str] = f"https://{SERVER_HOST}:{SERVER_PORT}/"
DEBUG_MODE: Final[bool] = "--debug" in sys.argv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)
    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)

logger = logging.getLogger("test_datagrams")


async def test_basic_datagram() -> bool:
    logger.info("--- Test 05A: Basic Datagram Echo ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Session ready for datagrams.")

            test_message = b"Hello, Datagram!"
            expected_response = b"ECHO: " + test_message

            logger.info("Sending datagram: %r", test_message)
            await session.send_datagram(data=test_message)

            logger.info("Waiting for echo...")
            event: Event = await session.events.wait_for(event_type=EventType.DATAGRAM_RECEIVED, timeout=5.0)

            response = None
            if isinstance(event.data, dict):
                response = event.data.get("data")

            if response == expected_response:
                logger.info("SUCCESS: Received correct datagram echo.")
                return True
            else:
                logger.error("FAILURE: Datagram echo mismatch. Got: %r", response)
                return False
    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_multiple_datagrams() -> bool:
    logger.info("--- Test 05B: Multiple Datagrams ---")
    num_datagrams = 10
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Sending %d datagrams and awaiting echoes...", num_datagrams)

            received_events: list[bytes] = []

            async def receiver() -> None:
                try:
                    for _ in range(num_datagrams):
                        event = await session.events.wait_for(event_type=EventType.DATAGRAM_RECEIVED, timeout=5.0)

                        data = None
                        if isinstance(event.data, dict):
                            data = event.data.get("data")

                        if isinstance(data, bytes):
                            received_events.append(data)
                except asyncio.TimeoutError:
                    logger.warning("Receiver timed out.")
                except Exception:
                    pass

            receiver_task = asyncio.create_task(receiver())
            await asyncio.sleep(0.1)

            for i in range(num_datagrams):
                await session.send_datagram(data=f"Datagram message {i + 1}".encode())

            await receiver_task

            if len(received_events) != num_datagrams:
                logger.error(
                    "FAILURE: Expected %d datagrams, but received %d.",
                    num_datagrams,
                    len(received_events),
                )
                return False

            for i, data in enumerate(received_events):
                expected = f"ECHO: Datagram message {i + 1}".encode()
                if data != expected:
                    logger.error("FAILURE: Datagram %d mismatch. Got: %r", i + 1, data)
                    return False

            logger.info("SUCCESS: Received %d correct datagram echoes.", num_datagrams)
            return True

    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_datagram_sizes() -> bool:
    logger.info("--- Test 05C: Datagram Size Limits ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE, max_datagram_size=1200)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)

            connection = session._connection()
            if not connection:
                logger.error("FAILURE: Connection lost unexpectedly.")
                return False

            diags = await connection.diagnostics()
            local_max = diags.max_datagram_size
            remote_max = diags.remote_max_datagram_frame_size
            logger.info("Max datagram size from diagnostics: local=%s, remote=%s", local_max, remote_max)

            if local_max != 1200:
                logger.warning("Engine state max_datagram_size (%s) mismatch config (%s)", local_max, 1200)

            if remote_max is None:
                logger.error(
                    "FAILURE: Remote max datagram size is None (not negotiated), cannot test oversized datagram."
                )
                return False

            logger.info("Testing oversized datagram...")
            try:
                oversized_data = b"X" * (remote_max + 1)
                await session.send_datagram(data=oversized_data)
                logger.error("FAILURE: Sending oversized datagram should have raised an exception.")
                return False
            except WebTransportError as e:
                if "Datagram size" in str(e) and "exceeds limit" in str(e):
                    logger.info("SUCCESS: Oversized datagram correctly raised WebTransportError: %s", e)
                    return True
                else:
                    logger.error("FAILURE: Caught WebTransportError, but message mismatch: %s", e)
                    return False
            except Exception as e:
                logger.error("FAILURE: Unexpected exception type for oversized datagram: %s (%s)", type(e).__name__, e)
                return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_datagram_burst() -> bool:
    logger.info("--- Test 05G: Datagram Burst ---")
    burst_size = 50
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Starting burst of %d datagrams...", burst_size)
            start_time = time.time()

            tasks = [session.send_datagram(data=f"Burst {i}".encode()) for i in range(burst_size)]
            await asyncio.gather(*tasks)
            duration = time.time() - start_time
            rate = burst_size / duration if duration > 0 else float("inf")

            logger.info("SUCCESS: Sent %d datagrams in %.3fs (%.1f dgrams/s).", burst_size, duration, rate)
            return True
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def main() -> int:
    logger.info("--- Starting Test 05: Datagrams ---")

    tests: list[tuple[str, Callable[[], Awaitable[bool]]]] = [
        ("Basic Datagram Echo", test_basic_datagram),
        ("Multiple Datagrams", test_multiple_datagrams),
        ("Datagram Size Limits", test_datagram_sizes),
        ("Datagram Burst", test_datagram_burst),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info("")
        try:
            if await test_func():
                logger.info("%s: PASSED", test_name)
                passed += 1
            else:
                logger.error("%s: FAILED", test_name)
        except Exception as e:
            logger.error("%s: CRASHED - %s", test_name, e, exc_info=True)
        await asyncio.sleep(1)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 05 Results: %d/%d passed", passed, total)

    if passed == total:
        logger.info("TEST 05 PASSED: All datagram tests successful!")
        return 0
    else:
        logger.error("TEST 05 FAILED: Some datagram tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user.")
        exit_code = 130
    except Exception as e:
        logger.critical("Test suite crashed with an unhandled exception: %s", e, exc_info=True)
    finally:
        sys.exit(exit_code)



================================================
FILE: tests/e2e/test_06_error_handling.py
================================================
"""E2E test for WebTransport error handling and edge cases."""

import asyncio
import logging
import ssl
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Final

from pywebtransport import (
    ClientConfig,
    ClientError,
    ConnectionError,
    SessionError,
    StreamError,
    TimeoutError,
    WebTransportClient,
)

SERVER_HOST: Final[str] = "127.0.0.1"
SERVER_PORT: Final[int] = 4433
SERVER_URL: Final[str] = f"https://{SERVER_HOST}:{SERVER_PORT}/"
DEBUG_MODE: Final[bool] = "--debug" in sys.argv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)
    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)

logger = logging.getLogger("test_error_handling")


async def test_connection_timeout() -> bool:
    """Test the handling of a connection timeout to an unreachable port."""
    logger.info("--- Test 06A: Connection Timeout ---")
    unreachable_url = f"https://{SERVER_HOST}:9999/"
    config = ClientConfig(verify_mode=ssl.CERT_NONE, connect_timeout=2.0)

    logger.info("Attempting connection to unreachable server: %s", unreachable_url)
    start_time = time.time()
    try:
        async with WebTransportClient(config=config) as client:
            await client.connect(url=unreachable_url)
        logger.error("FAILURE: Connection should have failed but it succeeded.")
        return False
    except (TimeoutError, ConnectionError, ClientError):
        duration = time.time() - start_time
        logger.info("SUCCESS: Connection correctly failed after %.1fs.", duration)
        return True
    except Exception as e:
        logger.error("FAILURE: An unexpected exception was caught: %s", type(e).__name__, exc_info=True)
        return False


async def test_invalid_server_address() -> bool:
    """Test handling of various invalid server addresses."""
    logger.info("--- Test 06B: Invalid Server Address ---")
    invalid_urls = [
        "https://invalid-hostname-for-testing.local/",
        "http://127.0.0.1:4433/",
    ]
    config = ClientConfig(verify_mode=ssl.CERT_NONE, connect_timeout=2.0)

    try:
        async with WebTransportClient(config=config) as client:
            for i, invalid_url in enumerate(invalid_urls):
                logger.info("Testing invalid URL %d: %s", i + 1, invalid_url)
                try:
                    await client.connect(url=invalid_url)
                    logger.error("FAILURE: Connection to %s should have failed.", invalid_url)
                    return False
                except Exception:
                    logger.info("   - SUCCESS: Connection to %s correctly failed.", invalid_url)
            return True
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred in the test setup: %s", e, exc_info=True)
        return False


async def test_stream_errors() -> bool:
    """Test error handling for various stream operations."""
    logger.info("--- Test 06C: Stream Error Handling ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            stream = await session.create_bidirectional_stream()
            await stream.close()
            logger.info("Stream closed for testing subsequent operations.")

            logger.info("Testing write operation on a closed stream...")
            try:
                await stream.write(data=b"This should fail")
                logger.error("FAILURE: Write on a closed stream should have failed.")
                return False
            except StreamError:
                logger.info("   - SUCCESS: Write on a closed stream correctly failed.")
            except Exception as e:
                logger.error("   - FAILURE: Unexpected error on write: %s", e)
                return False

            return True
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_read_timeout() -> bool:
    """Test the handling of a stream read timeout."""
    logger.info("--- Test 06D: Stream Read Timeout ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            stream = await session.create_bidirectional_stream()
            logger.info("Attempting to read from a stream with no data (should time out)...")
            start_time = time.time()
            try:
                async with asyncio.timeout(delay=1.0):
                    await stream.read(max_bytes=1024)
                logger.error("FAILURE: Read operation should have timed out.")
                return False
            except asyncio.TimeoutError:
                duration = time.time() - start_time
                logger.info("SUCCESS: Read correctly timed out after %.1fs.", duration)
                await stream.close()
                return True
            except Exception as e:
                logger.error("FAILURE: Unexpected exception during read: %s", e)
                return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_session_closure_handling() -> bool:
    """Test that operations on a closed session correctly raise errors."""
    logger.info("--- Test 06E: Operations on Closed Session ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Connected, session ID: %s", session.session_id)
            await session.close()
            logger.info("Session closed.")

            logger.info("Testing stream creation on closed session...")
            try:
                await session.create_bidirectional_stream()
                logger.error("FAILURE: Stream creation on closed session should have failed.")
                return False
            except SessionError:
                logger.info("   - SUCCESS: Stream creation correctly failed.")
            except Exception as e:
                logger.error("   - FAILURE: Unexpected error: %s", e)
                return False

            logger.info("Testing datagram send on closed session...")
            try:
                await session.send_datagram(data=b"This should fail")
                logger.error("FAILURE: Datagram send on closed session should have failed.")
                return False
            except SessionError:
                logger.info("   - SUCCESS: Datagram send correctly failed.")
            except Exception as e:
                logger.error("   - FAILURE: Unexpected error: %s", e)
                return False

            return True
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_malformed_operations() -> bool:
    """Test handling of malformed API operations."""
    logger.info("--- Test 06H: Malformed Operations ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            stream = await session.create_bidirectional_stream()

            logger.info("Testing invalid write data (None)...")
            try:
                await stream.write(data=None)  # type: ignore
                logger.error("FAILURE: Writing None should have failed.")
                return False
            except TypeError:
                logger.info("   - SUCCESS: Writing None correctly failed with TypeError.")
            except Exception as e:
                logger.error("   - FAILURE: Unexpected error for None write: %s", e)
                return False

            return True
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def main() -> int:
    """Run the main entry point for the error handling test suite."""
    logger.info("--- Starting Test 06: Error Handling ---")

    tests: list[tuple[str, Callable[[], Awaitable[bool]]]] = [
        ("Connection Timeout", test_connection_timeout),
        ("Invalid Server Address", test_invalid_server_address),
        ("Stream Error Handling", test_stream_errors),
        ("Read Timeout", test_read_timeout),
        ("Operations on Closed Session", test_session_closure_handling),
        ("Malformed Operations", test_malformed_operations),
    ]
    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info("")
        try:
            if await test_func():
                logger.info("%s: PASSED", test_name)
                passed += 1
            else:
                logger.error("%s: FAILED", test_name)
        except Exception as e:
            logger.error("%s: CRASHED - %s", test_name, e, exc_info=True)
        await asyncio.sleep(delay=1)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 06 Results: %d/%d passed", passed, total)

    if passed == total:
        logger.info("TEST 06 PASSED: All error handling tests successful!")
        return 0
    else:
        logger.error("TEST 06 FAILED: Some error handling tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user.")
        exit_code = 130
    except Exception as e:
        logger.critical("Test suite crashed with an unhandled exception: %s", e, exc_info=True)
    finally:
        sys.exit(exit_code)



================================================
FILE: tests/e2e/test_07_advanced_features.py
================================================
"""E2E test for advanced WebTransport features."""

import asyncio
import json
import logging
import ssl
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Final

from pywebtransport import ClientConfig, WebTransportClient

SERVER_HOST: Final[str] = "127.0.0.1"
SERVER_PORT: Final[int] = 4433
SERVER_URL: Final[str] = f"https://{SERVER_HOST}:{SERVER_PORT}/"
DEBUG_MODE: Final[bool] = "--debug" in sys.argv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)
    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)

logger = logging.getLogger("test_advanced_features")


async def test_session_statistics() -> bool:
    """Test the retrieval and correctness of session-level statistics."""
    logger.info("--- Test 07A: Session Statistics ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Performing operations to generate statistics...")

            for i in range(3):
                stream = await session.create_bidirectional_stream()
                await stream.write_all(data=f"Stats test {i + 1}".encode(), end_stream=True)
                await stream.read_all()

            for i in range(5):
                await session.send_datagram(data=f"Datagram {i + 1}".encode())

            await asyncio.sleep(0.1)
            final_stats = await session.diagnostics()
            logger.info("Final session statistics retrieved.")

            streams_ok = final_stats.local_streams_bidi_opened >= 3
            datagrams_ok = final_stats.datagrams_sent >= 5

            if streams_ok and datagrams_ok:
                logger.info("SUCCESS: Session statistics appear correct.")
                return True
            else:
                logger.error("FAILURE: Session statistics mismatch.")
                logger.error("   - Streams Created: %s (expected >= 3)", final_stats.local_streams_bidi_opened)
                logger.error("   - Datagrams Sent: %s (expected >= 5)", final_stats.datagrams_sent)
                return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_connection_info() -> bool:
    """Test the retrieval of underlying connection information."""
    logger.info("--- Test 07B: Connection Information ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            connection = session._connection()
            if not connection:
                logger.error("FAILURE: No connection object available on session.")
                return False

            logger.info("Retrieving connection information...")
            logger.info("   - Connection ID: %s", connection.connection_id)
            logger.info("   - State: %s", connection.state.value)
            logger.info("   - Remote Address: %s", connection.remote_address)

            if connection.is_connected and connection.remote_address:
                logger.info("SUCCESS: Connection information retrieved successfully.")
                return True
            else:
                logger.error("FAILURE: Connection information is incomplete or state is incorrect.")
                return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_client_statistics() -> bool:
    """Test the retrieval of client-wide statistics across multiple connections."""
    logger.info("--- Test 07C: Client-Wide Statistics ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            logger.info("Performing 3 connections to generate client stats...")
            for _ in range(3):
                session = await client.connect(url=SERVER_URL)
                await session.close()
                await asyncio.sleep(0.2)

            final_stats = (await client.diagnostics()).stats
            logger.info("Final client statistics:")
            logger.info("   - Connections Attempted: %s", final_stats.connections_attempted)
            logger.info("   - Connections Successful: %s", final_stats.connections_successful)
            logger.info("   - Avg Connect Time: %.3fs", final_stats.avg_connect_time)

            if final_stats.connections_attempted >= 3 and final_stats.connections_successful >= 3:
                logger.info("SUCCESS: Client statistics appear correct.")
                return True
            else:
                logger.error("FAILURE: Client statistics are incorrect.")
                return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_stream_management_diagnostics() -> bool:
    """Test advanced stream management features via diagnostics."""
    logger.info("--- Test 07D: Stream Management (Diagnostics) ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Connected, session: %s", session.session_id)
            connection = session._connection()
            if not connection:
                logger.error("FAILURE: Connection lost.")
                return False

            streams = [await session.create_bidirectional_stream() for _ in range(5)]
            logger.info("Created %d streams.", len(streams))

            conn_diag = await connection.diagnostics()
            logger.info("Connection diagnostics:")
            logger.info("   - Stream count: %s", conn_diag.stream_count)

            if conn_diag.stream_count == 5:
                logger.info("SUCCESS: Connection diagnostics correctly report stream count.")
            else:
                logger.error("FAILURE: Stream count is incorrect in connection diagnostics.")
                return False

            for stream in streams:
                if not stream.is_closed:
                    await stream.close()

            return True
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_datagram_statistics() -> bool:
    """Test retrieval of detailed statistics for the datagram transport."""
    logger.info("--- Test 07E: Datagram Statistics ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Sending datagrams to generate statistics...")
            total_bytes_sent = 0
            for i in range(5):
                data = f"Datagram stats test {i}".encode()
                await session.send_datagram(data=data)
                total_bytes_sent += len(data)

            await asyncio.sleep(0.1)
            final_stats = await session.diagnostics()

            logger.info("Final session datagram statistics:")
            logger.info("   - Datagrams Sent: %s", final_stats.datagrams_sent)
            logger.info("   - Bytes Sent: %s", final_stats.datagram_bytes_sent)

            if final_stats.datagrams_sent >= 5 and final_stats.datagram_bytes_sent >= total_bytes_sent:
                logger.info("SUCCESS: Datagram statistics appear correct.")
                return True
            else:
                logger.error("FAILURE: Datagram statistics are incorrect.")
                return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_performance_monitoring() -> bool:
    """Test a simple performance monitoring loop over multiple transfers."""
    logger.info("--- Test 07F: Performance Monitoring ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            logger.info("Starting simple performance monitoring loop...")

            for size in [1024, 8192]:
                latencies = []
                for _ in range(3):
                    stream = await session.create_bidirectional_stream()
                    start_time = time.time()
                    await stream.write_all(data=b"x" * size, end_stream=True)
                    await stream.read(max_bytes=size + 10)
                    latencies.append(time.time() - start_time)
                    await stream.close()

                avg_rtt_ms = (sum(latencies) / len(latencies)) * 1000
                logger.info("   - Avg RTT for %s bytes: %.1fms", size, avg_rtt_ms)

            logger.info("SUCCESS: Performance monitoring loop completed.")
            return True
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_session_lifecycle_events() -> bool:
    """Test the basic session lifecycle event flow."""
    logger.info("--- Test 07G: Session Lifecycle Events ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        events_received = []
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL)
            events_received.append("connected")

            await session.close()
            events_received.append("closed")

        if events_received == ["connected", "closed"]:
            logger.info("SUCCESS: Session lifecycle events occurred in the correct order.")
            return True
        else:
            logger.error("FAILURE: Incorrect event order: %s", events_received)
            return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_server_diagnostics() -> bool:
    """Test retrieving the server's diagnostics API."""
    logger.info("--- Test 07H: Server-Side Diagnostics ---")
    config = ClientConfig(verify_mode=ssl.CERT_NONE)
    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL + "diagnostics")
            logger.info("Connected to /diagnostics endpoint...")
            stream = await session.create_bidirectional_stream()
            response_data = await stream.read_all()
            if not response_data:
                logger.error("FAILURE: Received no data from /diagnostics endpoint.")
                return False

            stats = json.loads(response_data)
            logger.info("Received server diagnostics successfully.")

            if (
                "stats" in stats
                and "connection_states" in stats
                and "session_states" in stats
                and stats["is_serving"] is True
            ):
                logger.info("SUCCESS: Server diagnostics structure is valid.")
                return True
            else:
                logger.error("FAILURE: Server diagnostics data is incomplete or invalid.")
                logger.error("Received: %s", stats)
                return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def main() -> int:
    """Run the main entry point for the advanced features test suite."""
    logger.info("--- Starting Test 07: Advanced Features ---")

    tests: list[tuple[str, Callable[[], Awaitable[bool]]]] = [
        ("Session Statistics", test_session_statistics),
        ("Connection Information", test_connection_info),
        ("Client-Wide Statistics", test_client_statistics),
        ("Stream Management (Diagnostics)", test_stream_management_diagnostics),
        ("Datagram Statistics", test_datagram_statistics),
        ("Performance Monitoring", test_performance_monitoring),
        ("Session Lifecycle Events", test_session_lifecycle_events),
        ("Server-Side Diagnostics", test_server_diagnostics),
    ]
    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info("")
        try:
            if await test_func():
                logger.info("%s: PASSED", test_name)
                passed += 1
            else:
                logger.error("%s: FAILED", test_name)
        except Exception as e:
            logger.error("%s: CRASHED - %s", test_name, e, exc_info=True)
        await asyncio.sleep(1)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 07 Results: %d/%d passed", passed, total)

    if passed == total:
        logger.info("TEST 07 PASSED: All advanced features tests successful!")
        return 0
    else:
        logger.error("TEST 07 FAILED: Some advanced features tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user.")
        exit_code = 130
    except Exception as e:
        logger.critical("Test suite crashed with an unhandled exception: %s", e, exc_info=True)
    finally:
        sys.exit(exit_code)



================================================
FILE: tests/e2e/test_08_structured_messaging.py
================================================
"""E2E test for the structured message layer."""

import asyncio
import logging
import ssl
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

from pywebtransport import (
    ClientConfig,
    ConnectionError,
    StructuredDatagramTransport,
    StructuredStream,
    TimeoutError,
    WebTransportClient,
)
from pywebtransport.constants import DEFAULT_MAX_MESSAGE_SIZE
from pywebtransport.serializer import JSONSerializer, MsgPackSerializer
from pywebtransport.types import Serializer

SERVER_HOST: Final[str] = "127.0.0.1"
SERVER_PORT: Final[int] = 4433
SERVER_URL: Final[str] = f"https://{SERVER_HOST}:{SERVER_PORT}/"
DEBUG_MODE: Final[bool] = "--debug" in sys.argv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)
    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)

logger = logging.getLogger("test_structured_messaging")


@dataclass(kw_only=True)
class UserData:
    """Represents user data structure."""

    id: int
    name: str
    email: str


@dataclass(kw_only=True)
class StatusUpdate:
    """Represents a status update message."""

    status: str
    timestamp: float


MESSAGE_REGISTRY: dict[int, type[Any]] = {1: UserData, 2: StatusUpdate}


async def run_structured_test(*, serializer: Serializer, path: str, serializer_name: str) -> bool:
    """Run the core logic for testing a specific serializer end-to-end."""
    config = ClientConfig(verify_mode=ssl.CERT_NONE)

    try:
        async with WebTransportClient(config=config) as client:
            session = await client.connect(url=SERVER_URL + path)
            logger.info("Connected for %s test, session: %s", serializer_name.upper(), session.session_id)

            logger.info("[%s] Testing StructuredStream...", serializer_name.upper())
            raw_stream = await session.create_bidirectional_stream()
            structured_stream = StructuredStream(
                stream=raw_stream,
                serializer=serializer,
                registry=MESSAGE_REGISTRY,
                max_message_size=DEFAULT_MAX_MESSAGE_SIZE,
            )

            user_obj = UserData(id=1, name="test", email="test@example.com")
            logger.info("   - Sending stream object: %s", user_obj)
            await structured_stream.send_obj(obj=user_obj)
            received_user_obj = await structured_stream.receive_obj()
            logger.info("   - Received stream object: %s", received_user_obj)
            if user_obj != received_user_obj:
                logger.error("FAILURE: Stream object mismatch for UserData.")
                return False

            status_obj = StatusUpdate(status="active", timestamp=time.time())
            logger.info("   - Sending stream object: %s", status_obj)
            await structured_stream.send_obj(obj=status_obj)
            received_status_obj = await structured_stream.receive_obj()
            logger.info("   - Received stream object: %s", received_status_obj)
            if status_obj.status != received_status_obj.status:
                logger.error("FAILURE: Stream object mismatch for StatusUpdate.")
                return False
            logger.info("   - SUCCESS: StructuredStream echo correct.")
            await structured_stream.close()

            logger.info("[%s] Testing StructuredDatagramTransport...", serializer_name.upper())
            structured_datagram_transport = StructuredDatagramTransport(
                session=session, serializer=serializer, registry=MESSAGE_REGISTRY
            )
            structured_datagram_transport.initialize()

            datagram_obj = UserData(id=99, name="datagram_user", email="dg@example.com")
            logger.info("   - Sending datagram object: %s", datagram_obj)
            await structured_datagram_transport.send_obj(obj=datagram_obj)
            received_datagram_obj = await structured_datagram_transport.receive_obj(timeout=5.0)
            logger.info("   - Received datagram object: %s", received_datagram_obj)
            if datagram_obj != received_datagram_obj:
                logger.error("FAILURE: Datagram object mismatch.")
                return False
            logger.info("   - SUCCESS: StructuredDatagramTransport echo correct.")
            await structured_datagram_transport.close()

            return True

    except (TimeoutError, ConnectionError) as e:
        logger.error("FAILURE: Test failed due to connection or timeout issue: %s", e)
        return False
    except Exception as e:
        logger.error("FAILURE: An unexpected error occurred: %s", e, exc_info=True)
        return False


async def test_json_messaging() -> bool:
    """Test the structured message layer using the JSON serializer."""
    logger.info("--- Test 08A: Structured Messaging (JSON) ---")
    return await run_structured_test(serializer=JSONSerializer(), path="structured-echo/json", serializer_name="json")


async def test_msgpack_messaging() -> bool:
    """Test the structured message layer using the MsgPack serializer."""
    logger.info("--- Test 08B: Structured Messaging (MsgPack) ---")
    return await run_structured_test(
        serializer=MsgPackSerializer(), path="structured-echo/msgpack", serializer_name="msgpack"
    )


async def main() -> int:
    """Run the main entry point for the structured messaging test suite."""
    logger.info("--- Starting Test 08: Structured Messaging ---")

    tests: list[tuple[str, Callable[[], Awaitable[bool]]]] = [
        ("JSON Messaging", test_json_messaging),
        ("MsgPack Messaging", test_msgpack_messaging),
    ]
    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info("")
        try:
            if await test_func():
                logger.info("%s: PASSED", test_name)
                passed += 1
            else:
                logger.error("%s: FAILED", test_name)
        except Exception as e:
            logger.error("%s: CRASHED - %s", test_name, e, exc_info=True)
        await asyncio.sleep(1)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 08 Results: %d/%d passed", passed, total)

    if passed == total:
        logger.info("TEST 08 PASSED: All structured messaging tests successful!")
        return 0
    else:
        logger.error("TEST 08 FAILED: Some structured messaging tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user.")
        exit_code = 130
    except Exception as e:
        logger.critical("Test suite crashed with an unhandled exception: %s", e, exc_info=True)
    finally:
        sys.exit(exit_code)



================================================
FILE: tests/e2e/test_e2e_suite.py
================================================
"""End-to-end tests for the pywebtransport client."""

import asyncio
import ssl
import subprocess
import sys
from collections.abc import AsyncGenerator

import pytest
from pytest_asyncio import fixture as asyncio_fixture

from pywebtransport import ClientConfig, ClientError, WebTransportClient

from .test_01_basic_connection import test_basic_connection as run_01_basic_connection
from .test_02_simple_stream import test_multiple_messages as run_02_multiple_messages
from .test_02_simple_stream import test_simple_echo as run_02_simple_echo
from .test_02_simple_stream import test_stream_creation as run_02_stream_creation
from .test_03_concurrent_streams import test_concurrent_streams as run_03_concurrent_streams
from .test_03_concurrent_streams import test_sequential_streams as run_03_sequential_streams
from .test_03_concurrent_streams import test_stream_lifecycle as run_03_stream_lifecycle
from .test_03_concurrent_streams import test_stream_stress as run_03_stream_stress
from .test_04_data_transfer import test_binary_data as run_04_binary_data
from .test_04_data_transfer import test_chunked_transfer as run_04_chunked_transfer
from .test_04_data_transfer import test_medium_data as run_04_medium_data
from .test_04_data_transfer import test_performance_benchmark as run_04_performance_benchmark
from .test_04_data_transfer import test_small_data as run_04_small_data
from .test_05_datagrams import test_basic_datagram as run_05_basic_datagram
from .test_05_datagrams import test_datagram_burst as run_05_datagram_burst
from .test_05_datagrams import test_datagram_sizes as run_05_datagram_sizes
from .test_05_datagrams import test_multiple_datagrams as run_05_multiple_datagrams
from .test_06_error_handling import test_connection_timeout as run_06_connection_timeout
from .test_06_error_handling import test_invalid_server_address as run_06_invalid_address
from .test_06_error_handling import test_malformed_operations as run_06_malformed_operations
from .test_06_error_handling import test_read_timeout as run_06_read_timeout
from .test_06_error_handling import test_session_closure_handling as run_06_session_closure
from .test_06_error_handling import test_stream_errors as run_06_stream_errors
from .test_07_advanced_features import test_client_statistics as run_07_client_statistics
from .test_07_advanced_features import test_connection_info as run_07_connection_info
from .test_07_advanced_features import test_datagram_statistics as run_07_datagram_statistics
from .test_07_advanced_features import test_performance_monitoring as run_07_performance_monitoring
from .test_07_advanced_features import test_server_diagnostics as run_07_server_diagnostics
from .test_07_advanced_features import test_session_lifecycle_events as run_07_session_lifecycle_events
from .test_07_advanced_features import test_session_statistics as run_07_session_statistics
from .test_07_advanced_features import test_stream_management_diagnostics as run_07_stream_management_diagnostics
from .test_08_structured_messaging import test_json_messaging as run_08_json_messaging
from .test_08_structured_messaging import test_msgpack_messaging as run_08_msgpack_messaging


async def _is_server_ready() -> bool:
    config = ClientConfig(verify_mode=ssl.CERT_NONE)
    for _ in range(60):
        try:
            async with WebTransportClient(config=config) as client:
                session = await client.connect(url="https://127.0.0.1:4433/health")
                await session.close()
                return True
        except (ClientError, asyncio.TimeoutError):
            await asyncio.sleep(0.5)
    return False


@asyncio_fixture(scope="module", autouse=True)
async def e2e_server() -> AsyncGenerator[None, None]:
    server_command = [
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--source=src/pywebtransport",
        "--parallel-mode",
        "-m",
        "tests.e2e.test_00_e2e_server",
    ]

    server_proc = subprocess.Popen(
        server_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    is_ready = await _is_server_ready()

    if not is_ready or server_proc.poll() is not None:
        stdout, stderr = server_proc.communicate()
        pytest.fail(
            f"E2E server failed to start or become ready. Exit code: {server_proc.returncode}\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}",
            pytrace=False,
        )

    yield

    server_proc.terminate()
    try:
        server_proc.communicate(timeout=5.0)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        server_proc.communicate()


@pytest.mark.asyncio
class TestE2eSuite:
    async def test_01_basic_connection(self) -> None:
        assert await run_01_basic_connection() is True, "Basic connection failed"

    async def test_02_stream_creation(self) -> None:
        assert await run_02_stream_creation() is True, "Stream creation failed"

    async def test_02_simple_echo(self) -> None:
        assert await run_02_simple_echo() is True, "Simple echo failed"

    async def test_02_multiple_messages(self) -> None:
        assert await run_02_multiple_messages() is True, "Multiple messages on separate streams failed"

    async def test_03_sequential_streams(self) -> None:
        assert await run_03_sequential_streams() is True, "Sequential streams failed"

    async def test_03_concurrent_streams(self) -> None:
        assert await run_03_concurrent_streams() is True, "Concurrent streams failed"

    async def test_03_stream_lifecycle(self) -> None:
        assert await run_03_stream_lifecycle() is True, "Stream lifecycle management failed"

    async def test_03_stream_stress(self) -> None:
        assert await run_03_stream_stress() is True, "Stream stress test failed"

    async def test_04_small_data(self) -> None:
        assert await run_04_small_data() is True, "Small data transfer failed"

    async def test_04_medium_data(self) -> None:
        assert await run_04_medium_data() is True, "Medium data transfer failed"

    async def test_04_chunked_transfer(self) -> None:
        assert await run_04_chunked_transfer() is True, "Chunked data transfer failed"

    async def test_04_binary_data(self) -> None:
        assert await run_04_binary_data() is True, "Binary data transfer failed"

    async def test_04_performance_benchmark(self) -> None:
        assert await run_04_performance_benchmark() is True, "Performance benchmark failed"

    async def test_05_basic_datagram(self) -> None:
        assert await run_05_basic_datagram() is True, "Basic datagram send failed"

    async def test_05_multiple_datagrams(self) -> None:
        assert await run_05_multiple_datagrams() is True, "Multiple datagrams send failed"

    async def test_05_datagram_sizes(self) -> None:
        assert await run_05_datagram_sizes() is True, "Datagram size handling failed"

    async def test_05_datagram_burst(self) -> None:
        assert await run_05_datagram_burst() is True, "Datagram burst test failed"

    async def test_06_connection_timeout(self) -> None:
        assert await run_06_connection_timeout() is True, "Connection timeout handling failed"

    async def test_06_invalid_address(self) -> None:
        assert await run_06_invalid_address() is True, "Invalid server address handling failed"

    async def test_06_stream_errors(self) -> None:
        assert await run_06_stream_errors() is True, "Stream error handling failed"

    async def test_06_read_timeout(self) -> None:
        assert await run_06_read_timeout() is True, "Read timeout handling failed"

    async def test_06_session_closure(self) -> None:
        assert await run_06_session_closure() is True, "Session closure handling failed"

    async def test_06_malformed_operations(self) -> None:
        assert await run_06_malformed_operations() is True, "Malformed API operations handling failed"

    async def test_07_session_statistics(self) -> None:
        assert await run_07_session_statistics() is True, "Session statistics retrieval failed"

    async def test_07_connection_info(self) -> None:
        assert await run_07_connection_info() is True, "Connection info retrieval failed"

    async def test_07_client_statistics(self) -> None:
        assert await run_07_client_statistics() is True, "Client statistics retrieval failed"

    async def test_07_stream_management_diagnostics(self) -> None:
        assert await run_07_stream_management_diagnostics() is True, "Stream management diagnostics test failed"

    async def test_07_datagram_statistics(self) -> None:
        assert await run_07_datagram_statistics() is True, "Datagram statistics retrieval failed"

    async def test_07_performance_monitoring(self) -> None:
        assert await run_07_performance_monitoring() is True, "Performance monitoring test failed"

    async def test_07_session_lifecycle_events(self) -> None:
        assert await run_07_session_lifecycle_events() is True, "Session lifecycle events tracking failed"

    async def test_07_server_diagnostics(self) -> None:
        assert await run_07_server_diagnostics() is True, "Server diagnostics retrieval failed"

    async def test_08_json_messaging(self) -> None:
        assert await run_08_json_messaging() is True, "Structured JSON messaging test failed"

    async def test_08_msgpack_messaging(self) -> None:
        assert await run_08_msgpack_messaging() is True, "Structured MsgPack messaging test failed"



================================================
FILE: tests/integration/conftest.py
================================================
"""Configuration and fixtures for pywebtransport integration tests."""

import asyncio
import socket
import ssl
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import cast

import pytest
from pytest_asyncio import fixture as asyncio_fixture

from pywebtransport import ClientConfig, ServerApp, ServerConfig, WebTransportClient
from pywebtransport.utils import generate_self_signed_cert


def find_free_port() -> int:
    """Find and return an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return cast(int, s.getsockname()[1])


@pytest.fixture(scope="session")
def certificates_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate self-signed certificates in a temporary directory for the session."""
    cert_dir = tmp_path_factory.mktemp("certs")
    generate_self_signed_cert(hostname="localhost", output_dir=str(cert_dir))
    return cert_dir


@pytest.fixture(scope="module")
def client_config(certificates_dir: Path) -> ClientConfig:
    """Provide a ClientConfig that trusts the self-signed server certificate."""
    return ClientConfig(verify_mode=ssl.CERT_NONE)


@pytest.fixture(scope="module")
def server_config(certificates_dir: Path) -> ServerConfig:
    """Provide a base ServerConfig configured with the test certificates."""
    return ServerConfig(
        certfile=str(certificates_dir / "localhost.crt"), keyfile=str(certificates_dir / "localhost.key")
    )


@asyncio_fixture
async def client(client_config: ClientConfig) -> AsyncGenerator[WebTransportClient, None]:
    """Provide a WebTransportClient instance for the duration of a test."""
    async with WebTransportClient(config=client_config) as wt_client:
        yield wt_client


@asyncio_fixture
async def server(server_app: ServerApp) -> AsyncGenerator[tuple[str, int], None]:
    """Start a WebTransport server in a background task for a test."""
    host = "127.0.0.1"
    port = find_free_port()

    async with server_app:
        server_task = asyncio.create_task(server_app.serve(host=host, port=port))
        await asyncio.sleep(0.1)

        try:
            yield host, port
        finally:
            if not server_task.done():
                server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass


@pytest.fixture
def server_app(request: pytest.FixtureRequest, server_config: ServerConfig) -> ServerApp:
    """Provide a ServerApp instance configured with basic echo handlers."""
    config_overrides = getattr(request, "param", {})
    if config_overrides and isinstance(config_overrides, dict):
        custom_config = server_config.update(**config_overrides)
        app = ServerApp(config=custom_config)
    else:
        app = ServerApp(config=server_config)

    return app



================================================
FILE: tests/integration/init.py
================================================
[Empty file]


================================================
FILE: tests/integration/test_01_client_server_lifecycle.py
================================================
"""Integration tests for the basic client-server connection lifecycle."""

import asyncio
from typing import Any

import pytest

from pywebtransport import ClientError, ServerApp, WebTransportClient, WebTransportSession
from pywebtransport.types import EventType, SessionState

pytestmark = pytest.mark.asyncio


async def test_client_initiated_close(
    server_app: ServerApp, server: tuple[str, int], client: WebTransportClient
) -> None:
    host, port = server
    url = f"https://{host}:{port}/"
    server_entered = asyncio.Event()

    @server_app.route(path="/")
    async def simple_handler(session: WebTransportSession, **kwargs: Any) -> None:
        server_entered.set()
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except (asyncio.CancelledError, Exception):
            pass

    session = await client.connect(url=url)
    assert session.state == SessionState.CONNECTED

    async with asyncio.timeout(2.0):
        await server_entered.wait()

    await session.close(reason="Client-initiated close")

    try:
        async with asyncio.timeout(2.0):
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
    except TimeoutError:
        pass

    assert session.is_closed is True


async def test_connection_to_non_existent_route_fails(
    server: tuple[str, int], client: WebTransportClient, server_app: ServerApp
) -> None:
    host, port = server
    url = f"https://{host}:{port}/nonexistent"

    with pytest.raises(ClientError) as exc_info:
        await client.connect(url=url)

    error_message = str(exc_info.value).lower()
    assert "404" in error_message or "rejected" in error_message or "timeout" in error_message


async def test_server_initiated_close(
    server_app: ServerApp, server: tuple[str, int], client: WebTransportClient
) -> None:
    host, port = server
    url = f"https://{host}:{port}/close-me"

    @server_app.route(path="/close-me")
    async def immediate_close_handler(session: WebTransportSession, **kwargs: Any) -> None:
        await asyncio.sleep(0.2)
        await session.close(reason="Server closed immediately.")

    session = await client.connect(url=url)

    try:
        async with asyncio.timeout(5.0):
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
    except TimeoutError:
        if not session.is_closed:
            pytest.fail("Timed out waiting for server-initiated close.")

    assert session.is_closed is True


async def test_successful_connection_and_session(
    server_app: ServerApp, server: tuple[str, int], client: WebTransportClient
) -> None:
    host, port = server
    url = f"https://{host}:{port}/"
    handler_called = asyncio.Event()

    @server_app.route(path="/")
    async def basic_handler(session: WebTransportSession, **kwargs: Any) -> None:
        handler_called.set()
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except asyncio.CancelledError:
            pass

    session = None
    try:
        session = await client.connect(url=url)
        assert session.state == SessionState.CONNECTED

        async with asyncio.timeout(2.0):
            await handler_called.wait()
    finally:
        if session and not session.is_closed:
            await session.close()



================================================
FILE: tests/integration/test_02_data_exchange.py
================================================
"""Integration tests for data exchange over streams and datagrams."""

import asyncio
from typing import Any

import pytest

from pywebtransport import (
    Event,
    ServerApp,
    WebTransportClient,
    WebTransportReceiveStream,
    WebTransportSession,
    WebTransportStream,
)
from pywebtransport.types import EventType

pytestmark = pytest.mark.asyncio


async def test_bidirectional_stream_echo(
    server: tuple[str, int], client: WebTransportClient, server_app: ServerApp
) -> None:
    host, port = server
    server_handler_finished = asyncio.Event()

    @server_app.route(path="/echo")
    async def echo_handler(session: WebTransportSession, **kwargs: Any) -> None:
        stream_queue: asyncio.Queue[WebTransportStream] = asyncio.Queue()

        async def on_stream(event: Event) -> None:
            if isinstance(event.data, dict):
                s = event.data.get("stream")
                if isinstance(s, WebTransportStream):
                    stream_queue.put_nowait(s)

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)

        try:
            stream = await stream_queue.get()
            data = await stream.read()
            await stream.write(data=data)
            await stream.close()
        except Exception:
            pass
        finally:
            server_handler_finished.set()

    session = await client.connect(url=f"https://{host}:{port}/echo")
    async with session:
        stream = await session.create_bidirectional_stream()
        test_message = b"Hello, bidirectional world!"
        await stream.write(data=test_message)

        response = await stream.read()
        assert response == test_message
        await stream.close()

    async with asyncio.timeout(2.0):
        await server_handler_finished.wait()


async def test_concurrent_streams_and_datagrams(
    server: tuple[str, int], client: WebTransportClient, server_app: ServerApp
) -> None:
    host, port = server
    num_concurrent_ops = 5

    @server_app.route(path="/concurrent")
    async def concurrent_handler(session: WebTransportSession, **kwargs: Any) -> None:
        async def on_stream(event: Event) -> None:
            if isinstance(event.data, dict):
                s = event.data.get("stream")
                if isinstance(s, WebTransportStream):
                    data = await s.read()
                    await s.write(data=data)
                    await s.close()

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)

        async def on_datagram(event: Event) -> None:
            if isinstance(event.data, dict):
                d = event.data.get("data")
                if d:
                    await session.send_datagram(data=d)

        session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=on_datagram)

        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    async def _stream_worker(*, session: WebTransportSession, i: int) -> bool:
        stream = await session.create_bidirectional_stream()
        msg = f"Stream worker {i}".encode()
        await stream.write(data=msg)
        response = await stream.read()
        await stream.close()
        return response == msg

    async def _datagram_worker(*, session: WebTransportSession, i: int) -> bool:
        msg = f"Datagram worker {i}".encode()
        fut: asyncio.Future[bool] = asyncio.Future()

        def listener(event: Event) -> None:
            if isinstance(event.data, dict) and event.data.get("data") == msg:
                if not fut.done():
                    fut.set_result(True)

        session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=listener)
        for _ in range(3):
            if fut.done():
                break
            await session.send_datagram(data=msg)
            await asyncio.sleep(0.1)

        try:
            async with asyncio.timeout(2.0):
                await fut
            return True
        except TimeoutError:
            return False
        finally:
            session.events.off(event_type=EventType.DATAGRAM_RECEIVED, handler=listener)

    session = await client.connect(url=f"https://{host}:{port}/concurrent")
    async with session:
        stream_tasks = [_stream_worker(session=session, i=i) for i in range(num_concurrent_ops)]
        datagram_tasks = [_datagram_worker(session=session, i=i) for i in range(num_concurrent_ops)]
        results = await asyncio.gather(*(stream_tasks + datagram_tasks), return_exceptions=True)

    for result in results:
        assert result is True


async def test_datagram_echo(server: tuple[str, int], client: WebTransportClient, server_app: ServerApp) -> None:
    host, port = server
    server_handler_finished = asyncio.Event()

    @server_app.route(path="/datagram")
    async def datagram_echo_handler(session: WebTransportSession, **kwargs: Any) -> None:
        async def on_datagram(event: Event) -> None:
            if isinstance(event.data, dict):
                data = event.data.get("data")
                if data:
                    await session.send_datagram(data=data)
                    server_handler_finished.set()

        session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=on_datagram)
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    session = await client.connect(url=f"https://{host}:{port}/datagram")
    async with session:
        test_message = b"Hello, datagram world!"
        fut: asyncio.Future[bool] = asyncio.Future()

        def listener(event: Event) -> None:
            if isinstance(event.data, dict) and event.data.get("data") == test_message:
                if not fut.done():
                    fut.set_result(True)

        session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=listener)

        for _ in range(5):
            await session.send_datagram(data=test_message)
            try:
                async with asyncio.timeout(0.5):
                    await asyncio.shield(fut)
                break
            except TimeoutError:
                continue
        else:
            pytest.fail("Datagram echo timed out")

    async with asyncio.timeout(2.0):
        await server_handler_finished.wait()


async def test_unidirectional_stream_to_server(
    server: tuple[str, int], client: WebTransportClient, server_app: ServerApp
) -> None:
    host, port = server
    data_queue: asyncio.Queue[bytes] = asyncio.Queue()

    @server_app.route(path="/uni")
    async def uni_handler(session: WebTransportSession, **kwargs: Any) -> None:
        async def on_stream(event: Event) -> None:
            if isinstance(event.data, dict):
                s = event.data.get("stream")
                if isinstance(s, WebTransportReceiveStream):
                    data = await s.read()
                    await data_queue.put(data)

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    session = await client.connect(url=f"https://{host}:{port}/uni")
    async with session:
        stream = await session.create_unidirectional_stream()
        test_message = b"Hello, unidirectional world!"
        await stream.write(data=test_message)
        await stream.close()

    async with asyncio.timeout(2.0):
        received_data = await data_queue.get()

    assert received_data == test_message



================================================
FILE: tests/integration/test_03_server_app_features.py
================================================
"""Integration tests for high-level ServerApp features."""

import asyncio
import http
from typing import Any

import pytest

from pywebtransport import (
    ClientError,
    Event,
    Headers,
    ServerApp,
    WebTransportClient,
    WebTransportSession,
    WebTransportStream,
)
from pywebtransport.server import MiddlewareRejected
from pywebtransport.types import EventType, SessionProtocol
from pywebtransport.utils import find_header_str

pytestmark = pytest.mark.asyncio


async def test_middleware_accepts_session(
    server: tuple[str, int], client: WebTransportClient, server_app: ServerApp
) -> None:
    host, port = server
    handler_was_reached = asyncio.Event()

    async def auth_middleware(session: SessionProtocol) -> None:
        token = find_header_str(headers=session.headers, key="x-auth-token")
        if token != "valid-token":
            raise MiddlewareRejected(status_code=http.HTTPStatus.FORBIDDEN)

    server_app.add_middleware(middleware=auth_middleware)

    @server_app.route(path="/protected")
    async def protected_handler(session: WebTransportSession, **kwargs: Any) -> None:
        handler_was_reached.set()
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    headers: Headers = {"x-auth-token": "valid-token"}
    async with await client.connect(url=f"https://{host}:{port}/protected", headers=headers):
        async with asyncio.timeout(2.0):
            await handler_was_reached.wait()


async def test_middleware_rejects_session(
    server: tuple[str, int], client: WebTransportClient, server_app: ServerApp
) -> None:
    host, port = server

    async def auth_middleware(session: SessionProtocol) -> None:
        token = find_header_str(headers=session.headers, key="x-auth-token")
        if token != "valid-token":
            raise MiddlewareRejected(status_code=http.HTTPStatus.FORBIDDEN)

    server_app.add_middleware(middleware=auth_middleware)

    @server_app.route(path="/protected")
    async def protected_handler(session: WebTransportSession, **kwargs: Any) -> None:
        pytest.fail("Rejected session reached the route handler.")

    headers: Headers = {"x-auth-token": "invalid-token"}
    with pytest.raises(ClientError) as exc_info:
        await client.connect(url=f"https://{host}:{port}/protected", headers=headers)

    error_message = str(exc_info.value).lower()
    assert "403" in error_message or "rejected" in error_message or "timeout" in error_message


async def test_pattern_routing_with_params(
    server: tuple[str, int], client: WebTransportClient, server_app: ServerApp
) -> None:
    host, port = server

    @server_app.pattern_route(pattern=r"/items/(?P<item_id>[a-zA-Z0-9-]+)")
    async def item_handler(session: WebTransportSession, item_id: str, **kwargs: Any) -> None:
        async def on_stream(event: Event) -> None:
            if isinstance(event.data, dict):
                s = event.data.get("stream")
                if isinstance(s, WebTransportStream):
                    _ = await s.read()
                    response_message = f"Accessed item: {item_id}".encode()
                    await s.write(data=response_message)
                    await s.close()

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)

        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    async with await client.connect(url=f"https://{host}:{port}/items/123-abc") as session:
        stream = await session.create_bidirectional_stream()
        await stream.write(data=b"get item data")
        response = await stream.read()
        assert response == b"Accessed item: 123-abc"


async def test_routing_to_path_one(server: tuple[str, int], client: WebTransportClient, server_app: ServerApp) -> None:
    host, port = server
    handler_one_called = asyncio.Event()
    handler_two_called = asyncio.Event()

    @server_app.route(path="/path_one")
    async def handler_one(session: WebTransportSession, **kwargs: Any) -> None:
        handler_one_called.set()
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    @server_app.route(path="/path_two")
    async def handler_two(session: WebTransportSession, **kwargs: Any) -> None:
        handler_two_called.set()
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    async with await client.connect(url=f"https://{host}:{port}/path_one"):
        async with asyncio.timeout(2.0):
            await handler_one_called.wait()

    assert handler_one_called.is_set()
    assert not handler_two_called.is_set()


async def test_routing_to_path_two(server: tuple[str, int], client: WebTransportClient, server_app: ServerApp) -> None:
    host, port = server
    handler_one_called = asyncio.Event()
    handler_two_called = asyncio.Event()

    @server_app.route(path="/path_one")
    async def handler_one(session: WebTransportSession, **kwargs: Any) -> None:
        handler_one_called.set()
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    @server_app.route(path="/path_two")
    async def handler_two(session: WebTransportSession, **kwargs: Any) -> None:
        handler_two_called.set()
        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception:
            pass

    async with await client.connect(url=f"https://{host}:{port}/path_two"):
        async with asyncio.timeout(2.0):
            await handler_two_called.wait()

    assert handler_two_called.is_set()
    assert not handler_one_called.is_set()



================================================
FILE: tests/integration/test_04_resource_management_and_errors.py
================================================
"""Integration tests for resource management and error handling."""

import asyncio
from typing import Any

import pytest

from pywebtransport import (
    ClientConfig,
    ClientError,
    ConnectionError,
    ServerApp,
    StreamError,
    TimeoutError,
    WebTransportClient,
    WebTransportSession,
)
from pywebtransport.types import EventType, SessionState

pytestmark = pytest.mark.asyncio


async def idle_handler(session: WebTransportSession, **kwargs: Any) -> None:
    try:
        await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
    except asyncio.CancelledError:
        pass


@pytest.mark.parametrize("server_app", [{"max_connections": 1}], indirect=True)
async def test_max_connections_limit_rejection(
    server_app: ServerApp, server: tuple[str, int], client_config: ClientConfig
) -> None:
    server_app.route(path="/")(idle_handler)
    host, port = server
    url = f"https://{host}:{port}/"

    async with WebTransportClient(config=client_config) as client1:
        session1 = await client1.connect(url=url)
        try:
            async with WebTransportClient(config=client_config) as client2:
                with pytest.raises((ClientError, ConnectionError, TimeoutError, asyncio.TimeoutError)):
                    await client2.connect(url=url)
        finally:
            if not session1.is_closed:
                await session1.close()


@pytest.mark.parametrize(
    "server_app", [{"initial_max_streams_bidi": 2, "flow_control_window_auto_scale": False}], indirect=True
)
async def test_max_streams_limit(server_app: ServerApp, server: tuple[str, int], client_config: ClientConfig) -> None:
    server_app.route(path="/")(idle_handler)
    host, port = server
    url = f"https://{host}:{port}/"

    async with WebTransportClient(config=client_config) as client:
        async with await client.connect(url=url) as session:
            await asyncio.sleep(delay=0.2)

            s1 = await session.create_bidirectional_stream()
            s2 = await session.create_bidirectional_stream()

            await s1.write(data=b"1")
            await s2.write(data=b"2")

            with pytest.raises((StreamError, TimeoutError, asyncio.TimeoutError)):
                async with asyncio.timeout(delay=1.0):
                    await session.create_bidirectional_stream()


@pytest.mark.parametrize(
    "server_app",
    [{"connection_idle_timeout": 0.2, "resource_cleanup_interval": 0.1}],
    indirect=True,
)
async def test_server_cleans_up_closed_connection(
    server_app: ServerApp, server: tuple[str, int], client_config: ClientConfig
) -> None:
    server_app.route(path="/")(idle_handler)
    host, port = server
    url = f"https://{host}:{port}/"
    connection_manager = server_app.server.connection_manager

    assert len(await connection_manager.get_all_resources()) == 0

    async with WebTransportClient(config=client_config) as client:
        session = await client.connect(url=url)
        try:
            assert session.state == SessionState.CONNECTED

            async with asyncio.timeout(delay=2.0):
                while len(await connection_manager.get_all_resources()) < 1:
                    await asyncio.sleep(delay=0.05)

            assert len(await connection_manager.get_all_resources()) == 1
        finally:
            await session.close()
            await client.close()

    async with asyncio.timeout(delay=5.0):
        while len(await connection_manager.get_all_resources()) > 0:
            await asyncio.sleep(delay=0.1)

    assert len(await connection_manager.get_all_resources()) == 0



================================================
FILE: tests/unit/__init__.py
================================================
[Empty file]


================================================
FILE: tests/unit/test_config.py
================================================
"""Unit tests for the pywebtransport.config module."""

import ssl
from typing import Any, Union, get_type_hints
from unittest.mock import patch

import pytest

from pywebtransport import ClientConfig, ConfigurationError, Headers, ServerConfig
from pywebtransport.constants import (
    DEFAULT_ALPN_PROTOCOLS,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_FLOW_CONTROL_WINDOW_SIZE,
    DEFAULT_INITIAL_MAX_DATA,
    DEFAULT_MAX_CAPSULE_SIZE,
    DEFAULT_SERVER_MAX_CONNECTIONS,
)


class TestClientConfig:

    def test_copy_method(self) -> None:
        config1 = ClientConfig(alpn_protocols=["h3"])
        config2 = config1.copy()

        config2.max_connection_retries = 99
        config2.alpn_protocols.append("h2")

        assert config1 is not config2
        assert config1.max_connection_retries != 99
        assert config1.alpn_protocols == ["h3"]
        assert config2.alpn_protocols == ["h3", "h2"]

    def test_default_initialization(self) -> None:
        config = ClientConfig()

        assert config.connect_timeout == DEFAULT_CONNECT_TIMEOUT
        assert config.verify_mode == ssl.CERT_REQUIRED
        assert config.user_agent is None
        assert config.headers == {}
        assert config.congestion_control_algorithm == "cubic"
        assert config.flow_control_window_size == DEFAULT_FLOW_CONTROL_WINDOW_SIZE
        assert config.initial_max_data == DEFAULT_INITIAL_MAX_DATA
        assert config.max_capsule_size == DEFAULT_MAX_CAPSULE_SIZE
        assert config.alpn_protocols == DEFAULT_ALPN_PROTOCOLS

    def test_from_dict_method(self) -> None:
        config_dict = {"max_connection_retries": 5, "unknown_field": "should_be_ignored"}

        config = ClientConfig.from_dict(config_dict=config_dict)

        assert config.max_connection_retries == 5
        assert not hasattr(config, "unknown_field")

    def test_from_dict_missing_type_hint(self) -> None:
        def mock_get_type_hints(obj: Any) -> dict[str, Any]:
            hints = get_type_hints(obj)
            if "max_connection_retries" in hints:
                del hints["max_connection_retries"]
            return hints

        with patch("pywebtransport.config.get_type_hints", side_effect=mock_get_type_hints):
            config = ClientConfig.from_dict(config_dict={"max_connection_retries": 5})
            assert config.max_connection_retries == 5

    def test_from_dict_multi_union_ignored(self) -> None:
        def mock_get_type_hints(obj: Any) -> dict[str, Any]:
            hints = get_type_hints(obj)
            hints["max_connections"] = Union[int, str]
            return hints

        with patch("pywebtransport.config.get_type_hints", side_effect=mock_get_type_hints):
            config = ClientConfig.from_dict(config_dict={"max_connections": 5})
            assert config.max_connections == 5

    def test_headers_remain_as_provided(self) -> None:
        headers: Headers = {"X-Custom": "Value", "User-Agent": "Custom/1.0"}
        config = ClientConfig(headers=headers)

        assert config.headers == headers
        assert isinstance(config.headers, dict)
        assert config.headers["X-Custom"] == "Value"
        assert config.user_agent is None

    def test_initialization_with_none_timeout(self) -> None:
        config = ClientConfig(read_timeout=None)

        assert config.read_timeout is None

        config.validate()

    def test_to_dict_method(self) -> None:
        config = ClientConfig(verify_mode=ssl.CERT_OPTIONAL)

        data = config.to_dict()

        assert data["verify_mode"] == "CERT_OPTIONAL"

    def test_update_method(self) -> None:
        config = ClientConfig()

        new_config = config.update(connect_timeout=15.0)

        assert new_config.connect_timeout == 15.0
        assert config.connect_timeout == DEFAULT_CONNECT_TIMEOUT
        assert new_config is not config

        with pytest.raises(ConfigurationError, match="Unknown configuration key"):
            config.update(unknown_key="value")

    @pytest.mark.parametrize(
        "invalid_attrs, error_match",
        [
            ({"alpn_protocols": []}, "cannot be empty"),
            ({"certfile": "a.pem", "keyfile": None}, "must be provided together"),
            ({"congestion_control_algorithm": "invalid_algo"}, "must be one of"),
            ({"connect_timeout": -1}, "Timeout must be positive"),
            ({"connect_timeout": "invalid"}, "Timeout must be a number"),
            ({"connection_idle_timeout": 0}, "Timeout must be positive"),
            ({"flow_control_window_size": 0}, "must be positive"),
            ({"max_capsule_size": 0}, "must be positive"),
            ({"max_connections": 0}, "must be positive"),
            ({"max_datagram_size": 0}, "must be between 1 and 65535"),
            ({"max_datagram_size": 65536}, "must be between 1 and 65535"),
            ({"max_event_history_size": -1}, "must be non-negative"),
            ({"max_event_listeners": 0}, "must be positive"),
            ({"max_event_queue_size": 0}, "must be positive"),
            ({"max_message_size": 0}, "must be positive"),
            ({"max_pending_events_per_session": 0}, "must be positive"),
            ({"max_sessions": 0}, "must be positive"),
            ({"max_stream_read_buffer": 0}, "must be positive"),
            ({"max_stream_write_buffer": 0}, "must be positive"),
            ({"max_total_pending_events": 0}, "must be positive"),
            ({"pending_event_ttl": 0}, "Timeout must be positive"),
            ({"verify_mode": "INVALID"}, "unknown SSL verify mode"),
        ],
    )
    def test_validation_failures(self, invalid_attrs: dict[str, Any], error_match: str) -> None:
        base_config = ClientConfig().to_dict()
        base_config["verify_mode"] = ssl.CERT_REQUIRED
        test_config = {**base_config, **invalid_attrs}
        config = ClientConfig(**test_config)

        with pytest.raises(ConfigurationError, match=error_match):
            config.validate()

    @pytest.mark.parametrize(
        "invalid_attrs, error_match",
        [
            ({"max_connection_retries": -1}, "must be non-negative"),
            ({"max_retry_delay": -10.0}, "must be positive"),
            ({"retry_backoff": 0.9}, "must be >= 1.0"),
            ({"retry_delay": 0}, "must be positive"),
        ],
    )
    def test_validation_failures_retry_logic(self, invalid_attrs: dict[str, Any], error_match: str) -> None:
        base_config = ClientConfig().to_dict()
        base_config["verify_mode"] = ssl.CERT_REQUIRED
        test_config = {**base_config, **invalid_attrs}
        config = ClientConfig(**test_config)

        with pytest.raises(ConfigurationError, match=error_match):
            config.validate()


class TestServerConfig:

    def test_default_initialization(self) -> None:
        config = ServerConfig(certfile="dummy.crt", keyfile="dummy.key")

        assert config.bind_host == "::"
        assert config.max_connections == DEFAULT_SERVER_MAX_CONNECTIONS
        assert config.congestion_control_algorithm == "cubic"
        assert config.flow_control_window_size == DEFAULT_FLOW_CONTROL_WINDOW_SIZE
        assert config.initial_max_data == DEFAULT_INITIAL_MAX_DATA
        assert config.max_capsule_size == DEFAULT_MAX_CAPSULE_SIZE
        assert config.alpn_protocols == DEFAULT_ALPN_PROTOCOLS

    def test_from_dict_coercion(self) -> None:
        config_dict = {"bind_port": "8080", "certfile": "dummy.crt", "keyfile": "dummy.key"}

        config = ServerConfig.from_dict(config_dict=config_dict)

        assert config.bind_port == 8080

    def test_from_dict_enum_conversion_failure_ignored(self) -> None:
        config_dict = {"bind_port": 8080, "certfile": "c", "keyfile": "k", "verify_mode": "INVALID_MODE"}
        config = ServerConfig.from_dict(config_dict=config_dict)

        assert config.verify_mode == "INVALID_MODE"  # type: ignore[comparison-overlap]

        with pytest.raises(ConfigurationError, match="unknown SSL verify mode"):
            config.validate()

    def test_from_dict_enum_conversion_success(self) -> None:
        config_dict = {"bind_port": 8080, "certfile": "c", "keyfile": "k", "verify_mode": "CERT_NONE"}
        config = ServerConfig.from_dict(config_dict=config_dict)

        assert config.verify_mode == ssl.CERT_NONE
        assert isinstance(config.verify_mode, ssl.VerifyMode)

    def test_from_dict_filtering_extra_keys(self) -> None:
        config_dict = {
            "max_connections": 500,
            "unknown_field": "should_be_ignored",
            "certfile": "dummy.crt",
            "keyfile": "dummy.key",
        }

        config = ServerConfig.from_dict(config_dict=config_dict)

        assert config.max_connections == 500
        assert not hasattr(config, "unknown_field")

    def test_from_dict_invalid_port_raises_error(self) -> None:
        config_dict = {"bind_port": "invalid", "certfile": "dummy.crt", "keyfile": "dummy.key"}
        config = ServerConfig.from_dict(config_dict=config_dict)

        with pytest.raises(ConfigurationError, match="Port must be an integer"):
            config.validate()

    def test_from_dict_union_enum_resolution(self) -> None:
        def mock_get_type_hints(obj: Any) -> dict[str, Any]:
            hints = get_type_hints(obj)
            hints["verify_mode"] = Union[ssl.VerifyMode, str]
            hints["bind_host"] = Union[int, str]
            hints["keyfile"] = Union[int, ssl.VerifyMode]
            return hints

        with patch("pywebtransport.config.get_type_hints", side_effect=mock_get_type_hints):
            config1 = ServerConfig.from_dict(config_dict={"verify_mode": "CERT_NONE", "certfile": "c", "keyfile": "k"})
            assert config1.verify_mode == ssl.CERT_NONE

            config2 = ServerConfig.from_dict(config_dict={"bind_host": "localhost", "certfile": "c", "keyfile": "k"})
            assert config2.bind_host == "localhost"

            config3 = ServerConfig.from_dict(config_dict={"keyfile": "CERT_OPTIONAL", "certfile": "c"})
            assert config3.keyfile == ssl.CERT_OPTIONAL  # type: ignore[comparison-overlap]

    def test_initialization_fails_without_bind_host(self) -> None:
        config = ServerConfig(bind_host="", certfile="c", keyfile="k")

        with pytest.raises(ConfigurationError, match="cannot be empty"):
            config.validate()

    def test_initialization_fails_without_certs(self) -> None:
        config = ServerConfig(certfile=None, keyfile=None)

        with pytest.raises(ConfigurationError, match="Server requires both certificate and key files"):
            config.validate()

    def test_to_dict_method(self) -> None:
        config = ServerConfig(verify_mode=ssl.CERT_REQUIRED, certfile="d.crt", keyfile="d.key")

        data = config.to_dict()

        assert data["verify_mode"] == "CERT_REQUIRED"

    def test_update_method_failure(self) -> None:
        config = ServerConfig(certfile="d.crt", keyfile="d.key")

        with pytest.raises(ConfigurationError, match="Unknown configuration key"):
            config.update(unknown_key="value")

    def test_update_method_success(self) -> None:
        config = ServerConfig(certfile="d.crt", keyfile="d.key")

        new_config = config.update(max_connections=500)

        assert new_config.max_connections == 500
        assert config.max_connections == DEFAULT_SERVER_MAX_CONNECTIONS
        assert new_config is not config

    @pytest.mark.parametrize(
        "invalid_attrs, error_match",
        [
            ({"alpn_protocols": []}, "cannot be empty"),
            ({"bind_host": ""}, "cannot be empty"),
            ({"bind_port": 0}, "must be an integer"),
            ({"bind_port": "invalid"}, "must be an integer"),
            ({"congestion_control_algorithm": "invalid_algo"}, "must be one of"),
            ({"flow_control_window_size": 0}, "must be positive"),
            ({"max_capsule_size": 0}, "must be positive"),
            ({"max_connections": 0}, "must be positive"),
            ({"max_datagram_size": 0}, "must be between 1 and 65535"),
            ({"max_datagram_size": 65536}, "must be between 1 and 65535"),
            ({"max_event_history_size": -1}, "must be non-negative"),
            ({"max_event_listeners": 0}, "must be positive"),
            ({"max_event_queue_size": 0}, "must be positive"),
            ({"max_message_size": 0}, "must be positive"),
            ({"max_pending_events_per_session": 0}, "must be positive"),
            ({"max_sessions": 0}, "must be positive"),
            ({"max_stream_read_buffer": 0}, "must be positive"),
            ({"max_stream_write_buffer": 0}, "must be positive"),
            ({"max_total_pending_events": 0}, "must be positive"),
            ({"pending_event_ttl": -1.0}, "Timeout must be positive"),
            ({"read_timeout": "invalid"}, "Timeout must be a number"),
            ({"verify_mode": "INVALID"}, "unknown SSL verify mode"),
        ],
    )
    def test_validation_failures(self, invalid_attrs: dict[str, Any], error_match: str) -> None:
        base_config = ServerConfig(certfile="dummy.crt", keyfile="dummy.key").to_dict()
        base_config["verify_mode"] = ssl.CERT_NONE
        test_config = {**base_config, **invalid_attrs}
        config = ServerConfig(**test_config)

        with pytest.raises(ConfigurationError, match=error_match):
            config.validate()



================================================
FILE: tests/unit/test_connection.py
================================================
import asyncio
import weakref
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from pywebtransport import ClientConfig, ConnectionError, SessionError, TimeoutError, WebTransportSession
from pywebtransport._adapter.client import WebTransportClientProtocol
from pywebtransport._protocol.events import (
    ConnectionClose,
    UserConnectionGracefulClose,
    UserCreateSession,
    UserGetConnectionDiagnostics,
)
from pywebtransport.connection import ConnectionDiagnostics, WebTransportConnection
from pywebtransport.types import ConnectionState, EventType, StreamDirection


class TestConnectionDiagnostics:

    def test_init(self) -> None:
        diag = ConnectionDiagnostics(
            connection_id="uuid-123",
            state=ConnectionState.CONNECTED,
            is_client=True,
            connected_at=100.0,
            closed_at=None,
            max_datagram_size=1200,
            remote_max_datagram_frame_size=1200,
            handshake_complete=True,
            peer_settings_received=True,
            local_goaway_sent=False,
            session_count=1,
            stream_count=2,
            pending_request_count=0,
            early_event_count=0,
            active_session_handles=1,
            active_stream_handles=2,
        )

        assert diag.connection_id == "uuid-123"
        assert diag.state == ConnectionState.CONNECTED


class TestWebTransportConnection:

    @pytest.fixture
    def mock_config(self, mocker: MockerFixture) -> MagicMock:
        conf = mocker.Mock(spec=ClientConfig)
        conf.max_event_queue_size = 100
        conf.max_event_listeners = 100
        conf.max_event_history_size = 100
        return cast(MagicMock, conf)

    @pytest.fixture
    def mock_protocol(self, mocker: MockerFixture) -> MagicMock:
        proto = mocker.Mock(spec=WebTransportClientProtocol)
        proto.create_request.side_effect = lambda: (1, asyncio.Future())
        return cast(MagicMock, proto)

    @pytest.fixture
    def mock_transport(self, mocker: MockerFixture) -> MagicMock:
        transport = mocker.Mock(spec=asyncio.DatagramTransport)
        transport.is_closing.return_value = False
        transport.get_extra_info.return_value = ("127.0.0.1", 12345)
        return cast(MagicMock, transport)

    @pytest.fixture
    def connection(
        self,
        mock_config: MagicMock,
        mock_protocol: MagicMock,
        mock_transport: MagicMock,
        mocker: MockerFixture,
    ) -> WebTransportConnection:
        conn = WebTransportConnection(
            config=mock_config, protocol=mock_protocol, transport=mock_transport, is_client=True
        )
        conn.events = mocker.Mock()
        return conn

    @pytest.fixture
    def mock_session_cls(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("pywebtransport.connection.WebTransportSession")

    def test_init(
        self,
        connection: WebTransportConnection,
        mock_config: MagicMock,
        mock_protocol: MagicMock,
        mock_transport: MagicMock,
    ) -> None:
        assert connection.config == mock_config
        assert connection.is_client is True
        assert connection._transport == mock_transport
        mock_protocol.set_status_callback.assert_called_once_with(callback=connection._notify_owner)

    def test_accept_factory(self, mock_transport: MagicMock, mock_protocol: MagicMock, mock_config: MagicMock) -> None:
        conn = WebTransportConnection.accept(transport=mock_transport, protocol=mock_protocol, config=mock_config)
        assert isinstance(conn, WebTransportConnection)
        assert conn.is_client is False
        assert conn.config == mock_config

    @pytest.mark.asyncio
    async def test_connect_factory(self, mocker: MockerFixture, mock_config: MagicMock) -> None:
        mock_endpoint = mocker.patch(
            "pywebtransport.connection.create_quic_endpoint",
            return_value=(mocker.Mock(), mocker.Mock()),
        )
        conn = await WebTransportConnection.connect(host="example.com", port=443, config=mock_config)

        assert isinstance(conn, WebTransportConnection)
        assert conn.is_client is True
        mock_endpoint.assert_awaited_once()

    def test_properties(self, connection: WebTransportConnection) -> None:
        assert isinstance(connection.connection_id, str)
        assert connection.state == ConnectionState.IDLE
        assert connection.is_closed is False
        assert connection.is_closing is False
        assert connection.is_connected is False

    def test_address_properties(self, connection: WebTransportConnection, mock_transport: MagicMock) -> None:
        mock_transport.get_extra_info.side_effect = lambda k: ("127.0.0.1", 443) if k == "peername" else ("0.0.0.0", 0)

        assert connection.remote_address == ("127.0.0.1", 443)
        assert connection.local_address == ("0.0.0.0", 0)

    def test_address_properties_invalid_format(
        self, connection: WebTransportConnection, mock_transport: MagicMock
    ) -> None:
        mock_transport.get_extra_info.return_value = None
        assert connection.remote_address is None
        assert connection.local_address is None

        mock_transport.get_extra_info.return_value = ("path",)
        assert connection.remote_address is None

    def test_repr(self, connection: WebTransportConnection) -> None:
        assert "WebTransportConnection" in repr(connection)
        assert "id=" in repr(connection)

    @pytest.mark.asyncio
    async def test_close_success(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mock_transport: MagicMock
    ) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (123, fut)
        fut.set_result(None)

        await connection.close()

        mock_protocol.create_request.assert_called_once()
        mock_protocol.send_event.assert_called_once()
        event = mock_protocol.send_event.call_args[1]["event"]
        assert isinstance(event, ConnectionClose)
        assert event.request_id == 123

        mock_transport.close.assert_called_once()
        assert connection.state == ConnectionState.CLOSED

    @pytest.mark.asyncio
    async def test_close_idempotent(self, connection: WebTransportConnection, mock_protocol: MagicMock) -> None:
        connection._cached_state = ConnectionState.CLOSED
        await connection.close()
        mock_protocol.create_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_timeout(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        mocker.patch("asyncio.timeout", side_effect=asyncio.TimeoutError)

        await connection.close()

        assert connection.state == ConnectionState.CLOSED
        cast(MagicMock, connection._transport.close).assert_called()

    @pytest.mark.asyncio
    async def test_close_connection_error_debug(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        mocker.patch("asyncio.timeout", side_effect=ConnectionError("Connection closed"))
        spy_logger = mocker.patch("pywebtransport.connection.logger")

        await connection.close()

        spy_logger.debug.assert_any_call("Connection closed while waiting for close confirmation: %s", mocker.ANY)
        assert connection.state == ConnectionState.CLOSED

    @pytest.mark.asyncio
    async def test_close_connection_error_warning(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        mocker.patch("asyncio.timeout", side_effect=ConnectionError("Something failed"))
        spy_logger = mocker.patch("pywebtransport.connection.logger")

        await connection.close()

        spy_logger.warning.assert_called_with("Connection error during close: %s", mocker.ANY)

    @pytest.mark.asyncio
    async def test_close_generic_exception(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        mocker.patch("asyncio.timeout", side_effect=ValueError("Unexpected"))
        spy_logger = mocker.patch("pywebtransport.connection.logger")

        await connection.close()

        spy_logger.warning.assert_called_with("Error during close event processing: %s", mocker.ANY)

    @pytest.mark.asyncio
    async def test_close_server_does_not_close_transport(
        self, connection: WebTransportConnection, mock_protocol: MagicMock
    ) -> None:
        connection._is_client = False
        fut: asyncio.Future[None] = asyncio.Future()
        fut.set_result(None)
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        await connection.close()

        cast(MagicMock, connection._transport.close).assert_not_called()

    @pytest.mark.asyncio
    async def test_close_transport_already_closing(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mock_transport: MagicMock
    ) -> None:
        mock_transport.is_closing.return_value = True
        fut: asyncio.Future[None] = asyncio.Future()
        fut.set_result(None)
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        await connection.close()

        mock_transport.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_context_manager(self, connection: WebTransportConnection, mocker: MockerFixture) -> None:
        spy_close = mocker.patch.object(connection, "close", new_callable=mocker.AsyncMock)

        async with connection as c:
            assert c is connection

        spy_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_success(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        fut.set_result(None)
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        spy_close = mocker.spy(connection, "close")

        await connection.graceful_shutdown()

        assert mock_protocol.send_event.call_count == 2
        calls = mock_protocol.send_event.call_args_list
        event1 = calls[0].kwargs["event"]
        assert isinstance(event1, UserConnectionGracefulClose)
        event2 = calls[1].kwargs["event"]
        assert isinstance(event2, ConnectionClose)

        spy_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_timeout(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, asyncio.Future())
        mocker.patch("asyncio.timeout", side_effect=asyncio.TimeoutError)
        spy_logger = mocker.patch("pywebtransport.connection.logger")

        await connection.graceful_shutdown()

        spy_logger.warning.assert_any_call("Timeout waiting for graceful shutdown GOAWAY confirmation.")

    @pytest.mark.asyncio
    async def test_graceful_shutdown_error(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, asyncio.Future())
        mocker.patch("asyncio.timeout", side_effect=Exception("Error"))
        spy_logger = mocker.patch("pywebtransport.connection.logger")

        await connection.graceful_shutdown()

        spy_logger.warning.assert_any_call("Error during graceful shutdown: %s", mocker.ANY)

    @pytest.mark.asyncio
    async def test_create_session_success(
        self, connection: WebTransportConnection, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (100, fut)

        session_mock = mocker.Mock(spec=WebTransportSession)
        connection._session_handles[1] = session_mock
        fut.set_result(1)

        session = await connection.create_session(path="/", headers={"a": "b"})

        assert session is session_mock
        event = mock_protocol.send_event.call_args[1]["event"]
        assert isinstance(event, UserCreateSession)
        assert event.request_id == 100
        assert event.path == "/"
        assert event.headers == {"a": "b"}

    @pytest.mark.asyncio
    async def test_create_session_server_error(self, connection: WebTransportConnection) -> None:
        connection._is_client = False
        with pytest.raises(ConnectionError, match="Sessions can only be created by the client"):
            await connection.create_session(path="/")

    @pytest.mark.asyncio
    async def test_create_session_timeout(self, connection: WebTransportConnection, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (100, fut)
        fut.set_exception(asyncio.TimeoutError("Timeout"))

        with pytest.raises(TimeoutError, match="Session creation timed out"):
            await connection.create_session(path="/")

    @pytest.mark.asyncio
    async def test_create_session_cancelled(self, connection: WebTransportConnection, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (100, fut)
        fut.cancel()

        with pytest.raises(asyncio.CancelledError):
            await connection.create_session(path="/")

    @pytest.mark.asyncio
    async def test_create_session_generic_error(
        self, connection: WebTransportConnection, mock_protocol: MagicMock
    ) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (100, fut)
        fut.set_exception(ValueError("Fail"))

        with pytest.raises(SessionError, match="Session creation failed"):
            await connection.create_session(path="/")

    @pytest.mark.asyncio
    async def test_create_session_connection_error_propagates(
        self, connection: WebTransportConnection, mock_protocol: MagicMock
    ) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (100, fut)
        fut.set_exception(ConnectionError("Fail"))

        with pytest.raises(ConnectionError):
            await connection.create_session(path="/")

    @pytest.mark.asyncio
    async def test_create_session_handle_missing(
        self, connection: WebTransportConnection, mock_protocol: MagicMock
    ) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (100, fut)
        fut.set_result(1)

        with pytest.raises(SessionError, match="Internal error creating session handle"):
            await connection.create_session(path="/")

    @pytest.mark.asyncio
    async def test_diagnostics_success(self, connection: WebTransportConnection, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[dict[str, Any]] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        diag_raw = {
            "connection_id": "cid",
            "state": ConnectionState.CONNECTED,
            "is_client": True,
            "connected_at": 1.0,
            "closed_at": None,
            "max_datagram_size": 1200,
            "remote_max_datagram_frame_size": 1200,
            "handshake_complete": True,
            "peer_settings_received": True,
            "local_goaway_sent": False,
            "session_count": 1,
            "stream_count": 0,
            "pending_request_count": 0,
            "early_event_count": 0,
        }
        fut.set_result(diag_raw)

        diag = await connection.diagnostics()

        assert isinstance(diag, ConnectionDiagnostics)
        assert diag.connection_id == "cid"
        assert diag.active_session_handles == 0

        mock_protocol.send_event.assert_called_once()
        event = mock_protocol.send_event.call_args[1]["event"]
        assert isinstance(event, UserGetConnectionDiagnostics)

    def test_get_all_sessions(self, connection: WebTransportConnection, mocker: MockerFixture) -> None:
        s1 = mocker.Mock()
        connection._session_handles[1] = s1
        assert connection.get_all_sessions() == [s1]

    def test_notify_owner_connection_events(self, connection: WebTransportConnection, mocker: MockerFixture) -> None:
        connection._cached_state = ConnectionState.IDLE

        connection._notify_owner(EventType.CONNECTION_ESTABLISHED, {})
        assert connection.state == ConnectionState.CONNECTED
        cast(MagicMock, connection.events.emit_nowait).assert_called_with(
            event_type=EventType.CONNECTION_ESTABLISHED, data=mocker.ANY
        )
        assert isinstance(
            cast(MagicMock, connection.events.emit_nowait).call_args[1]["data"]["connection"], weakref.ProxyType
        )

        connection._notify_owner(EventType.CONNECTION_CLOSED, {})
        assert connection.state == ConnectionState.CLOSED  # type: ignore[comparison-overlap]

    def test_notify_owner_data_already_populated(
        self, connection: WebTransportConnection, mocker: MockerFixture
    ) -> None:
        existing_obj = "mock_obj"
        existing_id = "mock_id"
        data = {"connection": existing_obj, "connection_id": existing_id}

        connection._notify_owner(EventType.DATAGRAM_RECEIVED, data)
        assert data["connection"] == existing_obj
        assert data["connection_id"] == connection.connection_id

    def test_notify_owner_exception_handler(self, connection: WebTransportConnection, mocker: MockerFixture) -> None:
        cast(MagicMock, connection.events.emit_nowait).side_effect = ValueError("Boom")
        spy_logger = mocker.patch("pywebtransport.connection.logger")

        connection._notify_owner(EventType.CONNECTION_ESTABLISHED, {})

        spy_logger.error.assert_called_with("Error during owner notification callback: %s", mocker.ANY, exc_info=True)

    def test_handle_session_event_client_ready(
        self, connection: WebTransportConnection, mock_session_cls: MagicMock, mocker: MockerFixture
    ) -> None:
        data = {"session_id": 1, "path": "/", "headers": {}}

        connection._notify_owner(EventType.SESSION_READY, data)

        assert 1 in connection._session_handles
        assert connection._session_handles[1] == mock_session_cls.return_value
        assert data["session"] == mock_session_cls.return_value

    def test_handle_session_event_handle_exists(
        self, connection: WebTransportConnection, mocker: MockerFixture
    ) -> None:
        data = {"session_id": 1, "path": "/", "headers": {}}
        existing_session = mocker.Mock()
        connection._session_handles[1] = existing_session

        connection._notify_owner(EventType.SESSION_READY, data)
        assert connection._session_handles[1] is existing_session

    def test_handle_session_event_server_request(
        self, connection: WebTransportConnection, mock_session_cls: MagicMock
    ) -> None:
        connection._is_client = False
        data = {"session_id": 2, "path": "/", "headers": {}}

        connection._notify_owner(EventType.SESSION_REQUEST, data)
        assert 2 in connection._session_handles

    def test_handle_session_event_missing_metadata(
        self, connection: WebTransportConnection, mocker: MockerFixture
    ) -> None:
        spy_logger = mocker.patch("pywebtransport.connection.logger")
        data = {"session_id": 1}

        connection._notify_owner(EventType.SESSION_READY, data)

        assert 1 not in connection._session_handles
        spy_logger.error.assert_called_with("Missing metadata for session handle creation %s", 1)

    def test_handle_session_event_no_id(self, connection: WebTransportConnection) -> None:
        connection._notify_owner(EventType.SESSION_READY, {})
        assert not connection._session_handles

    def test_route_session_event_and_close(self, connection: WebTransportConnection, mocker: MockerFixture) -> None:
        session_handle = mocker.Mock()
        session_handle.events = mocker.Mock()
        connection._session_handles[1] = session_handle

        connection._notify_owner(EventType.SESSION_DATA_BLOCKED, {"session_id": 1})
        cast(MagicMock, session_handle.events.emit_nowait).assert_called()

        connection._notify_owner(EventType.SESSION_CLOSED, {"session_id": 1})
        assert 1 not in connection._session_handles

    def test_route_session_event_missing_id(self, connection: WebTransportConnection) -> None:
        connection._notify_owner(EventType.SESSION_DATA_BLOCKED, {})

    @pytest.mark.parametrize(
        "direction",
        [StreamDirection.BIDIRECTIONAL, StreamDirection.SEND_ONLY, StreamDirection.RECEIVE_ONLY],
    )
    def test_handle_stream_event_opened_success(
        self, connection: WebTransportConnection, mocker: MockerFixture, direction: StreamDirection
    ) -> None:
        session_handle = mocker.Mock()
        session_handle.events = mocker.Mock()
        connection._session_handles[1] = session_handle

        mock_bidi = mocker.patch("pywebtransport.connection.WebTransportStream", return_value=mocker.Mock())
        mock_send = mocker.patch("pywebtransport.connection.WebTransportSendStream", return_value=mocker.Mock())
        mock_recv = mocker.patch("pywebtransport.connection.WebTransportReceiveStream", return_value=mocker.Mock())

        data = {"stream_id": 10, "session_id": 1, "direction": direction}

        connection._notify_owner(EventType.STREAM_OPENED, data)

        assert 10 in connection._stream_handles
        cast(MagicMock, session_handle.events.emit_nowait).assert_called()

        if direction == StreamDirection.BIDIRECTIONAL:
            mock_bidi.assert_called_once()
        elif direction == StreamDirection.SEND_ONLY:
            mock_send.assert_called_once()
        elif direction == StreamDirection.RECEIVE_ONLY:
            mock_recv.assert_called_once()

    def test_handle_stream_event_opened_invalid_direction(
        self, connection: WebTransportConnection, mocker: MockerFixture
    ) -> None:
        session_handle = mocker.Mock()
        connection._session_handles[1] = session_handle
        spy_logger = mocker.patch("pywebtransport.connection.logger")

        data = {"stream_id": 10, "session_id": 1, "direction": 999}

        connection._notify_owner(EventType.STREAM_OPENED, data)

        assert 10 not in connection._stream_handles
        spy_logger.error.assert_called_with("Unknown stream direction: %s", 999)

    def test_handle_stream_event_opened_missing_session(
        self, connection: WebTransportConnection, mocker: MockerFixture
    ) -> None:
        spy_logger = mocker.patch("pywebtransport.connection.logger")
        data = {"stream_id": 10, "session_id": 999, "direction": StreamDirection.BIDIRECTIONAL}

        connection._notify_owner(EventType.STREAM_OPENED, data)

        spy_logger.warning.assert_called_with("Session %s not found for stream %d", 999, 10)
        assert 10 not in connection._stream_handles

    def test_handle_stream_event_opened_missing_metadata(self, connection: WebTransportConnection) -> None:
        data = {"stream_id": 10}
        connection._notify_owner(EventType.STREAM_OPENED, data)
        assert 10 not in connection._stream_handles

    def test_handle_stream_event_no_id(self, connection: WebTransportConnection) -> None:
        connection._notify_owner(EventType.STREAM_OPENED, {})
        assert not connection._stream_handles

    def test_handle_stream_event_closed(self, connection: WebTransportConnection, mocker: MockerFixture) -> None:
        stream_handle = mocker.Mock()
        stream_handle.events = mocker.Mock()
        connection._stream_handles[10] = stream_handle

        data = {"stream_id": 10}
        connection._notify_owner(EventType.STREAM_CLOSED, data)

        assert 10 not in connection._stream_handles
        cast(MagicMock, stream_handle.events.emit_nowait).assert_called()

    def test_handle_stream_event_closed_missing(
        self, connection: WebTransportConnection, mocker: MockerFixture
    ) -> None:
        data = {"stream_id": 999}
        connection._notify_owner(EventType.STREAM_CLOSED, data)
        assert 999 not in connection._stream_handles

    def test_handle_stream_event_dispatch_unknown_type(self, connection: WebTransportConnection) -> None:
        connection._handle_stream_event(event_type=EventType.DATAGRAM_RECEIVED, data={"stream_id": 1})



================================================
FILE: tests/unit/test_constants.py
================================================
"""Unit tests for the pywebtransport.constants module."""

from enum import IntEnum

import pytest

from pywebtransport import ErrorCodes
from pywebtransport.constants import (
    DEFAULT_ALPN_PROTOCOLS,
    DEFAULT_BIND_HOST,
    DEFAULT_CLIENT_MAX_CONNECTIONS,
    DEFAULT_CLIENT_MAX_SESSIONS,
    DEFAULT_CLOSE_TIMEOUT,
    DEFAULT_CONGESTION_CONTROL_ALGORITHM,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_CONNECTION_IDLE_TIMEOUT,
    DEFAULT_DEV_PORT,
    DEFAULT_FLOW_CONTROL_WINDOW_AUTO_SCALE,
    DEFAULT_FLOW_CONTROL_WINDOW_SIZE,
    DEFAULT_INITIAL_MAX_DATA,
    DEFAULT_INITIAL_MAX_STREAMS_BIDI,
    DEFAULT_INITIAL_MAX_STREAMS_UNI,
    DEFAULT_KEEP_ALIVE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_CAPSULE_SIZE,
    DEFAULT_MAX_CONNECTION_RETRIES,
    DEFAULT_MAX_DATAGRAM_SIZE,
    DEFAULT_MAX_EVENT_HISTORY_SIZE,
    DEFAULT_MAX_EVENT_LISTENERS,
    DEFAULT_MAX_EVENT_QUEUE_SIZE,
    DEFAULT_MAX_MESSAGE_SIZE,
    DEFAULT_MAX_PENDING_EVENTS_PER_SESSION,
    DEFAULT_MAX_RETRY_DELAY,
    DEFAULT_MAX_STREAM_READ_BUFFER,
    DEFAULT_MAX_STREAM_WRITE_BUFFER,
    DEFAULT_MAX_TOTAL_PENDING_EVENTS,
    DEFAULT_PENDING_EVENT_TTL,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_RESOURCE_CLEANUP_INTERVAL,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SERVER_MAX_CONNECTIONS,
    DEFAULT_SERVER_MAX_SESSIONS,
    DEFAULT_STREAM_CREATION_TIMEOUT,
    DEFAULT_WRITE_TIMEOUT,
    H3_FRAME_TYPE_WEBTRANSPORT_STREAM,
    MAX_CLOSE_REASON_BYTES,
    MAX_PROTOCOL_STREAMS_LIMIT,
    MAX_STREAM_ID,
    QPACK_DECODER_MAX_BLOCKED_STREAMS,
    QPACK_DECODER_MAX_TABLE_CAPACITY,
    SETTINGS_WT_INITIAL_MAX_DATA,
    SETTINGS_WT_INITIAL_MAX_STREAMS_BIDI,
    SETTINGS_WT_INITIAL_MAX_STREAMS_UNI,
    SUPPORTED_CONGESTION_CONTROL_ALGORITHMS,
    USER_AGENT_HEADER,
    WEBTRANSPORT_DEFAULT_PORT,
    WEBTRANSPORT_SCHEME,
    WT_DATA_BLOCKED_TYPE,
    WT_MAX_DATA_TYPE,
    WT_MAX_STREAM_DATA_TYPE,
    WT_MAX_STREAMS_BIDI_TYPE,
    WT_MAX_STREAMS_UNI_TYPE,
    WT_STREAM_DATA_BLOCKED_TYPE,
    WT_STREAMS_BLOCKED_BIDI_TYPE,
    WT_STREAMS_BLOCKED_UNI_TYPE,
)


class TestConstantsValues:

    def test_top_level_constants_values(self) -> None:
        assert H3_FRAME_TYPE_WEBTRANSPORT_STREAM == 0x41
        assert MAX_CLOSE_REASON_BYTES == 1024
        assert MAX_PROTOCOL_STREAMS_LIMIT == 2**60
        assert MAX_STREAM_ID == 2**62 - 1
        assert QPACK_DECODER_MAX_BLOCKED_STREAMS == 16
        assert QPACK_DECODER_MAX_TABLE_CAPACITY == 4096
        assert SETTINGS_WT_INITIAL_MAX_DATA == 0x2B61
        assert SETTINGS_WT_INITIAL_MAX_STREAMS_BIDI == 0x2B65
        assert SETTINGS_WT_INITIAL_MAX_STREAMS_UNI == 0x2B64
        assert USER_AGENT_HEADER == "user-agent"
        assert WEBTRANSPORT_SCHEME == "https"
        assert WEBTRANSPORT_DEFAULT_PORT == 443
        assert WT_DATA_BLOCKED_TYPE == 0x190B4D41
        assert WT_MAX_DATA_TYPE == 0x190B4D3D
        assert WT_MAX_STREAM_DATA_TYPE == 0x190B4D3E
        assert WT_MAX_STREAMS_BIDI_TYPE == 0x190B4D3F
        assert WT_MAX_STREAMS_UNI_TYPE == 0x190B4D40
        assert WT_STREAM_DATA_BLOCKED_TYPE == 0x190B4D42
        assert WT_STREAMS_BLOCKED_BIDI_TYPE == 0x190B4D43
        assert WT_STREAMS_BLOCKED_UNI_TYPE == 0x190B4D44
        assert DEFAULT_ALPN_PROTOCOLS == ["h3"]
        assert DEFAULT_BIND_HOST == "::"
        assert DEFAULT_CLIENT_MAX_CONNECTIONS == 100
        assert DEFAULT_CLIENT_MAX_SESSIONS == 100
        assert DEFAULT_CLOSE_TIMEOUT == 5.0
        assert DEFAULT_CONGESTION_CONTROL_ALGORITHM == "cubic"
        assert DEFAULT_CONNECT_TIMEOUT == 30.0
        assert DEFAULT_CONNECTION_IDLE_TIMEOUT == 60.0
        assert DEFAULT_DEV_PORT == 4433
        assert DEFAULT_FLOW_CONTROL_WINDOW_AUTO_SCALE is True
        assert DEFAULT_FLOW_CONTROL_WINDOW_SIZE == 1024 * 1024
        assert DEFAULT_INITIAL_MAX_DATA == 10 * 1024 * 1024
        assert DEFAULT_INITIAL_MAX_STREAMS_BIDI == 100
        assert DEFAULT_INITIAL_MAX_STREAMS_UNI == 100
        assert DEFAULT_KEEP_ALIVE is True
        assert DEFAULT_LOG_LEVEL == "INFO"
        assert DEFAULT_MAX_CAPSULE_SIZE == 65536
        assert DEFAULT_MAX_CONNECTION_RETRIES == 3
        assert DEFAULT_MAX_DATAGRAM_SIZE == 1350
        assert DEFAULT_MAX_EVENT_HISTORY_SIZE == 0
        assert DEFAULT_MAX_EVENT_LISTENERS == 100
        assert DEFAULT_MAX_EVENT_QUEUE_SIZE == 1000
        assert DEFAULT_MAX_MESSAGE_SIZE == 1024 * 1024
        assert DEFAULT_MAX_PENDING_EVENTS_PER_SESSION == 100
        assert DEFAULT_MAX_RETRY_DELAY == 30.0
        assert DEFAULT_MAX_STREAM_READ_BUFFER == 2 * 1024 * 1024
        assert DEFAULT_MAX_STREAM_WRITE_BUFFER == 2 * 1024 * 1024
        assert DEFAULT_MAX_TOTAL_PENDING_EVENTS == 1000
        assert DEFAULT_PENDING_EVENT_TTL == 5.0
        assert DEFAULT_READ_TIMEOUT == 60.0
        assert DEFAULT_RESOURCE_CLEANUP_INTERVAL == 15.0
        assert DEFAULT_RETRY_BACKOFF == 2.0
        assert DEFAULT_RETRY_DELAY == 1.0
        assert DEFAULT_SERVER_MAX_CONNECTIONS == 3000
        assert DEFAULT_SERVER_MAX_SESSIONS == 10000
        assert DEFAULT_STREAM_CREATION_TIMEOUT == 10.0
        assert DEFAULT_WRITE_TIMEOUT == 30.0
        assert SUPPORTED_CONGESTION_CONTROL_ALGORITHMS == ["reno", "cubic"]


class TestErrorCodes:

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            (ErrorCodes.NO_ERROR, 0x0),
            (ErrorCodes.INTERNAL_ERROR, 0x1),
            (ErrorCodes.CONNECTION_REFUSED, 0x2),
            (ErrorCodes.FLOW_CONTROL_ERROR, 0x3),
            (ErrorCodes.STREAM_LIMIT_ERROR, 0x4),
            (ErrorCodes.STREAM_STATE_ERROR, 0x5),
            (ErrorCodes.FINAL_SIZE_ERROR, 0x6),
            (ErrorCodes.FRAME_ENCODING_ERROR, 0x7),
            (ErrorCodes.TRANSPORT_PARAMETER_ERROR, 0x8),
            (ErrorCodes.CONNECTION_ID_LIMIT_ERROR, 0x9),
            (ErrorCodes.PROTOCOL_VIOLATION, 0xA),
            (ErrorCodes.INVALID_TOKEN, 0xB),
            (ErrorCodes.APPLICATION_ERROR, 0xC),
            (ErrorCodes.CRYPTO_BUFFER_EXCEEDED, 0xD),
            (ErrorCodes.KEY_UPDATE_ERROR, 0xE),
            (ErrorCodes.AEAD_LIMIT_REACHED, 0xF),
            (ErrorCodes.NO_VIABLE_PATH, 0x10),
            (ErrorCodes.H3_DATAGRAM_ERROR, 0x33),
            (ErrorCodes.H3_NO_ERROR, 0x100),
            (ErrorCodes.H3_GENERAL_PROTOCOL_ERROR, 0x101),
            (ErrorCodes.H3_INTERNAL_ERROR, 0x102),
            (ErrorCodes.H3_STREAM_CREATION_ERROR, 0x103),
            (ErrorCodes.H3_CLOSED_CRITICAL_STREAM, 0x104),
            (ErrorCodes.H3_FRAME_UNEXPECTED, 0x105),
            (ErrorCodes.H3_FRAME_ERROR, 0x106),
            (ErrorCodes.H3_EXCESSIVE_LOAD, 0x107),
            (ErrorCodes.H3_ID_ERROR, 0x108),
            (ErrorCodes.H3_SETTINGS_ERROR, 0x109),
            (ErrorCodes.H3_MISSING_SETTINGS, 0x10A),
            (ErrorCodes.H3_REQUEST_REJECTED, 0x10B),
            (ErrorCodes.H3_REQUEST_CANCELLED, 0x10C),
            (ErrorCodes.H3_REQUEST_INCOMPLETE, 0x10D),
            (ErrorCodes.H3_MESSAGE_ERROR, 0x10E),
            (ErrorCodes.H3_CONNECT_ERROR, 0x10F),
            (ErrorCodes.H3_VERSION_FALLBACK, 0x110),
            (ErrorCodes.QPACK_DECODER_STREAM_ERROR, 0x202),
            (ErrorCodes.QPACK_DECOMPRESSION_FAILED, 0x200),
            (ErrorCodes.QPACK_ENCODER_STREAM_ERROR, 0x201),
            (ErrorCodes.WT_SESSION_GONE, 0x170D7B68),
            (ErrorCodes.WT_BUFFERED_STREAM_REJECTED, 0x3994BD84),
            (ErrorCodes.WT_FLOW_CONTROL_ERROR, 0x045D4487),
            (ErrorCodes.WT_APPLICATION_ERROR_FIRST, 0x52E4A40FA8DB),
            (ErrorCodes.WT_APPLICATION_ERROR_LAST, 0x52E5AC983162),
            (ErrorCodes.APP_CONNECTION_TIMEOUT, 0x1000),
            (ErrorCodes.APP_AUTHENTICATION_FAILED, 0x1001),
            (ErrorCodes.APP_PERMISSION_DENIED, 0x1002),
            (ErrorCodes.APP_RESOURCE_EXHAUSTED, 0x1003),
            (ErrorCodes.APP_INVALID_REQUEST, 0x1004),
            (ErrorCodes.APP_SERVICE_UNAVAILABLE, 0x1005),
            (ErrorCodes.LIB_INTERNAL_ERROR, 0x10000001),
            (ErrorCodes.LIB_CONNECTION_STATE_ERROR, 0x11000001),
            (ErrorCodes.LIB_SESSION_STATE_ERROR, 0x12000001),
            (ErrorCodes.LIB_STREAM_STATE_ERROR, 0x13000001),
        ],
    )
    def test_error_code_values(self, member: ErrorCodes, expected_value: int) -> None:
        assert member.value == expected_value

    def test_error_codes_is_int_enum(self) -> None:
        assert issubclass(ErrorCodes, IntEnum)



================================================
FILE: tests/unit/test_events.py
================================================
"""Unit tests for the pywebtransport.events module."""

import asyncio
from typing import Any

import pytest
from pytest_mock import MockerFixture

from pywebtransport import Event
from pywebtransport.events import EventEmitter
from pywebtransport.types import EventType


@pytest.fixture
def mock_logger(mocker: MockerFixture) -> Any:
    return mocker.patch("pywebtransport.events.logger")


@pytest.fixture(autouse=True)
def mock_timestamp(mocker: MockerFixture) -> None:
    mocker.patch("time.perf_counter", return_value=12345.6789)


class TestEvent:

    def test_event_equality(self) -> None:
        event1 = Event(type=EventType.SESSION_READY, timestamp=100.0)
        event2 = Event(type=EventType.SESSION_READY, timestamp=100.0)
        event3 = Event(type=EventType.SESSION_READY, timestamp=200.0)

        assert event1 == event2
        assert event1 != event3

    def test_event_explicit_init(self) -> None:
        event = Event(type=EventType.SESSION_READY, timestamp=999.99, data={"foo": "bar"}, source="src")

        assert event.timestamp == 999.99
        assert event.data == {"foo": "bar"}
        assert event.source == "src"

    def test_init_with_non_string_type(self) -> None:
        event = Event(type=123)  # type: ignore[arg-type]
        assert event.type == 123  # type: ignore[comparison-overlap]

    def test_initialization_with_enum(self) -> None:
        event = Event(type=EventType.CONNECTION_ESTABLISHED)

        assert event.type == EventType.CONNECTION_ESTABLISHED
        assert event.timestamp == 12345.6789
        assert event.data is None

    def test_post_init_str_to_enum_conversion(self) -> None:
        event = Event(type="connection_established")

        assert event.type == EventType.CONNECTION_ESTABLISHED

    def test_post_init_unknown_str_logs_warning(self, mock_logger: Any) -> None:
        event = Event(type="custom_event")

        assert event.type == "custom_event"
        mock_logger.warning.assert_called_once_with("Unknown event type string: '%s'", "custom_event")

    def test_repr_and_str(self) -> None:
        event = Event(type=EventType.CONNECTION_FAILED)

        assert repr(event) == "Event(type=connection_failed, timestamp=12345.6789)"
        assert str(event) == "Event(connection_failed)"

    def test_to_dict(self) -> None:
        event = Event(type=EventType.SESSION_READY, data={"id": 1}, source="test_source")
        expected_dict = {
            "type": EventType.SESSION_READY,
            "timestamp": 12345.6789,
            "data": {"id": 1},
            "source": "test_source",
        }

        event_dict = event.to_dict()

        assert event_dict == expected_dict

    def test_to_dict_with_none_source(self) -> None:
        event = Event(type=EventType.SESSION_READY, data={"id": 1}, source=None)

        event_dict = event.to_dict()

        assert event_dict["source"] is None


class TestEventEmitter:

    @pytest.fixture
    def emitter(self) -> EventEmitter:
        return EventEmitter(max_listeners=3, max_history=10)

    @pytest.mark.asyncio
    async def test_clear_history(self, emitter: EventEmitter) -> None:
        await emitter.emit(event_type=EventType.SESSION_READY)
        assert len(emitter.get_event_history()) == 1

        emitter.clear_history()

        assert len(emitter.get_event_history()) == 0

    @pytest.mark.asyncio
    async def test_close(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        real_task = asyncio.create_task(coro=asyncio.sleep(delay=10))
        cancel_spy = mocker.spy(real_task, "cancel")
        emitter._processing_task = real_task
        emitter.on(event_type=EventType.SESSION_READY, handler=mocker.Mock())

        await emitter.close()

        cancel_spy.assert_called_once()
        assert real_task.cancelled()
        assert emitter.get_stats()["total_handlers"] == 0

    @pytest.mark.asyncio
    async def test_close_cancels_background_tasks(self, emitter: EventEmitter) -> None:
        async def hang() -> None:
            await asyncio.sleep(10)

        async def quick() -> None:
            pass

        task1 = asyncio.create_task(hang())
        task2 = asyncio.create_task(quick())

        await task2

        emitter._background_tasks.add(task1)
        emitter._background_tasks.add(task2)

        await asyncio.sleep(0)

        await emitter.close()

        with pytest.raises(asyncio.CancelledError):
            await task1

        assert task1.cancelled()
        assert task2.done()
        assert not task2.cancelled()

    @pytest.mark.asyncio
    async def test_close_with_done_task(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        mock_task = mocker.Mock(done=lambda: True)
        emitter._processing_task = mock_task

        await emitter.close()

        mock_task.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_emit_nowait_no_loop(self, emitter: EventEmitter, mocker: MockerFixture, mock_logger: Any) -> None:
        mocker.patch("asyncio.create_task", side_effect=RuntimeError)
        mocker.patch.object(emitter, "_process_event", new_callable=mocker.Mock)
        handler = mocker.AsyncMock()
        emitter.on(event_type=EventType.SESSION_READY, handler=handler)

        emitter.emit_nowait(event_type=EventType.SESSION_READY)

        mock_logger.warning.assert_called_once()
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_emit_nowait_paused(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.AsyncMock()
        emitter.on(event_type=EventType.SESSION_READY, handler=handler)
        emitter.pause()

        emitter.emit_nowait(event_type=EventType.SESSION_READY)
        await asyncio.sleep(delay=0)

        handler.assert_not_awaited()
        assert emitter.get_stats()["queued_events"] == 1

    @pytest.mark.asyncio
    async def test_emit_nowait_success(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.AsyncMock()
        emitter.on(event_type=EventType.SESSION_READY, handler=handler)

        assert len(emitter._background_tasks) == 0

        emitter.emit_nowait(event_type=EventType.SESSION_READY, data={"k": "v"})

        assert len(emitter._background_tasks) == 1

        await asyncio.sleep(delay=0.01)

        handler.assert_awaited_once()
        call_args = handler.call_args[0][0]
        assert call_args.data == {"k": "v"}

    @pytest.mark.asyncio
    async def test_emit_with_awaitable_non_coroutine(self, emitter: EventEmitter) -> None:
        future: asyncio.Future[None] = asyncio.Future()

        def handler(event: Event) -> asyncio.Future[None]:
            future.set_result(None)
            return future

        emitter.on(event_type=EventType.SESSION_READY, handler=handler)

        await emitter.emit(event_type=EventType.SESSION_READY)

        assert future.done()

    @pytest.mark.asyncio
    async def test_emit_with_no_handlers(self, emitter: EventEmitter, mock_logger: Any) -> None:
        await emitter.emit(event_type=EventType.SESSION_CLOSED)

        emit_log_found = any(
            call.args and "Emitting event" in call.args[0] for call in mock_logger.debug.call_args_list
        )
        assert not emit_log_found

    @pytest.mark.asyncio
    async def test_emit_with_sync_handler(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.Mock()
        emitter.on(event_type=EventType.SESSION_READY, handler=handler)

        await emitter.emit(event_type=EventType.SESSION_READY)

        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_history_and_filtering(self, emitter: EventEmitter) -> None:
        await emitter.emit(event_type=EventType.SESSION_READY)
        await emitter.emit(event_type=EventType.STREAM_OPENED)
        await emitter.emit(event_type=EventType.DATAGRAM_RECEIVED)

        history = emitter.get_event_history()
        assert len(history) == 3

        limited_history = emitter.get_event_history(limit=1)
        assert len(limited_history) == 1
        assert limited_history[0].type == EventType.DATAGRAM_RECEIVED

        filtered_history = emitter.get_event_history(event_type=EventType.STREAM_OPENED)
        assert len(filtered_history) == 1
        assert filtered_history[0].type == EventType.STREAM_OPENED

    @pytest.mark.asyncio
    async def test_event_queue_full_warning(self, mocker: MockerFixture, mock_logger: Any) -> None:
        emitter = EventEmitter(max_queue_size=1)
        emitter.pause()

        emitter.emit_nowait(event_type=EventType.SESSION_READY)
        emitter.emit_nowait(event_type=EventType.SESSION_READY)

        mock_logger.warning.assert_called_once()
        assert "Event queue full" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handler_raises_exception(
        self, emitter: EventEmitter, mocker: MockerFixture, mock_logger: Any
    ) -> None:
        handler1 = mocker.AsyncMock(side_effect=ValueError("Handler failed"))
        handler2 = mocker.AsyncMock()
        emitter.on(event_type=EventType.SESSION_READY, handler=handler1)
        emitter.on(event_type=EventType.SESSION_READY, handler=handler2)

        await emitter.emit(event_type=EventType.SESSION_READY)

        mock_logger.error.assert_called_once()
        handler1.assert_awaited_once()
        handler2.assert_awaited_once()

    def test_init_is_idempotent(self) -> None:
        emitter = EventEmitter(max_listeners=5)
        assert emitter._max_listeners == 5

        emitter.__init__(max_listeners=10)  # type: ignore[misc]

        assert emitter._max_listeners == 10

    @pytest.mark.asyncio
    async def test_max_listeners_warning(self, emitter: EventEmitter, mocker: MockerFixture, mock_logger: Any) -> None:
        emitter.set_max_listeners(max_listeners=1)
        emitter.on(event_type=EventType.SESSION_READY, handler=mocker.AsyncMock())

        emitter.on(event_type=EventType.SESSION_READY, handler=mocker.AsyncMock())

        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_off(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.Mock()
        emitter.on(event_type=EventType.CONNECTION_LOST, handler=handler)

        emitter.off(event_type=EventType.CONNECTION_LOST, handler=handler)
        await emitter.emit(event_type=EventType.CONNECTION_LOST)

        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_off_all_handlers_for_event(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler1 = mocker.AsyncMock()
        handler2 = mocker.AsyncMock()
        emitter.on(event_type=EventType.SESSION_READY, handler=handler1)
        emitter.on(event_type=EventType.SESSION_READY, handler=handler2)
        assert emitter.listener_count(event_type=EventType.SESSION_READY) == 2

        emitter.off(event_type=EventType.SESSION_READY, handler=None)

        assert emitter.listener_count(event_type=EventType.SESSION_READY) == 0

    @pytest.mark.asyncio
    async def test_off_any_no_args_removes_all(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.Mock()
        emitter.on_any(handler=handler)

        emitter.off_any()
        await emitter.emit(event_type=EventType.SESSION_READY)

        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_off_any_unknown_handler(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.Mock()
        emitter.on_any(handler=handler)
        unknown = mocker.Mock()

        emitter.off_any(handler=unknown)

        assert emitter.get_stats()["wildcard_handlers"] == 1

    @pytest.mark.asyncio
    async def test_off_removes_once_handler(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.Mock()
        emitter.once(event_type=EventType.CONNECTION_LOST, handler=handler)

        emitter.off(event_type=EventType.CONNECTION_LOST, handler=handler)
        await emitter.emit(event_type=EventType.CONNECTION_LOST)

        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_off_unknown_handler(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.Mock()
        emitter.on(event_type=EventType.SESSION_READY, handler=handler)
        unknown = mocker.Mock()

        emitter.off(event_type=EventType.SESSION_READY, handler=unknown)

        assert emitter.listener_count(event_type=EventType.SESSION_READY) == 1

    @pytest.mark.asyncio
    async def test_on_and_emit(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.AsyncMock()
        emitter.on(event_type=EventType.SESSION_READY, handler=handler)

        await emitter.emit(event_type=EventType.SESSION_READY, data={"test": 1})

        handler.assert_awaited_once()
        call_arg = handler.call_args[0][0]
        assert isinstance(call_arg, Event)
        assert call_arg.type == EventType.SESSION_READY
        assert call_arg.data == {"test": 1}

    @pytest.mark.asyncio
    async def test_on_any_and_off_any(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        wildcard_handler = mocker.AsyncMock()
        emitter.on_any(handler=wildcard_handler)

        await emitter.emit(event_type=EventType.CONNECTION_ESTABLISHED)
        emitter.off_any(handler=wildcard_handler)
        await emitter.emit(event_type=EventType.DATAGRAM_RECEIVED)

        wildcard_handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_any_duplicate_handler(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.Mock()
        emitter.on_any(handler=handler)
        emitter.on_any(handler=handler)

        await emitter.emit(event_type=EventType.SESSION_READY)

        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_once(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.AsyncMock()
        emitter.once(event_type=EventType.STREAM_OPENED, handler=handler)
        assert emitter.listener_count(event_type=EventType.STREAM_OPENED) == 1

        await emitter.emit(event_type=EventType.STREAM_OPENED)
        await emitter.emit(event_type=EventType.STREAM_OPENED)

        handler.assert_awaited_once()
        assert emitter.listener_count(event_type=EventType.STREAM_OPENED) == 0

    @pytest.mark.asyncio
    async def test_once_duplicate_handler(self, emitter: EventEmitter, mocker: MockerFixture, mock_logger: Any) -> None:
        handler = mocker.AsyncMock()
        emitter.once(event_type=EventType.SESSION_READY, handler=handler)

        emitter.once(event_type=EventType.SESSION_READY, handler=handler)

        assert emitter.listener_count(event_type=EventType.SESSION_READY) == 1
        assert len(emitter._once_handlers[EventType.SESSION_READY]) == 1

    @pytest.mark.asyncio
    async def test_pause_and_resume(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.AsyncMock()
        spy_create_task = mocker.spy(asyncio, "create_task")

        emitter.on(event_type=EventType.SESSION_READY, handler=handler)

        emitter.pause()
        await emitter.emit(event_type=EventType.SESSION_READY)
        handler.assert_not_awaited()

        task = emitter.resume()

        assert task is not None
        spy_create_task.assert_called()
        await task
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_registering_same_handler_twice_warning(
        self, emitter: EventEmitter, mocker: MockerFixture, mock_logger: Any
    ) -> None:
        handler = mocker.AsyncMock()

        emitter.on(event_type=EventType.SESSION_READY, handler=handler)
        emitter.on(event_type=EventType.SESSION_READY, handler=handler)

        assert emitter.listener_count(event_type=EventType.SESSION_READY) == 1
        mock_logger.warning.assert_called_once()

    def test_remove_all_listeners_defaults(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler = mocker.Mock()
        emitter.on(event_type=EventType.SESSION_READY, handler=handler)

        emitter.remove_all_listeners()

        assert emitter.listener_count(event_type=EventType.SESSION_READY) == 0

    def test_remove_all_listeners_for_specific_event(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        handler1 = mocker.Mock()
        handler2 = mocker.Mock()
        ev_a = EventType.SESSION_READY
        ev_b = EventType.STREAM_OPENED

        emitter.on(event_type=ev_a, handler=handler1)
        emitter.once(event_type=ev_a, handler=handler2)
        emitter.on(event_type=ev_b, handler=handler1)
        assert emitter.listener_count(event_type=ev_a) == 2
        assert emitter.listener_count(event_type=ev_b) == 1

        emitter.remove_all_listeners(event_type=ev_a)

        assert emitter.listener_count(event_type=ev_a) == 0
        assert emitter.listener_count(event_type=ev_b) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("queue_empty, task_running", [(True, False), (False, True)])
    async def test_resume_returns_none(
        self, emitter: EventEmitter, mocker: MockerFixture, queue_empty: bool, task_running: bool
    ) -> None:
        if not queue_empty:
            emitter._event_queue.append(Event(type=EventType.SESSION_READY))
        if task_running:
            emitter._processing_task = mocker.Mock(done=lambda: False)

        task = emitter.resume()

        assert task is None

    @pytest.mark.asyncio
    async def test_resume_task_cancelled(self, emitter: EventEmitter, mocker: MockerFixture) -> None:
        started = asyncio.Event()

        async def blocking_handler(event: Event) -> None:
            started.set()
            try:
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise

        emitter.on(event_type=EventType.SESSION_READY, handler=blocking_handler)

        emitter.pause()
        await emitter.emit(event_type=EventType.SESSION_READY)

        task = emitter.resume()
        assert task is not None

        await asyncio.wait_for(started.wait(), timeout=1.0)

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_wait_for_condition(self, emitter: EventEmitter) -> None:
        wait_task = asyncio.create_task(
            coro=emitter.wait_for(
                event_type=EventType.STREAM_DATA_RECEIVED, condition=lambda e: bool(e.data and e.data["stream_id"] == 3)
            )
        )
        await asyncio.sleep(delay=0.01)

        await emitter.emit(event_type=EventType.STREAM_DATA_RECEIVED, data={"stream_id": 1})
        assert not wait_task.done()
        await emitter.emit(event_type=EventType.STREAM_DATA_RECEIVED, data={"stream_id": 3})

        try:
            async with asyncio.timeout(delay=1):
                result = await wait_task
        except TimeoutError:
            wait_task.cancel()
            raise

        assert result.data
        assert result.data["stream_id"] == 3

    @pytest.mark.asyncio
    async def test_wait_for_condition_raises_exception(self, emitter: EventEmitter) -> None:
        class ConditionError(Exception):
            pass

        def faulty_condition(event: Event) -> bool:
            raise ConditionError("Condition failed")

        wait_task = asyncio.create_task(
            coro=emitter.wait_for(event_type=EventType.SESSION_READY, condition=faulty_condition)
        )
        await asyncio.sleep(delay=0.01)

        await emitter.emit(event_type=EventType.SESSION_READY)

        with pytest.raises(ConditionError):
            await wait_task

    @pytest.mark.asyncio
    async def test_wait_for_is_cancelled(self, emitter: EventEmitter) -> None:
        event_type = EventType.SESSION_READY
        wait_task = asyncio.create_task(coro=emitter.wait_for(event_type=event_type))
        await asyncio.sleep(delay=0.01)

        assert emitter.listener_count(event_type=event_type) == 1
        wait_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await wait_task

        assert emitter.listener_count(event_type=event_type) == 0

    @pytest.mark.asyncio
    async def test_wait_for_list_of_events(self, emitter: EventEmitter) -> None:
        wait_task = asyncio.create_task(
            coro=emitter.wait_for(event_type=[EventType.SESSION_READY, EventType.STREAM_OPENED])
        )
        await asyncio.sleep(0.01)

        await emitter.emit(event_type=EventType.STREAM_OPENED, data={"id": 1})

        try:
            async with asyncio.timeout(1):
                result = await wait_task
        except TimeoutError:
            wait_task.cancel()
            raise

        assert result.type == EventType.STREAM_OPENED

    @pytest.mark.asyncio
    async def test_wait_for_race_condition_error(self, emitter: EventEmitter) -> None:
        class RaceError(Exception):
            pass

        def faulty_condition(event: Event) -> bool:
            raise RaceError("Failed")

        emitter.pause()
        wait_task = asyncio.create_task(
            coro=emitter.wait_for(event_type=EventType.SESSION_READY, condition=faulty_condition)
        )
        await asyncio.sleep(delay=0.01)

        emitter.emit_nowait(event_type=EventType.SESSION_READY)
        emitter.emit_nowait(event_type=EventType.SESSION_READY)

        emitter.resume()
        try:
            async with asyncio.timeout(delay=1):
                with pytest.raises(RaceError):
                    await wait_task
        except TimeoutError:
            wait_task.cancel()
            raise

    @pytest.mark.asyncio
    async def test_wait_for_race_condition_success(self, emitter: EventEmitter) -> None:
        emitter.pause()
        wait_task = asyncio.create_task(coro=emitter.wait_for(event_type=EventType.SESSION_READY))
        await asyncio.sleep(delay=0.01)
        emitter.emit_nowait(event_type=EventType.SESSION_READY, data={"id": 1})
        emitter.emit_nowait(event_type=EventType.SESSION_READY, data={"id": 2})

        emitter.resume()
        try:
            async with asyncio.timeout(delay=1):
                result = await wait_task
        except TimeoutError:
            wait_task.cancel()
            raise

        assert result.data == {"id": 1}

    @pytest.mark.asyncio
    async def test_wait_for_success(self, emitter: EventEmitter) -> None:
        wait_task = asyncio.create_task(coro=emitter.wait_for(event_type=EventType.SESSION_READY))
        await asyncio.sleep(delay=0.01)

        await emitter.emit(event_type=EventType.SESSION_READY, data={"id": "abc"})
        try:
            async with asyncio.timeout(delay=1):
                result = await wait_task
        except TimeoutError:
            wait_task.cancel()
            raise

        assert result.data == {"id": "abc"}

    @pytest.mark.asyncio
    async def test_wait_for_timeout(self, emitter: EventEmitter) -> None:
        with pytest.raises(asyncio.TimeoutError):
            await emitter.wait_for(event_type=EventType.SESSION_READY, timeout=0.01)



================================================
FILE: tests/unit/test_exceptions.py
================================================
"""Unit tests for the pywebtransport.exceptions module."""

from typing import Any

import pytest

from pywebtransport import (
    ClientError,
    ConfigurationError,
    ConnectionError,
    DatagramError,
    ErrorCodes,
    ProtocolError,
    ServerError,
    SessionError,
    StreamError,
    TimeoutError,
    WebTransportError,
)
from pywebtransport.exceptions import (
    AuthenticationError,
    CertificateError,
    FlowControlError,
    HandshakeError,
    SerializationError,
)
from pywebtransport.types import SessionState


class TestSubclassExceptions:

    @pytest.mark.parametrize(
        "exc_class, kwargs, expected_category",
        [
            (AuthenticationError, {"auth_method": "token"}, "authentication"),
            (CertificateError, {"certificate_path": "/c.pem"}, "certificate"),
            (ClientError, {"target_url": "https://a.com"}, "client"),
            (ConfigurationError, {"config_key": "timeout"}, "configuration"),
            (ConnectionError, {"remote_address": ("1.1.1.1", 443)}, "connection"),
            (DatagramError, {"max_size": 1500}, "datagram"),
            (FlowControlError, {"stream_id": 1}, "flow_control"),
            (HandshakeError, {"handshake_stage": "alpn"}, "handshake"),
            (ProtocolError, {"frame_type": 0x41}, "protocol"),
            (SerializationError, {}, "serialization"),
            (ServerError, {"bind_address": ("0.0.0.0", 443)}, "server"),
            (SessionError, {"session_id": 100}, "session"),
            (StreamError, {"stream_id": 5}, "stream"),
            (TimeoutError, {"operation": "read"}, "timeout"),
        ],
    )
    def test_category_derivation(
        self, exc_class: type[WebTransportError], kwargs: dict[str, Any], expected_category: str
    ) -> None:
        exc = exc_class(message="Test", **kwargs)

        assert exc.category == expected_category

    def test_custom_attributes_in_repr(self) -> None:
        exc = ClientError(message="Invalid URL", target_url="https://example.com")

        r = repr(exc)

        assert "ClientError" in r
        assert "message='Invalid URL'" in r
        assert "target_url='https://example.com'" in r

    def test_custom_attributes_in_to_dict(self) -> None:
        exc = DatagramError(message="Too big", datagram_size=9000, max_size=1500)

        data = exc.to_dict()

        assert data["type"] == "DatagramError"
        assert data["datagram_size"] == 9000
        assert data["max_size"] == 1500

    def test_serialization_error_handles_exception_object(self) -> None:
        cause = ValueError("Parsing failed")
        exc = SerializationError(message="Bad data", original_exception=cause)

        data = exc.to_dict()

        assert data["original_exception"] == "Parsing failed"
        assert isinstance(exc.original_exception, ValueError)

    def test_session_error_with_enum(self) -> None:
        exc = SessionError(message="Closed", session_state=SessionState.CLOSED)

        data = exc.to_dict()

        assert data["session_state"] == SessionState.CLOSED
        assert "session_state=<SessionState.CLOSED: 'closed'>" in repr(exc)

    def test_stream_error_custom_str(self) -> None:
        exc_no_id = StreamError(message="No ID")
        exc_with_id = StreamError(message="With ID", stream_id=5)

        assert str(exc_no_id) == f"[{hex(exc_no_id.error_code)}] No ID"
        assert str(exc_with_id) == f"[{hex(exc_with_id.error_code)}] With ID (stream_id=5)"


class TestWebTransportErrorBase:

    def test_category_without_error_suffix(self) -> None:
        class CustomFault(WebTransportError):
            pass

        exc = CustomFault(message="Something failed")

        assert exc.category == "custom_fault"

    def test_dynamic_repr_generation(self) -> None:
        exc = WebTransportError(message="Base error", error_code=0x1)

        assert repr(exc) == "WebTransportError(message='Base error', error_code=0x1)"

    def test_dynamic_repr_with_details(self) -> None:
        details = {"info": "debug"}
        exc = WebTransportError(message="Msg", error_code=0x1, details=details)

        assert "details={'info': 'debug'}" in repr(exc)

    def test_error_properties_fatal(self) -> None:
        exc = WebTransportError(message="Fatal", error_code=ErrorCodes.INTERNAL_ERROR)

        assert exc.is_fatal is True
        assert exc.is_retriable is False

    def test_error_properties_retriable(self) -> None:
        exc = WebTransportError(message="Retry", error_code=ErrorCodes.APP_CONNECTION_TIMEOUT)

        assert exc.is_fatal is False
        assert exc.is_retriable is True

    def test_error_properties_unknown_code(self) -> None:
        exc = WebTransportError(message="Unknown", error_code=0x999999)

        assert exc.is_fatal is False
        assert exc.is_retriable is False

    def test_initialization_defaults(self) -> None:
        exc = WebTransportError(message="Base error")

        assert exc.message == "Base error"
        assert exc.error_code == ErrorCodes.INTERNAL_ERROR
        assert exc.details == {}
        assert str(exc) == "[0x1] Base error"
        assert exc.category == "web_transport"

    def test_to_dict_structure(self) -> None:
        exc = WebTransportError(message="Base error", error_code=ErrorCodes.INTERNAL_ERROR)

        data = exc.to_dict()

        assert data["type"] == "WebTransportError"
        assert data["category"] == "web_transport"
        assert data["message"] == "Base error"
        assert data["error_code"] == ErrorCodes.INTERNAL_ERROR
        assert data["is_fatal"] is True
        assert data["is_retriable"] is False
        assert data["details"] == {}



================================================
FILE: tests/unit/test_session.py
================================================
"""Unit tests for the pywebtransport.session module."""

import asyncio
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from pywebtransport import (
    ClientConfig,
    ConnectionError,
    SessionError,
    StreamError,
    TimeoutError,
    WebTransportReceiveStream,
    WebTransportSendStream,
    WebTransportSession,
    WebTransportStream,
)
from pywebtransport._adapter.client import WebTransportClientProtocol
from pywebtransport._protocol.events import (
    UserCloseSession,
    UserCreateStream,
    UserGetSessionDiagnostics,
    UserGrantDataCredit,
    UserGrantStreamsCredit,
    UserSendDatagram,
)
from pywebtransport.connection import WebTransportConnection
from pywebtransport.session import SessionDiagnostics
from pywebtransport.types import EventType, SessionState


class TestSessionDiagnostics:

    def test_init(self) -> None:
        diag = SessionDiagnostics(
            session_id=1,
            state=SessionState.CONNECTED,
            path="/",
            headers={"Host": "example.com"},
            created_at=100.0,
            local_max_data=1000,
            local_data_sent=50,
            local_data_consumed=40,
            peer_max_data=2000,
            peer_data_sent=100,
            local_max_streams_bidi=10,
            local_streams_bidi_opened=1,
            peer_max_streams_bidi=10,
            peer_streams_bidi_opened=2,
            peer_streams_bidi_closed=1,
            local_max_streams_uni=5,
            local_streams_uni_opened=0,
            peer_max_streams_uni=5,
            peer_streams_uni_opened=0,
            peer_streams_uni_closed=0,
            pending_bidi_stream_requests=[],
            pending_uni_stream_requests=[],
            datagrams_sent=5,
            datagram_bytes_sent=500,
            datagrams_received=3,
            datagram_bytes_received=300,
            active_streams=[],
            blocked_streams=[],
            close_code=None,
            close_reason=None,
            closed_at=None,
            ready_at=101.0,
        )

        assert diag.session_id == 1
        assert diag.state == SessionState.CONNECTED
        assert diag.local_data_consumed == 40
        assert diag.peer_streams_bidi_closed == 1


class TestWebTransportSession:

    @pytest.fixture
    def mock_protocol(self, mocker: MockerFixture) -> MagicMock:
        proto = mocker.Mock(spec=WebTransportClientProtocol)
        proto.create_request.side_effect = lambda: (1, asyncio.Future())
        return cast(MagicMock, proto)

    @pytest.fixture
    def mock_config(self, mocker: MockerFixture) -> MagicMock:
        conf = mocker.Mock(spec=ClientConfig)
        conf.max_event_queue_size = 100
        conf.max_event_listeners = 100
        conf.max_event_history_size = 100
        conf.stream_creation_timeout = 0.1
        return cast(MagicMock, conf)

    @pytest.fixture
    def mock_connection(self, mock_protocol: MagicMock, mock_config: MagicMock, mocker: MockerFixture) -> MagicMock:
        conn = mocker.Mock(spec=WebTransportConnection)
        conn.config = mock_config
        conn._protocol = mock_protocol
        conn.remote_address = ("127.0.0.1", 443)
        conn._stream_handles = {}
        return cast(MagicMock, conn)

    @pytest.fixture
    def session(self, mock_connection: MagicMock) -> WebTransportSession:
        return WebTransportSession(
            connection=mock_connection, session_id=1, path="/chat", headers={"User-Agent": "TestClient"}
        )

    def test_add_stream_handle_emits_event(self, session: WebTransportSession, mocker: MockerFixture) -> None:
        mock_stream = mocker.Mock(spec=WebTransportStream)
        mock_stream.stream_id = 1
        mock_emit = mocker.patch.object(session.events, "emit_nowait")

        session._add_stream_handle(stream=mock_stream, event_data={"a": 1})

        mock_emit.assert_called_once()
        call_args = mock_emit.call_args[1]
        assert call_args["event_type"] == EventType.STREAM_OPENED
        assert call_args["data"]["stream"] is mock_stream
        assert call_args["data"]["a"] == 1

    @pytest.mark.asyncio
    async def test_close_already_closed(self, session: WebTransportSession, mock_protocol: MagicMock) -> None:
        session._cached_state = SessionState.CLOSED

        await session.close()

        mock_protocol.create_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_connection_gone(self, session: WebTransportSession, mock_protocol: MagicMock) -> None:
        session._connection = lambda: None  # type: ignore[assignment]

        await session.close()

        mock_protocol.create_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_error_logging(
        self, session: WebTransportSession, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_exception(ConnectionError("Gone"))
        spy_logger = mocker.patch("pywebtransport.session.logger")

        await session.close()

        spy_logger.warning.assert_called_with("Error initiating session close for %s: %s", 1, mocker.ANY, exc_info=True)

    @pytest.mark.asyncio
    async def test_close_success(self, session: WebTransportSession, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_result(None)

        await session.close(error_code=100, reason="Done")

        mock_protocol.create_request.assert_called_once()
        mock_protocol.send_event.assert_called_once()
        event = mock_protocol.send_event.call_args[1]["event"]
        assert isinstance(event, UserCloseSession)
        assert event.session_id == 1
        assert event.error_code == 100
        assert event.reason == "Done"

    @pytest.mark.asyncio
    async def test_context_manager(self, session: WebTransportSession, mocker: MockerFixture) -> None:
        spy_close = mocker.patch.object(session, "close", new_callable=mocker.AsyncMock)

        async with session as s:
            assert s is session

        spy_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_stream_connection_gone(self, session: WebTransportSession) -> None:
        session._connection = lambda: None  # type: ignore[assignment]

        with pytest.raises(ConnectionError, match="Connection is gone"):
            await session.create_bidirectional_stream()

    @pytest.mark.asyncio
    async def test_create_stream_generic_error(self, session: WebTransportSession, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_exception(ValueError("Fail"))

        with pytest.raises(ValueError, match="Fail"):
            await session.create_bidirectional_stream()

    @pytest.mark.asyncio
    async def test_create_stream_handle_missing(
        self, session: WebTransportSession, mock_protocol: MagicMock, mock_connection: MagicMock
    ) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        mock_connection._stream_handles = {}
        fut.set_result(103)

        with pytest.raises(StreamError, match="Internal error creating stream handle"):
            await session.create_bidirectional_stream()

    @pytest.mark.asyncio
    async def test_create_stream_invalid_handle_type(
        self, session: WebTransportSession, mock_protocol: MagicMock, mock_connection: MagicMock, mocker: MockerFixture
    ) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        mock_recv = mocker.Mock(spec=WebTransportReceiveStream)
        mock_connection._stream_handles = {104: mock_recv}
        fut.set_result(104)

        with pytest.raises(StreamError, match="Invalid stream handle type"):
            await session.create_bidirectional_stream()

    @pytest.mark.parametrize(
        "method, wrong_type, error_msg",
        [
            ("create_bidirectional_stream", WebTransportSendStream, "Expected bidirectional stream"),
            ("create_unidirectional_stream", WebTransportStream, "Expected unidirectional send stream"),
        ],
    )
    @pytest.mark.asyncio
    async def test_create_stream_mismatch_type(
        self,
        session: WebTransportSession,
        mock_protocol: MagicMock,
        mock_connection: MagicMock,
        mocker: MockerFixture,
        method: str,
        wrong_type: type,
        error_msg: str,
    ) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        mock_wrong = mocker.Mock(spec=wrong_type)
        mock_connection._stream_handles = {105: mock_wrong}
        fut.set_result(105)
        create_method = getattr(session, method)

        with pytest.raises(StreamError, match=error_msg):
            await create_method()

    @pytest.mark.parametrize(
        "method, stream_type, is_uni, req_id",
        [
            ("create_bidirectional_stream", WebTransportStream, False, 101),
            ("create_unidirectional_stream", WebTransportSendStream, True, 102),
        ],
    )
    @pytest.mark.asyncio
    async def test_create_stream_success(
        self,
        session: WebTransportSession,
        mock_protocol: MagicMock,
        mock_connection: MagicMock,
        mocker: MockerFixture,
        method: str,
        stream_type: type,
        is_uni: bool,
        req_id: int,
    ) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        mock_stream = mocker.Mock(spec=stream_type)
        mock_connection._stream_handles = {req_id: mock_stream}
        fut.set_result(req_id)
        create_method = getattr(session, method)

        stream = await create_method()

        assert stream is mock_stream
        event = mock_protocol.send_event.call_args[1]["event"]
        assert isinstance(event, UserCreateStream)
        assert event.is_unidirectional is is_uni

    @pytest.mark.asyncio
    async def test_create_stream_timeout(
        self, session: WebTransportSession, mock_protocol: MagicMock, mocker: MockerFixture
    ) -> None:
        fut: asyncio.Future[int] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        mocker.patch("asyncio.timeout", side_effect=asyncio.TimeoutError)
        spy_logger = mocker.patch("pywebtransport.session.logger")

        with pytest.raises(TimeoutError, match="timed out creating stream"):
            await session.create_bidirectional_stream()

        spy_logger.warning.assert_called_with("Timeout creating stream on session %s", 1)

    @pytest.mark.asyncio
    async def test_diagnostics_connection_gone(self, session: WebTransportSession) -> None:
        session._connection = lambda: None  # type: ignore[assignment]

        with pytest.raises(ConnectionError, match="Connection is gone"):
            await session.diagnostics()

    @pytest.mark.asyncio
    async def test_diagnostics_protocol_error(self, session: WebTransportSession, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[dict[str, Any]] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_exception(ConnectionError("Closed"))

        with pytest.raises(SessionError, match="Connection is closed"):
            await session.diagnostics()

    @pytest.mark.asyncio
    async def test_diagnostics_success(self, session: WebTransportSession, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[dict[str, Any]] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        data = {
            "session_id": 1,
            "state": SessionState.CONNECTED,
            "path": "/",
            "headers": {},
            "created_at": 0.0,
            "local_max_data": 0,
            "local_data_sent": 0,
            "local_data_consumed": 0,
            "peer_max_data": 0,
            "peer_data_sent": 0,
            "local_max_streams_bidi": 0,
            "local_streams_bidi_opened": 0,
            "peer_max_streams_bidi": 0,
            "peer_streams_bidi_opened": 0,
            "peer_streams_bidi_closed": 0,
            "local_max_streams_uni": 0,
            "local_streams_uni_opened": 0,
            "peer_max_streams_uni": 0,
            "peer_streams_uni_opened": 0,
            "peer_streams_uni_closed": 0,
            "pending_bidi_stream_requests": [],
            "pending_uni_stream_requests": [],
            "datagrams_sent": 0,
            "datagram_bytes_sent": 0,
            "datagrams_received": 0,
            "datagram_bytes_received": 0,
            "active_streams": [],
            "blocked_streams": [],
            "close_code": None,
            "close_reason": None,
            "closed_at": None,
            "ready_at": None,
        }
        fut.set_result(data)

        diag = await session.diagnostics()

        assert isinstance(diag, SessionDiagnostics)
        assert diag.session_id == 1
        event = mock_protocol.send_event.call_args[1]["event"]
        assert isinstance(event, UserGetSessionDiagnostics)

    @pytest.mark.asyncio
    async def test_grant_data_credit(self, session: WebTransportSession, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_result(None)

        await session.grant_data_credit(max_data=1000)

        event = mock_protocol.send_event.call_args[1]["event"]
        assert isinstance(event, UserGrantDataCredit)
        assert event.max_data == 1000

    @pytest.mark.asyncio
    async def test_grant_streams_credit(self, session: WebTransportSession, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_result(None)

        await session.grant_streams_credit(max_streams=5, is_unidirectional=True)

        event = mock_protocol.send_event.call_args[1]["event"]
        assert isinstance(event, UserGrantStreamsCredit)
        assert event.max_streams == 5
        assert event.is_unidirectional is True

    def test_headers_copy(self, session: WebTransportSession) -> None:
        h = cast(dict[str, str], session.headers)
        h["New"] = "Value"
        internal_headers = cast(dict[str, str], session._headers)

        assert "New" not in internal_headers

    def test_init(self, session: WebTransportSession) -> None:
        assert session.session_id == 1
        assert session.path == "/chat"
        assert session.headers == {"User-Agent": "TestClient"}
        assert session.state == SessionState.CONNECTING
        assert session.is_closed is False

    @pytest.mark.asyncio
    async def test_methods_connection_gone(self, session: WebTransportSession) -> None:
        session._connection = lambda: None  # type: ignore[assignment]

        with pytest.raises(ConnectionError):
            await session.grant_data_credit(max_data=1)

        with pytest.raises(ConnectionError):
            await session.grant_streams_credit(max_streams=1, is_unidirectional=True)

        with pytest.raises(ConnectionError):
            await session.send_datagram(data=b"")

    def test_on_session_closed(self, session: WebTransportSession) -> None:
        session._on_session_closed(event=MagicMock())

        assert session.state == SessionState.CLOSED

    def test_on_session_ready(self, session: WebTransportSession) -> None:
        session._on_session_ready(event=MagicMock())

        assert session.state == SessionState.CONNECTED

    def test_remote_address(self, session: WebTransportSession, mock_connection: MagicMock) -> None:
        assert session.remote_address == ("127.0.0.1", 443)

    def test_remote_address_connection_gone(self, session: WebTransportSession) -> None:
        session._connection = lambda: None  # type: ignore[assignment]

        assert session.remote_address is None

    def test_remote_address_none(self, session: WebTransportSession, mock_connection: MagicMock) -> None:
        mock_connection.remote_address = None

        assert session.remote_address is None

    def test_repr(self, session: WebTransportSession) -> None:
        assert "id=1" in repr(session)
        assert "state=" in repr(session)

    @pytest.mark.asyncio
    async def test_send_datagram(self, session: WebTransportSession, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_result(None)

        await session.send_datagram(data=b"test")

        event = mock_protocol.send_event.call_args[1]["event"]
        assert isinstance(event, UserSendDatagram)
        assert event.data == b"test"



================================================
FILE: tests/unit/test_stream.py
================================================
"""Unit tests for the pywebtransport.stream.stream module."""

import asyncio
from typing import Any, cast
from unittest.mock import MagicMock, call

import pytest
from pytest_mock import MockerFixture

from pywebtransport import (
    ClientConfig,
    ConnectionError,
    ErrorCodes,
    StreamError,
    TimeoutError,
    WebTransportReceiveStream,
    WebTransportSendStream,
    WebTransportSession,
    WebTransportStream,
)
from pywebtransport._adapter.client import WebTransportClientProtocol
from pywebtransport._protocol.events import (
    UserGetStreamDiagnostics,
    UserResetStream,
    UserSendStreamData,
    UserStopStream,
    UserStreamRead,
)
from pywebtransport.connection import WebTransportConnection
from pywebtransport.stream import StreamDiagnostics, _BaseStream
from pywebtransport.types import StreamDirection, StreamState


class TestBaseStream:

    @pytest.fixture
    def mock_connection(self, mock_protocol: MagicMock, mocker: MockerFixture) -> MagicMock:
        conn = mocker.Mock(spec=WebTransportConnection)
        conn.config = mocker.Mock(spec=ClientConfig)
        conn.config.read_timeout = 0.1
        conn.config.write_timeout = 0.1
        conn.config.max_stream_read_buffer = 1024
        conn._protocol = mock_protocol
        return cast(MagicMock, conn)

    @pytest.fixture
    def mock_protocol(self, mocker: MockerFixture) -> MagicMock:
        proto = mocker.Mock(spec=WebTransportClientProtocol)
        proto.create_request.side_effect = lambda: (1, asyncio.Future())
        return cast(MagicMock, proto)

    @pytest.fixture
    def mock_session(self, mock_connection: MagicMock, mocker: MockerFixture) -> MagicMock:
        session = mocker.Mock(spec=WebTransportSession)
        session._connection = mocker.Mock(return_value=mock_connection)
        return cast(MagicMock, session)

    @pytest.fixture
    def stream(self, mock_session: MagicMock) -> _BaseStream:
        return _BaseStream(session=mock_session, stream_id=1)

    @pytest.mark.asyncio
    async def test_diagnostics_connection_closed_error(self, stream: _BaseStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[Any] = asyncio.Future()
        fut.set_exception(ConnectionError("Closed"))
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        with pytest.raises(StreamError, match="Connection is closed"):
            await stream.diagnostics()

    @pytest.mark.asyncio
    async def test_diagnostics_connection_gone(self, stream: _BaseStream, mock_session: MagicMock) -> None:
        mock_session._connection.return_value = None

        with pytest.raises(ConnectionError, match="Connection is gone"):
            await stream.diagnostics()

    @pytest.mark.asyncio
    async def test_diagnostics_success_deque(self, stream: _BaseStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[dict[str, Any]] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        data = {
            "stream_id": 1,
            "session_id": 100,
            "direction": StreamDirection.BIDIRECTIONAL,
            "state": StreamState.OPEN,
            "created_at": 0.0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "read_buffer_size": 0,
            "write_buffer_size": 4,
            "close_code": None,
            "close_reason": None,
            "closed_at": None,
        }
        fut.set_result(data)

        await stream.diagnostics()

        assert isinstance(mock_protocol.send_event.call_args.kwargs["event"], UserGetStreamDiagnostics)

    @pytest.mark.asyncio
    async def test_diagnostics_success_no_conversion_needed(
        self, stream: _BaseStream, mock_protocol: MagicMock
    ) -> None:
        fut: asyncio.Future[dict[str, Any]] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)

        data = {
            "stream_id": 1,
            "session_id": 100,
            "direction": StreamDirection.BIDIRECTIONAL,
            "state": StreamState.OPEN,
            "created_at": 0.0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "read_buffer_size": 0,
            "write_buffer_size": 0,
            "close_code": None,
            "close_reason": None,
            "closed_at": None,
        }
        fut.set_result(data)

        await stream.diagnostics()

    @pytest.mark.asyncio
    async def test_is_closed(self, stream: _BaseStream) -> None:
        stream._cached_state = StreamState.OPEN

        assert not stream.is_closed

        stream._cached_state = StreamState.CLOSED

        assert stream.is_closed

    @pytest.mark.asyncio
    async def test_on_closed_handler(self, stream: _BaseStream) -> None:
        stream.events.emit_nowait(event_type="stream_closed", data={})
        await asyncio.sleep(0)

        assert stream.state == StreamState.CLOSED

    @pytest.mark.asyncio
    async def test_repr(self, stream: _BaseStream) -> None:
        assert "_BaseStream" in repr(stream)
        assert "id=1" in repr(stream)

    @pytest.mark.asyncio
    async def test_session_property_gone(self, stream: _BaseStream) -> None:
        stream._session = lambda: None  # type: ignore

        with pytest.raises(ConnectionError, match="Session is gone"):
            _ = stream.session


class TestStreamDiagnostics:

    def test_init(self) -> None:
        diag = StreamDiagnostics(
            stream_id=1,
            session_id=100,
            direction=StreamDirection.BIDIRECTIONAL,
            state=StreamState.OPEN,
            created_at=100.0,
            bytes_sent=10,
            bytes_received=20,
            read_buffer_size=0,
            write_buffer_size=0,
            close_code=None,
            close_reason=None,
            closed_at=None,
        )

        assert diag.stream_id == 1
        assert diag.state == StreamState.OPEN


@pytest.mark.asyncio
class TestWebTransportReceiveStream(TestBaseStream):

    @pytest.fixture
    def stream(self, mock_session: MagicMock) -> WebTransportReceiveStream:
        return WebTransportReceiveStream(session=mock_session, stream_id=2)

    async def test_aiter(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "read", side_effect=[b"1", b"2", b""])

        res = [chunk async for chunk in stream]

        assert res == [b"1", b"2"]

    async def test_close(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        spy_stop = mocker.patch.object(stream, "stop_receiving", new_callable=mocker.AsyncMock)

        await stream.close()

        spy_stop.assert_awaited_once()

    async def test_context_manager(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        spy_stop = mocker.patch.object(stream, "stop_receiving", new_callable=mocker.AsyncMock)

        async with stream as s:
            assert s is stream

        spy_stop.assert_awaited_once()

    async def test_properties(self, stream: WebTransportReceiveStream) -> None:
        assert stream.direction == StreamDirection.RECEIVE_ONLY
        assert stream.can_read is True

        stream._cached_state = StreamState.RESET_RECEIVED

        assert stream.can_read is False

    async def test_read_all(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "read", side_effect=[b"a", b"b", b""])

        assert await stream.read_all() == b"ab"

    async def test_read_closed(self, stream: WebTransportReceiveStream) -> None:
        stream._cached_state = StreamState.CLOSED

        assert await stream.read() == b""

    async def test_read_eof(self, stream: WebTransportReceiveStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[bytes] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_result(b"")

        data = await stream.read()

        assert data == b""
        assert stream._read_eof is True

        mock_protocol.create_request.reset_mock()

        assert await stream.read() == b""
        mock_protocol.create_request.assert_not_called()

    async def test_read_generic_error(self, stream: WebTransportReceiveStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[bytes] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_exception(ValueError("Fail"))

        with pytest.raises(ValueError):
            await stream.read()

    async def test_read_no_connection(self, stream: WebTransportReceiveStream, mock_session: MagicMock) -> None:
        mock_session._connection.return_value = None

        with pytest.raises(ConnectionError):
            await stream.read()

    async def test_read_stream_error(self, stream: WebTransportReceiveStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[bytes] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_exception(StreamError("State", error_code=ErrorCodes.STREAM_STATE_ERROR))

        assert await stream.read() == b""

        mock_protocol.create_request.reset_mock()

        assert await stream.read() == b""
        mock_protocol.create_request.assert_not_called()

    async def test_read_stream_error_reraise(self, stream: WebTransportReceiveStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[bytes] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_exception(StreamError("Other", error_code=ErrorCodes.H3_FRAME_ERROR))

        with pytest.raises(StreamError, match="Other"):
            await stream.read()

    async def test_read_success(self, stream: WebTransportReceiveStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[bytes] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_result(b"data")

        data = await stream.read(max_bytes=10)

        assert data == b"data"
        event = mock_protocol.send_event.call_args.kwargs["event"]
        assert isinstance(event, UserStreamRead)
        assert event.max_bytes == 10

    async def test_readexactly(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "read", side_effect=[b"12", b"34"])

        assert await stream.readexactly(n=4) == b"1234"

    async def test_readexactly_incomplete(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "read", return_value=b"")

        with pytest.raises(asyncio.IncompleteReadError):
            await stream.readexactly(n=5)

    async def test_readexactly_no_connection(self, stream: WebTransportReceiveStream, mock_session: MagicMock) -> None:
        mock_session._connection.return_value = None

        with pytest.raises(ConnectionError, match="Connection is gone"):
            await stream.readexactly(n=1)

    async def test_readexactly_params(self, stream: WebTransportReceiveStream) -> None:
        with pytest.raises(ValueError):
            await stream.readexactly(n=-1)

        assert await stream.readexactly(n=0) == b""

    async def test_readexactly_timeout(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch("asyncio.timeout", side_effect=asyncio.TimeoutError)

        with pytest.raises(TimeoutError, match="readexactly timed out"):
            await stream.readexactly(n=1)

    async def test_readline(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "readuntil", return_value=b"line\n")

        assert await stream.readline() == b"line\n"

    async def test_readuntil_empty_separator(self, stream: WebTransportReceiveStream) -> None:
        with pytest.raises(ValueError):
            await stream.readuntil(separator=b"")

    async def test_readuntil_incomplete(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "read", return_value=b"")

        with pytest.raises(asyncio.IncompleteReadError):
            await stream.readuntil(separator=b"\n")

    async def test_readuntil_limit(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "read", side_effect=[b"1", b"2", b"3"])

        with pytest.raises(StreamError, match="Separator not found within limit"):
            await stream.readuntil(separator=b"\n", limit=2)

    async def test_readuntil_no_connection(self, stream: WebTransportReceiveStream, mock_session: MagicMock) -> None:
        mock_session._connection.return_value = None

        with pytest.raises(ConnectionError, match="Connection is gone"):
            await stream.readuntil(separator=b"\n")

    async def test_readuntil_params(self, stream: WebTransportReceiveStream) -> None:
        with pytest.raises(ValueError):
            await stream.readuntil(separator=b"")

    async def test_readuntil_success(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "read", side_effect=[b"a", b"b", b"\n"])

        assert await stream.readuntil(separator=b"\n") == b"ab\n"

    async def test_readuntil_timeout(self, stream: WebTransportReceiveStream, mocker: MockerFixture) -> None:
        mocker.patch("asyncio.timeout", side_effect=asyncio.TimeoutError)

        with pytest.raises(TimeoutError, match="readuntil timed out"):
            await stream.readuntil(separator=b"\n")

    async def test_repr(self, stream: WebTransportReceiveStream) -> None:  # type: ignore[override]
        assert "WebTransportReceiveStream" in repr(stream)
        assert "id=2" in repr(stream)

    async def test_stop_receiving(self, stream: WebTransportReceiveStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_result(None)

        await stream.stop_receiving(error_code=123)

        assert stream.state == StreamState.RESET_RECEIVED
        event = mock_protocol.send_event.call_args.kwargs["event"]
        assert isinstance(event, UserStopStream)
        assert event.error_code == 123

    async def test_stop_receiving_no_connection(
        self, stream: WebTransportReceiveStream, mock_session: MagicMock
    ) -> None:
        mock_session._connection.return_value = None

        await stream.stop_receiving()


@pytest.mark.asyncio
class TestWebTransportSendStream(TestBaseStream):

    @pytest.fixture
    def stream(self, mock_session: MagicMock) -> WebTransportSendStream:
        return WebTransportSendStream(session=mock_session, stream_id=3)

    async def test_close(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        spy_write = mocker.patch.object(stream, "write", new_callable=mocker.AsyncMock)

        await stream.close()

        spy_write.assert_awaited_once_with(data=b"", end_stream=True)
        assert stream.state == StreamState.HALF_CLOSED_LOCAL

    async def test_close_generic_error(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "write", side_effect=ValueError("Boom"))

        with pytest.raises(ValueError):
            await stream.close()

    async def test_close_stream_error_ignored(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "write", side_effect=StreamError("Expected"))

        await stream.close()

    async def test_close_with_error(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        spy_stop = mocker.patch.object(stream, "stop_sending", new_callable=mocker.AsyncMock)

        await stream.close(error_code=1)

        spy_stop.assert_awaited_once_with(error_code=1)

    async def test_context_manager_exit_cancelled(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        spy_close = mocker.patch.object(stream, "close", new_callable=mocker.AsyncMock)

        with pytest.raises(asyncio.CancelledError):
            async with stream:
                raise asyncio.CancelledError()

        spy_close.assert_awaited_once_with(error_code=ErrorCodes.APPLICATION_ERROR)

    async def test_context_manager_exit_error(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        spy_close = mocker.patch.object(stream, "close", new_callable=mocker.AsyncMock)

        class MyErr(Exception):
            error_code = 999

        with pytest.raises(MyErr):
            async with stream:
                raise MyErr()

        spy_close.assert_awaited_once_with(error_code=999)

    async def test_context_manager_exit_generic_error(
        self, stream: WebTransportSendStream, mocker: MockerFixture
    ) -> None:
        spy_close = mocker.patch.object(stream, "close", new_callable=mocker.AsyncMock)

        with pytest.raises(RuntimeError):
            async with stream:
                raise RuntimeError("Generic")

        spy_close.assert_awaited_once_with(error_code=ErrorCodes.APPLICATION_ERROR)

    async def test_context_manager_exit_success(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        spy_close = mocker.patch.object(stream, "close", new_callable=mocker.AsyncMock)

        async with stream:
            pass

        spy_close.assert_awaited_once_with(error_code=None)

    async def test_properties(self, stream: WebTransportSendStream) -> None:
        assert stream.direction == StreamDirection.SEND_ONLY
        assert stream.can_write is True

        stream._cached_state = StreamState.RESET_SENT

        assert stream.can_write is False

    async def test_repr(self, stream: WebTransportSendStream) -> None:  # type: ignore[override]
        assert "WebTransportSendStream" in repr(stream)

    async def test_stop_sending(self, stream: WebTransportSendStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_result(None)

        await stream.stop_sending(error_code=99)

        assert stream.state == StreamState.RESET_SENT
        event = mock_protocol.send_event.call_args.kwargs["event"]
        assert isinstance(event, UserResetStream)
        assert event.error_code == 99

    async def test_stop_sending_no_connection(self, stream: WebTransportSendStream, mock_session: MagicMock) -> None:
        mock_session._connection.return_value = None

        with pytest.raises(ConnectionError):
            await stream.stop_sending()

    async def test_write(self, stream: WebTransportSendStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_result(None)

        await stream.write(data=b"test", end_stream=True)

        event = mock_protocol.send_event.call_args.kwargs["event"]
        assert isinstance(event, UserSendStreamData)
        assert event.data == b"test"
        assert event.end_stream is True

    async def test_write_all(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        spy_write = mocker.patch.object(stream, "write", new_callable=mocker.AsyncMock)

        await stream.write_all(data=b"1234", chunk_size=2, end_stream=True)

        assert spy_write.await_count == 2
        spy_write.assert_has_awaits([call(data=b"12", end_stream=False), call(data=b"34", end_stream=True)])

    async def test_write_all_empty_end(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        spy_write = mocker.patch.object(stream, "write", new_callable=mocker.AsyncMock)

        await stream.write_all(data=b"", end_stream=True)

        spy_write.assert_awaited_once_with(data=b"", end_stream=True)

    async def test_write_all_error(self, stream: WebTransportSendStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream, "write", side_effect=StreamError("Fail", stream_id=3))

        with pytest.raises(StreamError):
            await stream.write_all(data=b"data")

    async def test_write_early_return(self, stream: WebTransportSendStream, mock_protocol: MagicMock) -> None:
        await stream.write(data=b"", end_stream=False)

        mock_protocol.create_request.assert_not_called()

    async def test_write_no_connection(self, stream: WebTransportSendStream, mock_session: MagicMock) -> None:
        mock_session._connection.return_value = None

        with pytest.raises(ConnectionError):
            await stream.write(data=b"a")

    async def test_write_timeout_propagation(self, stream: WebTransportSendStream, mock_protocol: MagicMock) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        mock_protocol.create_request.side_effect = None
        mock_protocol.create_request.return_value = (1, fut)
        fut.set_exception(TimeoutError("Timeout"))

        with pytest.raises(TimeoutError):
            await stream.write(data=b"payload")

    async def test_write_type_error(self, stream: WebTransportSendStream) -> None:
        with pytest.raises(TypeError):
            await stream.write(data=123)  # type: ignore[arg-type]


@pytest.mark.asyncio
class TestWebTransportStream(TestBaseStream):

    @pytest.fixture
    def stream(self, mock_session: MagicMock) -> WebTransportStream:
        return WebTransportStream(session=mock_session, stream_id=4)

    async def test_aiter(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._reader, "__anext__", side_effect=[b"1", StopAsyncIteration])

        chunks = [c async for c in stream]

        assert chunks == [b"1"]

    async def test_close(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        spy_send_close = mocker.patch.object(stream._writer, "close", new_callable=mocker.AsyncMock)
        spy_recv_stop = mocker.patch.object(stream._reader, "stop_receiving", new_callable=mocker.AsyncMock)

        await stream.close(error_code=10)

        spy_send_close.assert_awaited_once_with(error_code=10)
        spy_recv_stop.assert_awaited_once_with(error_code=10)

    async def test_close_no_args(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        spy_send_close = mocker.patch.object(stream._writer, "close", new_callable=mocker.AsyncMock)
        spy_recv_stop = mocker.patch.object(stream._reader, "stop_receiving", new_callable=mocker.AsyncMock)

        await stream.close()

        spy_send_close.assert_awaited_once_with(error_code=None)
        spy_recv_stop.assert_awaited_once_with(error_code=ErrorCodes.NO_ERROR)

    async def test_composition(self, stream: WebTransportStream) -> None:
        assert isinstance(stream._reader, WebTransportReceiveStream)
        assert isinstance(stream._writer, WebTransportSendStream)
        assert stream.direction == StreamDirection.BIDIRECTIONAL

    async def test_composition_properties(self, stream: WebTransportStream) -> None:
        assert stream.can_read is True
        assert stream.can_write is True

    async def test_context_manager(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        spy_close = mocker.patch.object(stream, "close", new_callable=mocker.AsyncMock)

        async with stream:
            pass

        spy_close.assert_awaited_once_with(error_code=None)

    @pytest.mark.parametrize("exception_type", [ValueError, asyncio.CancelledError])
    async def test_context_manager_error(
        self, stream: WebTransportStream, mocker: MockerFixture, exception_type: type[BaseException]
    ) -> None:
        spy_close = mocker.patch.object(stream, "close", new_callable=mocker.AsyncMock)

        with pytest.raises(exception_type):
            async with stream:
                raise exception_type()

        spy_close.assert_awaited_once_with(error_code=ErrorCodes.APPLICATION_ERROR)

    async def test_context_manager_exit_error_with_code(
        self, stream: WebTransportStream, mocker: MockerFixture
    ) -> None:
        spy_close = mocker.patch.object(stream, "close", new_callable=mocker.AsyncMock)

        class MyErr(Exception):
            error_code = 12345

        with pytest.raises(MyErr):
            async with stream:
                raise MyErr()

        spy_close.assert_awaited_once_with(error_code=12345)

    async def test_delegated_read(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._reader, "read", return_value=b"rd")

        assert await stream.read() == b"rd"

    async def test_delegated_read_all(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._reader, "read_all", return_value=b"all")

        assert await stream.read_all() == b"all"

    async def test_delegated_readexactly(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._reader, "readexactly", return_value=b"ex")

        assert await stream.readexactly(n=2) == b"ex"

    async def test_delegated_readline(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._reader, "readline", return_value=b"ln")

        assert await stream.readline() == b"ln"

    async def test_delegated_readuntil(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._reader, "readuntil", return_value=b"ut")

        assert await stream.readuntil(separator=b"t") == b"ut"

    async def test_delegated_stop_receiving(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._reader, "stop_receiving", new_callable=mocker.AsyncMock)

        await stream.stop_receiving(error_code=1)

        cast(MagicMock, stream._reader.stop_receiving).assert_awaited_once_with(error_code=1)

    async def test_delegated_stop_sending(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._writer, "stop_sending", new_callable=mocker.AsyncMock)

        await stream.stop_sending(error_code=2)

        cast(MagicMock, stream._writer.stop_sending).assert_awaited_once_with(error_code=2)

    async def test_delegated_write(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._writer, "write", new_callable=mocker.AsyncMock)

        await stream.write(data=b"wr")

        cast(MagicMock, stream._writer.write).assert_awaited_once_with(data=b"wr", end_stream=False)

    async def test_delegated_write_all(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        mocker.patch.object(stream._writer, "write_all", new_callable=mocker.AsyncMock)

        await stream.write_all(data=b"wall")

        cast(MagicMock, stream._writer.write_all).assert_awaited_once_with(
            data=b"wall", chunk_size=65536, end_stream=False
        )

    async def test_on_closed_propagates(self, stream: WebTransportStream, mocker: MockerFixture) -> None:
        stream._reader = mocker.Mock()
        stream._writer = mocker.Mock()
        stream.events.emit_nowait(event_type="stream_closed", data={})
        await asyncio.sleep(0)

        assert stream.state == StreamState.CLOSED
        cast(MagicMock, stream._reader)._on_closed.assert_called_once()
        cast(MagicMock, stream._writer)._on_closed.assert_called_once()

    async def test_repr(self, stream: WebTransportStream) -> None:  # type: ignore[override]
        assert "WebTransportStream" in repr(stream)



================================================
FILE: tests/unit/test_types.py
================================================
"""Unit tests for the pywebtransport.types module."""

import asyncio
from typing import Any

import pytest

from pywebtransport import Headers
from pywebtransport.types import (
    Buffer,
    ConnectionState,
    EventType,
    Serializer,
    SessionProtocol,
    SessionState,
    StreamDirection,
    StreamState,
    WebTransportProtocol,
)


class TestEnumerations:

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            (ConnectionState.IDLE, "idle"),
            (ConnectionState.CONNECTING, "connecting"),
            (ConnectionState.CONNECTED, "connected"),
            (ConnectionState.CLOSING, "closing"),
            (ConnectionState.DRAINING, "draining"),
            (ConnectionState.CLOSED, "closed"),
            (ConnectionState.FAILED, "failed"),
        ],
    )
    def test_connection_state(self, member: ConnectionState, expected_value: str) -> None:
        assert member.value == expected_value

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            (EventType.CAPSULE_RECEIVED, "capsule_received"),
            (EventType.CONNECTION_CLOSED, "connection_closed"),
            (EventType.CONNECTION_ESTABLISHED, "connection_established"),
            (EventType.CONNECTION_FAILED, "connection_failed"),
            (EventType.CONNECTION_LOST, "connection_lost"),
            (EventType.DATAGRAM_ERROR, "datagram_error"),
            (EventType.DATAGRAM_RECEIVED, "datagram_received"),
            (EventType.DATAGRAM_SENT, "datagram_sent"),
            (EventType.PROTOCOL_ERROR, "protocol_error"),
            (EventType.SESSION_CLOSED, "session_closed"),
            (EventType.SESSION_DATA_BLOCKED, "session_data_blocked"),
            (EventType.SESSION_DRAINING, "session_draining"),
            (EventType.SESSION_MAX_DATA_UPDATED, "session_max_data_updated"),
            (EventType.SESSION_MAX_STREAMS_BIDI_UPDATED, "session_max_streams_bidi_updated"),
            (EventType.SESSION_MAX_STREAMS_UNI_UPDATED, "session_max_streams_uni_updated"),
            (EventType.SESSION_READY, "session_ready"),
            (EventType.SESSION_REQUEST, "session_request"),
            (EventType.SESSION_STREAMS_BLOCKED, "session_streams_blocked"),
            (EventType.SETTINGS_RECEIVED, "settings_received"),
            (EventType.STREAM_CLOSED, "stream_closed"),
            (EventType.STREAM_DATA_RECEIVED, "stream_data_received"),
            (EventType.STREAM_ERROR, "stream_error"),
            (EventType.STREAM_OPENED, "stream_opened"),
            (EventType.TIMEOUT_ERROR, "timeout_error"),
        ],
    )
    def test_event_type(self, member: EventType, expected_value: str) -> None:
        assert member.value == expected_value

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            (SessionState.CONNECTING, "connecting"),
            (SessionState.CONNECTED, "connected"),
            (SessionState.CLOSING, "closing"),
            (SessionState.DRAINING, "draining"),
            (SessionState.CLOSED, "closed"),
        ],
    )
    def test_session_state(self, member: SessionState, expected_value: str) -> None:
        assert member.value == expected_value

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            (StreamDirection.BIDIRECTIONAL, "bidirectional"),
            (StreamDirection.SEND_ONLY, "send_only"),
            (StreamDirection.RECEIVE_ONLY, "receive_only"),
        ],
    )
    def test_stream_direction(self, member: StreamDirection, expected_value: str) -> None:
        assert member.value == expected_value

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            (StreamState.OPEN, "open"),
            (StreamState.HALF_CLOSED_LOCAL, "half_closed_local"),
            (StreamState.HALF_CLOSED_REMOTE, "half_closed_remote"),
            (StreamState.RESET_SENT, "reset_sent"),
            (StreamState.RESET_RECEIVED, "reset_received"),
            (StreamState.CLOSED, "closed"),
        ],
    )
    def test_stream_state(self, member: StreamState, expected_value: str) -> None:
        assert member.value == expected_value


class TestRuntimeCheckableProtocols:

    def test_serializer_protocol_conformance(self) -> None:
        class GoodSerializer:
            def serialize(self, *, obj: Any) -> bytes:
                return b"serialized"

            def deserialize(self, *, data: Buffer, obj_type: Any = None) -> Any:
                return "deserialized"

        assert isinstance(GoodSerializer(), Serializer)

    def test_serializer_protocol_non_conformance(self) -> None:
        class BadSerializer:
            def serialize(self, *, obj: Any) -> bytes:
                return b"serialized"

        assert not isinstance(BadSerializer(), Serializer)

    def test_session_protocol_conformance(self) -> None:
        class GoodSession:
            @property
            def headers(self) -> Headers:
                return {}

            @property
            def path(self) -> str:
                return "/"

            @property
            def remote_address(self) -> tuple[str, int] | None:
                return ("127.0.0.1", 443)

            @property
            def session_id(self) -> int:
                return 1

            @property
            def state(self) -> SessionState:
                return SessionState.CONNECTED

            async def close(self, *, error_code: int = 0, reason: str | None = None) -> None:
                pass

        assert isinstance(GoodSession(), SessionProtocol)

    def test_session_protocol_non_conformance(self) -> None:
        class BadSession:
            @property
            def headers(self) -> Headers:
                return {}

        assert not isinstance(BadSession(), SessionProtocol)

    def test_web_transport_protocol_conformance(self) -> None:
        class GoodTransport:
            def connection_lost(self, exc: Exception | None) -> None:
                pass

            def connection_made(self, transport: asyncio.BaseTransport) -> None:
                pass

            def datagram_received(self, data: Buffer, addr: tuple[str, int]) -> None:
                pass

            def error_received(self, exc: Exception) -> None:
                pass

        assert isinstance(GoodTransport(), WebTransportProtocol)

    def test_web_transport_protocol_non_conformance(self) -> None:
        class BadTransport:
            def connection_made(self, transport: Any) -> None:
                pass

        assert not isinstance(BadTransport(), WebTransportProtocol)



================================================
FILE: tests/unit/test_utils.py
================================================
"""Unit tests for the pywebtransport.utils module."""

import logging
from typing import Any, cast

import pytest
from pytest_mock import MockerFixture

from pywebtransport import Headers
from pywebtransport.utils import (
    ensure_buffer,
    format_duration,
    find_header,
    find_header_str,
    get_logger,
    get_timestamp,
    merge_headers,
)


class TestDataConversionAndFormatting:

    @pytest.mark.parametrize(
        "data, expected_type, expected_content",
        [
            ("hello", bytes, b"hello"),
            (b"world", bytes, b"world"),
            (bytearray(b"array"), bytearray, bytearray(b"array")),
            (memoryview(b"view"), memoryview, b"view"),
        ],
    )
    def test_ensure_buffer(self, data: Any, expected_type: type, expected_content: Any) -> None:
        result = ensure_buffer(data=data)

        assert isinstance(result, expected_type)
        if isinstance(result, memoryview):
            assert result.tobytes() == expected_content
        else:
            assert result == expected_content

    def test_ensure_buffer_invalid_type(self) -> None:
        with pytest.raises(TypeError):
            ensure_buffer(data=cast(Any, 123))

    @pytest.mark.parametrize(
        "seconds, expected",
        [
            (1e-7, "100ns"),
            (5e-5, "50.0µs"),
            (0.1234, "123.4ms"),
            (5.67, "5.7s"),
            (90.5, "1m30.5s"),
            (3723.1, "1h2m3.1s"),
        ],
    )
    def test_format_duration(self, seconds: float, expected: str) -> None:
        result = format_duration(seconds=seconds)

        assert result == expected


class TestHeaderUtils:

    def test_find_header_str_decoding(self) -> None:
        headers: Headers = {b"content-type": b"application/json"}

        result = find_header_str(headers=headers, key="content-type")

        assert result == "application/json"

    def test_find_header_str_default(self) -> None:
        headers: Headers = {"host": "example.com"}

        result = find_header_str(headers=headers, key="missing", default="default")

        assert result == "default"

    def test_find_header_str_existing_string(self) -> None:
        headers: Headers = {"user-agent": "test-client"}

        result = find_header_str(headers=headers, key="user-agent")

        assert result == "test-client"

    def test_find_header_str_invalid_utf8(self) -> None:
        headers: Headers = {b"key": b"\xff\xfe"}

        result = find_header_str(headers=headers, key="key", default="fallback")

        assert result == "fallback"

    def test_find_header_dual_mode_dict(self) -> None:
        headers: Headers = {b"content-length": b"123", "server": "test"}

        val_bytes = find_header(headers=headers, key="content-length")
        val_str = find_header(headers=headers, key="server")
        assert val_bytes == b"123"
        assert val_str == "test"

    def test_find_header_dual_mode_list(self) -> None:
        headers: Headers = [(b"content-length", b"123"), ("server", "test")]

        val_bytes = find_header(headers=headers, key="content-length")
        val_str = find_header(headers=headers, key="server")
        assert val_bytes == b"123"
        assert val_str == "test"

    def test_find_header_from_dict(self) -> None:
        headers: Headers = {"content-type": "application/json"}

        assert find_header(headers=headers, key="content-type") == "application/json"
        assert find_header(headers=headers, key="Unknown") is None
        assert find_header(headers=headers, key="Unknown", default="default") == "default"

    def test_find_header_from_list(self) -> None:
        headers: Headers = [("Content-Type", "application/json")]

        assert find_header(headers=headers, key="content-type") == "application/json"
        assert find_header(headers=headers, key="Unknown") is None

    def test_merge_headers_dict(self) -> None:
        base: Headers = {"a": "1"}
        update: Headers = {"b": "2"}

        result = merge_headers(base=base, update=update)

        assert result == {"a": "1", "b": "2"}

    def test_merge_headers_list(self) -> None:
        base: Headers = [("a", "1")]
        update: Headers = [("b", "2")]

        result = merge_headers(base=base, update=update)

        assert result == [("a", "1"), ("b", "2")]

    def test_merge_headers_mixed(self) -> None:
        base: Headers = {"a": "1"}
        update: Headers = [("b", "2")]

        result = merge_headers(base=base, update=update)

        assert result == [("a", "1"), ("b", "2")]

    def test_merge_headers_none(self) -> None:
        base: Headers = {"a": "1"}
        base_list: Headers = [("a", "1")]

        assert merge_headers(base=base, update=None) == {"a": "1"}
        assert merge_headers(base=base_list, update=None) == [("a", "1")]


class TestLoggingUtils:

    def test_get_logger(self) -> None:
        logger = get_logger(name="test")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test"


class TestTimestamp:

    def test_get_timestamp(self, mocker: MockerFixture) -> None:
        mocker.patch("time.perf_counter", return_value=12345.678)

        timestamp = get_timestamp()

        assert timestamp == 12345.678



================================================
FILE: tests/unit/_adapter/__init__.py
================================================
[Empty file]


================================================
FILE: tests/unit/_adapter/test_base.py
================================================
import asyncio
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from aioquic.quic.connection import QuicConnection
from pytest_mock import MockerFixture

from pywebtransport import ClientConfig, ErrorCodes
from pywebtransport._adapter.base import WebTransportCommonProtocol
from pywebtransport._protocol.events import (
    CloseQuicConnection,
    CreateH3Session,
    CreateQuicStream,
    Effect,
    EmitConnectionEvent,
    EmitSessionEvent,
    EmitStreamEvent,
    InternalCleanupEarlyEvents,
    InternalCleanupResources,
    InternalFailH3Session,
    InternalFailQuicStream,
    InternalReturnStreamData,
    LogH3Frame,
    NotifyRequestDone,
    NotifyRequestFailed,
    ProcessProtocolEvent,
    RescheduleQuicTimer,
    ResetQuicStream,
    SendH3Capsule,
    SendH3Datagram,
    SendH3Goaway,
    SendH3Headers,
    SendQuicData,
    SendQuicDatagram,
    StopQuicStream,
    TransportConnectionTerminated,
    TransportHandshakeCompleted,
    TransportQuicTimerFired,
    TriggerQuicTimer,
)
from pywebtransport.types import EventType


class TestWebTransportCommonProtocol:

    @pytest.fixture
    def mock_config(self) -> ClientConfig:
        config = ClientConfig()
        config.resource_cleanup_interval = 1.0
        config.pending_event_ttl = 1.0
        return config

    @pytest.fixture
    def mock_engine_class(self, mocker: MockerFixture) -> MagicMock:
        return cast(MagicMock, mocker.patch(target="pywebtransport._adapter.base.WebTransportEngine", autospec=True))

    @pytest.fixture
    def mock_loop(self, mocker: MockerFixture) -> MagicMock:
        loop = mocker.Mock(spec=asyncio.AbstractEventLoop)
        loop.time.return_value = 1000.0
        loop.create_future.side_effect = lambda: asyncio.Future(loop=loop)
        mocker.patch(target="asyncio.get_running_loop", return_value=loop)
        return cast(MagicMock, loop)

    @pytest.fixture
    def mock_quic(self, mocker: MockerFixture) -> MagicMock:
        quic = mocker.Mock(spec=QuicConnection)
        quic.host_cid = b"test_cid"
        quic._close_event = None
        quic._quic_logger = MagicMock()
        quic.configuration = mocker.Mock()
        quic.configuration.is_client = True
        quic.get_timer.return_value = 1100.0
        quic.datagrams_to_send.return_value = []
        quic.next_event.return_value = None
        return cast(MagicMock, quic)

    @pytest.fixture
    def protocol(
        self, mock_quic: MagicMock, mock_config: ClientConfig, mock_loop: MagicMock, mock_engine_class: MagicMock
    ) -> WebTransportCommonProtocol:
        return WebTransportCommonProtocol(quic=mock_quic, config=mock_config, is_client=True, loop=mock_loop)

    def test_allocate_stream_id(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic.get_next_available_stream_id.return_value = 4

        result = protocol._allocate_stream_id(is_unidirectional=False)

        assert result == 4
        mock_quic.send_stream_data.assert_called_once_with(stream_id=4, data=b"", end_stream=False)

    def test_close_connection_already_closing(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic._close_event = object()

        protocol.close_connection(error_code=ErrorCodes.NO_ERROR)

        mock_quic.close.assert_not_called()

    def test_close_connection_with_reason(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        protocol.close_connection(error_code=ErrorCodes.NO_ERROR, reason_phrase="graceful")

        mock_quic.close.assert_called_once_with(error_code=ErrorCodes.NO_ERROR, reason_phrase="graceful")

    def test_connection_lost_already_closing(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic._close_event = object()
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)

        protocol.connection_lost(exc=None)

        handle_event_mock.assert_not_called()

    def test_connection_lost_full(self, protocol: WebTransportCommonProtocol) -> None:
        timer_handle = MagicMock()
        protocol._timer_handle = timer_handle
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        protocol.connection_lost(exc=None)

        timer_handle.cancel.assert_called_once()
        event = handle_event_mock.call_args.kwargs["event"]
        assert isinstance(event, TransportConnectionTerminated)
        assert event.error_code == ErrorCodes.NO_ERROR

    def test_connection_lost_with_exception(self, protocol: WebTransportCommonProtocol) -> None:
        exc = RuntimeError("network error")
        protocol._setup_maintenance_timers()
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)

        protocol.connection_lost(exc=exc)

        event = handle_event_mock.call_args_list[0].kwargs["event"]
        assert isinstance(event, TransportConnectionTerminated)
        assert event.error_code == ErrorCodes.INTERNAL_ERROR
        assert protocol._resource_gc_timer is None

    def test_connection_made_setup_timers(self, protocol: WebTransportCommonProtocol, mock_loop: MagicMock) -> None:
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_transport.sendto = MagicMock()

        protocol.connection_made(transport=mock_transport)

        assert mock_loop.call_later.call_count == 2

    def test_execute_effects_loop(self, protocol: WebTransportCommonProtocol, mocker: MockerFixture) -> None:
        effect = SendQuicData(stream_id=0, data=b"data", end_stream=False)
        spy_process = mocker.spy(protocol, "_process_single_effect")

        protocol._execute_effects(effects=[effect])

        spy_process.assert_called_once_with(effect=effect)
        assert len(protocol._pending_effects) == 0

    def test_execute_effects_reentrancy(self, protocol: WebTransportCommonProtocol, mocker: MockerFixture) -> None:
        effect = SendQuicData(stream_id=0, data=b"data", end_stream=False)
        protocol._is_processing_effects = True
        spy_process = mocker.spy(protocol, "_process_single_effect")

        protocol._execute_effects(effects=[effect])

        assert len(protocol._pending_effects) == 1
        spy_process.assert_not_called()

    def test_get_next_available_stream_id(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic.get_next_available_stream_id.return_value = 8

        result = protocol.get_next_available_stream_id(is_unidirectional=True)

        assert result == 8
        mock_quic.get_next_available_stream_id.assert_called_once_with(is_unidirectional=True)

    def test_get_server_name(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic.configuration.server_name = "test.com"

        assert protocol.get_server_name() == "test.com"

    def test_handle_early_event_cleanup_timer_no_ttl(
        self, protocol: WebTransportCommonProtocol, mock_loop: MagicMock
    ) -> None:
        protocol._config.pending_event_ttl = 0
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        protocol._handle_early_event_cleanup_timer()

        assert mock_loop.call_later.call_count == 0

    def test_handle_early_event_cleanup_timer_with_ttl(
        self, protocol: WebTransportCommonProtocol, mock_loop: MagicMock
    ) -> None:
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        protocol._handle_early_event_cleanup_timer()

        event = handle_event_mock.call_args_list[0].kwargs["event"]
        assert isinstance(event, InternalCleanupEarlyEvents)
        mock_loop.call_later.assert_called_once()

    def test_handle_resource_gc_timer_no_interval(
        self, protocol: WebTransportCommonProtocol, mock_loop: MagicMock
    ) -> None:
        protocol._config.resource_cleanup_interval = 0
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        protocol._handle_resource_gc_timer()

        assert mock_loop.call_later.call_count == 0

    def test_handle_resource_gc_timer_with_interval(
        self, protocol: WebTransportCommonProtocol, mock_loop: MagicMock
    ) -> None:
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        protocol._handle_resource_gc_timer()

        event = handle_event_mock.call_args_list[0].kwargs["event"]
        assert isinstance(event, InternalCleanupResources)
        mock_loop.call_later.assert_called_once()

    def test_handle_timer_fired(self, protocol: WebTransportCommonProtocol) -> None:
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        protocol._handle_timer()

        event = handle_event_mock.call_args_list[0].kwargs["event"]
        assert isinstance(event, TransportQuicTimerFired)

    def test_handle_timer_now_with_events(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock, mocker: MockerFixture
    ) -> None:
        mock_event = MagicMock()
        mock_quic.next_event.side_effect = [mock_event, None]
        spy_received = mocker.spy(protocol, "quic_event_received")

        protocol.handle_timer_now()

        mock_quic.handle_timer.assert_called_once_with(now=1000.0)
        spy_received.assert_called_once_with(event=mock_event)

    def test_log_event_no_logger(self, protocol: WebTransportCommonProtocol) -> None:
        protocol._quic_logger = None

        protocol.log_event(category="cat", event="evt", data={})

        assert True

    def test_log_event_with_logger(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_logger = MagicMock()
        protocol._quic_logger = mock_logger

        protocol.log_event(category="cat", event="evt", data={"k": "v"})

        mock_logger.log_event.assert_called_once_with(category="cat", event="evt", data={"k": "v"})

    def test_on_handshake_completed_logic(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic.get_next_available_stream_id.side_effect = [1, 2, 3]
        mock_quic._remote_max_datagram_frame_size = 1500
        cast(MagicMock, protocol._engine.initialize_h3_transport).return_value = []
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)

        protocol._on_handshake_completed()

        assert protocol._quic_logger is not None
        assert isinstance(handle_event_mock.call_args_list[0].kwargs["event"], TransportHandshakeCompleted)
        cast(MagicMock, protocol._engine.initialize_h3_transport).assert_called_once_with(
            control_id=1, encoder_id=2, decoder_id=3
        )

    def test_on_handshake_completed_no_datagram_params(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock
    ) -> None:
        mock_quic.get_next_available_stream_id.side_effect = [1, 2, 3]
        del mock_quic._remote_max_datagram_frame_size
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)

        protocol._on_handshake_completed()

        assert handle_event_mock.call_count == 1

    def test_process_single_effect_close_connection(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock
    ) -> None:
        effect = CloseQuicConnection(error_code=ErrorCodes.INTERNAL_ERROR, reason="overload")

        protocol._process_single_effect(effect=effect)

        mock_quic.close.assert_called_once_with(error_code=ErrorCodes.INTERNAL_ERROR, reason_phrase="overload")

    def test_process_single_effect_create_h3_session(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock
    ) -> None:
        mock_quic.get_next_available_stream_id.return_value = 0
        effect = CreateH3Session(request_id=1, path="/test", headers={})

        protocol._process_single_effect(effect=effect)

        assert mock_quic.get_next_available_stream_id.called
        assert cast(MagicMock, protocol._engine.encode_session_request).called

    def test_process_single_effect_create_h3_session_fail(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock
    ) -> None:
        mock_quic.get_next_available_stream_id.side_effect = Exception("fail")
        effect = CreateH3Session(request_id=1, path="/test", headers={})
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)

        protocol._process_single_effect(effect=effect)

        event = handle_event_mock.call_args.kwargs["event"]
        assert isinstance(event, InternalFailH3Session)

    def test_process_single_effect_create_quic_stream(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock
    ) -> None:
        mock_quic.get_next_available_stream_id.return_value = 4
        effect = CreateQuicStream(request_id=1, session_id=0, is_unidirectional=False)

        protocol._process_single_effect(effect=effect)

        assert mock_quic.get_next_available_stream_id.called
        assert cast(MagicMock, protocol._engine.encode_stream_creation).called

    def test_process_single_effect_create_quic_stream_fail(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock
    ) -> None:
        mock_quic.get_next_available_stream_id.side_effect = Exception("fail")
        effect = CreateQuicStream(request_id=1, session_id=0, is_unidirectional=False)
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)

        protocol._process_single_effect(effect=effect)

        assert handle_event_mock.called

    def test_process_single_effect_emit_events(self, protocol: WebTransportCommonProtocol) -> None:
        cb = MagicMock()
        protocol.set_status_callback(callback=cb)
        effects: list[Effect] = [
            EmitConnectionEvent(event_type=cast(EventType, "conn"), data={}),
            EmitSessionEvent(event_type=cast(EventType, "sess"), session_id=0, data={}),
            EmitStreamEvent(event_type=cast(EventType, "stream"), stream_id=0, data={}),
            cast(Effect, InternalReturnStreamData(stream_id=0, data=b"data")),
        ]

        for effect in effects:
            protocol._process_single_effect(effect=effect)

        assert cb.call_count == 3
        assert cast(MagicMock, protocol._engine.handle_event).called

    def test_process_single_effect_emit_events_no_callback(self, protocol: WebTransportCommonProtocol) -> None:
        protocol.set_status_callback(callback=cast(Any, None))
        effects: list[Effect] = [
            EmitConnectionEvent(event_type=cast(EventType, "conn"), data={}),
            EmitSessionEvent(event_type=cast(EventType, "sess"), session_id=0, data={}),
            EmitStreamEvent(event_type=cast(EventType, "stream"), stream_id=0, data={}),
        ]

        for effect in effects:
            protocol._process_single_effect(effect=effect)

        assert True

    def test_process_single_effect_h3_actions(self, protocol: WebTransportCommonProtocol) -> None:
        effects: list[Effect] = [
            SendH3Headers(stream_id=0, status=200, end_stream=False),
            SendH3Headers(stream_id=0, status=200, end_stream=True),
            SendH3Capsule(stream_id=0, capsule_type=0, capsule_data=b"cap", end_stream=False),
            SendH3Datagram(stream_id=0, data=b"dg"),
            SendH3Goaway(),
        ]

        for effect in effects:
            protocol._process_single_effect(effect=effect)

        assert cast(MagicMock, protocol._engine.encode_headers).called
        assert cast(MagicMock, protocol._engine.encode_capsule).called
        assert cast(MagicMock, protocol._engine.encode_datagram).called
        assert cast(MagicMock, protocol._engine.encode_goaway).called

    def test_process_single_effect_log_and_protocol(self, protocol: WebTransportCommonProtocol) -> None:
        mock_evt = MagicMock()
        effects: list[Effect] = [
            LogH3Frame(category="h3", event="frame", data={}),
            ProcessProtocolEvent(event=mock_evt),
        ]
        cast(MagicMock, protocol._engine.handle_event).return_value = []

        for effect in effects:
            protocol._process_single_effect(effect=effect)

        assert len(protocol._pending_effects) == 0

    def test_process_single_effect_quic_io(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        effects: list[Effect] = [
            SendQuicData(stream_id=0, data=b"data", end_stream=False),
            SendQuicDatagram(data=b"dg"),
            ResetQuicStream(stream_id=0, error_code=0),
            StopQuicStream(stream_id=0, error_code=0),
        ]

        for effect in effects:
            protocol._process_single_effect(effect=effect)

        assert mock_quic.send_stream_data.called
        assert mock_quic.send_datagram_frame.called
        assert mock_quic.reset_stream.called
        assert mock_quic.stop_stream.called

    def test_process_single_effect_requests(self, protocol: WebTransportCommonProtocol) -> None:
        rid, fut = protocol.create_request()
        effects: list[Effect] = [
            NotifyRequestDone(request_id=rid, result="done"),
            NotifyRequestFailed(request_id=rid + 1, exception=RuntimeError()),
            cast(Effect, InternalFailH3Session(request_id=rid, exception=RuntimeError())),
            cast(
                Effect,
                InternalFailQuicStream(request_id=rid, session_id=0, is_unidirectional=False, exception=RuntimeError()),
            ),
        ]

        for effect in effects:
            protocol._process_single_effect(effect=effect)

        assert fut.result() == "done"

    def test_process_single_effect_timers(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock, mock_loop: MagicMock
    ) -> None:
        effects: list[Effect] = [RescheduleQuicTimer(), TriggerQuicTimer()]

        for effect in effects:
            protocol._process_single_effect(effect=effect)

        assert mock_loop.call_at.called
        assert cast(MagicMock, mock_quic.handle_timer).called

    def test_quic_event_received_handshake(self, protocol: WebTransportCommonProtocol, mocker: MockerFixture) -> None:
        spy_handshake = mocker.spy(protocol, "_on_handshake_completed")
        from aioquic.quic.events import HandshakeCompleted

        event = HandshakeCompleted(alpn_protocol="h3", early_data_accepted=False, session_resumed=False)

        protocol.quic_event_received(event=event)

        spy_handshake.assert_called_once()

    def test_quic_event_received_mapping(self, protocol: WebTransportCommonProtocol) -> None:
        from aioquic.quic.events import DatagramFrameReceived, StreamDataReceived, StreamReset

        events = [
            DatagramFrameReceived(data=b"dg"),
            StreamDataReceived(data=b"data", end_stream=False, stream_id=0),
            StreamReset(error_code=0, stream_id=0),
        ]
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        for event in events:
            protocol.quic_event_received(event=event)

        assert handle_event_mock.call_count == 3

    def test_quic_event_received_terminated(self, protocol: WebTransportCommonProtocol) -> None:
        from aioquic.quic.events import ConnectionTerminated

        event = ConnectionTerminated(error_code=0, frame_type=0x1D, reason_phrase="done")
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        protocol.quic_event_received(event=event)

        ev = handle_event_mock.call_args.kwargs["event"]
        assert isinstance(ev, TransportHandshakeCompleted) or isinstance(ev, TransportConnectionTerminated)

    def test_quic_event_received_unknown(self, protocol: WebTransportCommonProtocol) -> None:
        event = MagicMock()
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        protocol.quic_event_received(event=event)

        assert handle_event_mock.call_count == 0

    def test_reset_stream_closing(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic._close_event = object()

        protocol.reset_stream(stream_id=0, error_code=0)

        mock_quic.reset_stream.assert_not_called()

    def test_reset_stream_io_conflict(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic.reset_stream.side_effect = ValueError("state error")

        protocol.reset_stream(stream_id=0, error_code=0)

        assert mock_quic.reset_stream.called

    def test_schedule_timer_logic(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock, mock_loop: MagicMock
    ) -> None:
        old_handle = MagicMock()
        protocol._timer_handle = old_handle

        protocol.schedule_timer_now()

        old_handle.cancel.assert_called_once()
        assert mock_loop.call_at.called

    def test_schedule_timer_none(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock, mock_loop: MagicMock
    ) -> None:
        mock_quic.get_timer.return_value = None

        protocol.schedule_timer_now()

        assert mock_loop.call_at.call_count == 0

    def test_send_datagram_frame_closing(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic._close_event = object()

        protocol.send_datagram_frame(data=b"dg")

        mock_quic.send_datagram_frame.assert_not_called()

    def test_send_datagram_frame_list_input(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        protocol.send_datagram_frame(data=[b"a", b"b"])

        mock_quic.send_datagram_frame.assert_called_with(data=b"ab")

    def test_send_event(self, protocol: WebTransportCommonProtocol) -> None:
        evt = MagicMock()
        handle_event_mock = cast(MagicMock, protocol._engine.handle_event)
        handle_event_mock.return_value = []

        protocol.send_event(event=evt)

        handle_event_mock.assert_called_once()

    def test_send_stream_data_closing(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic._close_event = object()

        protocol.send_stream_data(stream_id=0, data=b"data")

        mock_quic.send_stream_data.assert_not_called()

    def test_send_stream_data_io_conflict(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic.send_stream_data.side_effect = AssertionError("io fail")

        protocol.send_stream_data(stream_id=0, data=b"data")

        assert mock_quic.send_stream_data.called

    def test_send_stream_data_with_fin_checks(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic._close_event = object()

        protocol.send_stream_data(stream_id=0, data=b"", end_stream=True)
        mock_quic.send_stream_data.assert_called_with(stream_id=0, data=b"", end_stream=True)

        protocol.send_stream_data(stream_id=0, data=b"fail", end_stream=False)
        assert mock_quic.send_stream_data.call_count == 1

    def test_setup_maintenance_timers_disabled(
        self, protocol: WebTransportCommonProtocol, mock_loop: MagicMock
    ) -> None:
        protocol._config.resource_cleanup_interval = 0
        protocol._config.pending_event_ttl = 0

        protocol._setup_maintenance_timers()

        assert mock_loop.call_later.call_count == 0

    def test_stop_stream_io_conflict(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic.stop_stream.side_effect = ValueError("io fail")

        protocol.stop_stream(stream_id=0, error_code=0)

        assert mock_quic.stop_stream.called

    def test_transmit_client_logic(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic.configuration.is_client = True
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_transport.sendto = MagicMock()
        protocol.connection_made(transport=mock_transport)
        mock_quic.datagrams_to_send.return_value = [(b"p1", None)]

        protocol.transmit()

        mock_transport.sendto.assert_called_with(b"p1")

    def test_transmit_generic_exception_handling(
        self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock
    ) -> None:
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_transport.sendto = MagicMock()
        protocol.connection_made(transport=mock_transport)
        mock_quic.datagrams_to_send.return_value = [(b"p1", ("1.1.1.1", 80))]
        mock_transport.sendto.side_effect = RuntimeError("generic failure")

        protocol.transmit()

        assert mock_transport.sendto.called

    def test_transmit_os_error_handling(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_transport.sendto = MagicMock()
        protocol.connection_made(transport=mock_transport)
        mock_quic.datagrams_to_send.return_value = [(b"p1", ("1.1.1.1", 80))]
        mock_transport.sendto.side_effect = OSError("network down")

        protocol.transmit()

        assert mock_transport.sendto.called

    def test_transmit_server_logic(self, protocol: WebTransportCommonProtocol, mock_quic: MagicMock) -> None:
        mock_quic.configuration.is_client = False
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_transport.sendto = MagicMock()
        protocol.connection_made(transport=mock_transport)
        mock_quic.datagrams_to_send.return_value = [(b"p1", ("1.1.1.1", 80))]

        protocol.transmit()

        mock_transport.sendto.assert_called_with(b"p1", ("1.1.1.1", 80))



================================================
FILE: tests/unit/_adapter/test_client.py
================================================
"""Unit tests for the pywebtransport._adapter.client module."""

import asyncio
import ssl
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from aioquic.quic.connection import QuicConnection
from pytest_mock import MockerFixture

from pywebtransport import ClientConfig
from pywebtransport._adapter.client import WebTransportClientProtocol, create_quic_endpoint


@pytest.mark.asyncio
class TestCreateQuicEndpoint:

    @pytest.fixture
    def client_config(self) -> ClientConfig:
        return ClientConfig()

    @pytest.fixture
    def mock_create_quic_config(self, mocker: MockerFixture) -> MagicMock:
        return cast(MagicMock, mocker.patch(target="pywebtransport._adapter.client.create_quic_configuration"))

    @pytest.fixture
    def mock_loop(self, mocker: MockerFixture) -> MagicMock:
        loop = mocker.Mock(spec=asyncio.AbstractEventLoop)
        loop.time.return_value = 1000.0

        async def side_effect(*args: Any, **kwargs: Any) -> tuple[MagicMock, WebTransportClientProtocol]:
            factory = kwargs.get("protocol_factory")
            if factory is None:
                raise ValueError("protocol_factory is required")

            protocol = factory()
            transport = mocker.Mock(spec=asyncio.DatagramTransport)
            transport.is_closing.return_value = False
            return transport, protocol

        loop.create_datagram_endpoint = mocker.AsyncMock(side_effect=side_effect)
        return cast(MagicMock, loop)

    @pytest.fixture
    def mock_quic_connection_class(self, mocker: MockerFixture) -> MagicMock:
        mock_class = mocker.patch(target="pywebtransport._adapter.client.QuicConnection", autospec=True)
        mock_instance = mock_class.return_value
        mock_instance.host_cid = b"test_cid"
        return mock_class

    async def test_create_quic_endpoint_no_certs(
        self,
        client_config: ClientConfig,
        mock_loop: MagicMock,
        mock_create_quic_config: MagicMock,
        mock_quic_connection_class: MagicMock,
    ) -> None:
        client_config.certfile = None
        client_config.keyfile = None

        await create_quic_endpoint(host="example.com", port=4433, config=client_config, loop=mock_loop)

        assert mock_create_quic_config.call_args.kwargs.get("certfile") is None
        assert mock_create_quic_config.call_args.kwargs.get("keyfile") is None

    async def test_create_quic_endpoint_partial_certs(
        self,
        client_config: ClientConfig,
        mock_loop: MagicMock,
        mock_create_quic_config: MagicMock,
        mock_quic_connection_class: MagicMock,
    ) -> None:
        client_config.certfile = "/path/to/cert.pem"
        client_config.keyfile = None

        await create_quic_endpoint(host="example.com", port=4433, config=client_config, loop=mock_loop)

        assert mock_create_quic_config.call_args.kwargs.get("certfile") == "/path/to/cert.pem"
        assert mock_create_quic_config.call_args.kwargs.get("keyfile") is None

    async def test_create_quic_endpoint_success(
        self,
        client_config: ClientConfig,
        mock_loop: MagicMock,
        mock_create_quic_config: MagicMock,
        mock_quic_connection_class: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        quic_config_instance = mock_create_quic_config.return_value
        quic_config_instance.server_name = "example.com"
        mock_quic_instance = mock_quic_connection_class.return_value

        def mock_init(self: Any, *args: Any, **kwargs: Any) -> None:
            self._quic = kwargs.get("quic")

        mocker.patch(
            target="pywebtransport._adapter.base.WebTransportCommonProtocol.__init__",
            side_effect=mock_init,
            autospec=True,
        )
        mocker.patch(target="pywebtransport._adapter.client.WebTransportClientProtocol.transmit")

        transport, protocol = await create_quic_endpoint(
            host="example.com", port=4433, config=client_config, loop=mock_loop
        )

        mock_create_quic_config.assert_called_once_with(
            alpn_protocols=client_config.alpn_protocols,
            ca_certs=None,
            certfile=None,
            congestion_control_algorithm=client_config.congestion_control_algorithm,
            idle_timeout=client_config.connection_idle_timeout,
            is_client=True,
            keyfile=None,
            max_datagram_size=client_config.max_datagram_size,
            server_name="example.com",
            verify_mode=client_config.verify_mode,
        )
        mock_loop.create_datagram_endpoint.assert_awaited_once()
        mock_quic_instance.connect.assert_called_once_with(addr=("example.com", 4433), now=1000.0)
        cast(MagicMock, protocol.transmit).assert_called_once()
        assert isinstance(transport, asyncio.DatagramTransport)
        assert isinstance(protocol, WebTransportClientProtocol)

    async def test_create_quic_endpoint_verify_mode(
        self,
        client_config: ClientConfig,
        mock_loop: MagicMock,
        mock_create_quic_config: MagicMock,
        mock_quic_connection_class: MagicMock,
    ) -> None:
        client_config.verify_mode = ssl.CERT_NONE

        await create_quic_endpoint(host="example.com", port=4433, config=client_config, loop=mock_loop)

        assert mock_create_quic_config.call_args.kwargs.get("verify_mode") == ssl.CERT_NONE

    async def test_create_quic_endpoint_with_ca_certs(
        self,
        client_config: ClientConfig,
        mock_loop: MagicMock,
        mock_create_quic_config: MagicMock,
        mock_quic_connection_class: MagicMock,
    ) -> None:
        client_config.ca_certs = "/path/to/ca.pem"

        await create_quic_endpoint(host="example.com", port=4433, config=client_config, loop=mock_loop)

        assert mock_create_quic_config.call_args.kwargs.get("ca_certs") == "/path/to/ca.pem"

    async def test_create_quic_endpoint_with_client_cert(
        self,
        client_config: ClientConfig,
        mock_loop: MagicMock,
        mock_create_quic_config: MagicMock,
        mock_quic_connection_class: MagicMock,
    ) -> None:
        client_config.certfile = "/path/to/cert.pem"
        client_config.keyfile = "/path/to/key.pem"

        await create_quic_endpoint(host="example.com", port=4433, config=client_config, loop=mock_loop)

        assert mock_create_quic_config.call_args.kwargs.get("certfile") == "/path/to/cert.pem"
        assert mock_create_quic_config.call_args.kwargs.get("keyfile") == "/path/to/key.pem"

    async def test_create_quic_endpoint_failure_cleanup(
        self,
        client_config: ClientConfig,
        mock_loop: MagicMock,
        mock_create_quic_config: MagicMock,
        mock_quic_connection_class: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        mock_protocol_cls = mocker.patch("pywebtransport._adapter.client.WebTransportClientProtocol", autospec=True)
        mock_protocol_instance = mock_protocol_cls.return_value

        async def side_effect(*args: Any, **kwargs: Any) -> None:
            factory = kwargs.get("protocol_factory")
            if factory is not None:
                factory()
            raise OSError("Simulated connection failure")

        mock_loop.create_datagram_endpoint = mocker.AsyncMock(side_effect=side_effect)

        with pytest.raises(OSError, match="Simulated connection failure"):
            await create_quic_endpoint(host="example.com", port=4433, config=client_config, loop=mock_loop)

        mock_protocol_instance.close_connection.assert_called_once_with(error_code=0, reason_phrase="Handshake failed")


class TestWebTransportClientProtocol:

    @pytest.fixture
    def client_config(self) -> ClientConfig:
        return ClientConfig()

    @pytest.fixture
    def mock_loop(self, mocker: MockerFixture) -> MagicMock:
        loop = mocker.Mock(spec=asyncio.AbstractEventLoop)
        mocker.patch(target="asyncio.get_running_loop", return_value=loop)
        return cast(MagicMock, loop)

    @pytest.fixture
    def mock_quic(self, mocker: MockerFixture) -> MagicMock:
        quic = mocker.Mock(spec=QuicConnection)
        quic.host_cid = b"test_cid"
        return cast(MagicMock, quic)

    @pytest.fixture
    def protocol(
        self, mock_quic: MagicMock, client_config: ClientConfig, mock_loop: MagicMock
    ) -> WebTransportClientProtocol:
        return WebTransportClientProtocol(
            quic=mock_quic, config=client_config, loop=mock_loop, max_event_queue_size=100
        )

    def test_protocol_initialization(self, protocol: WebTransportClientProtocol) -> None:
        assert isinstance(protocol, WebTransportClientProtocol)



================================================
FILE: tests/unit/_adapter/test_pending.py
================================================
"""Unit tests for the pywebtransport._adapter.pending module."""

import pytest

from pywebtransport._adapter.pending import PendingRequestManager


@pytest.mark.asyncio
class TestPendingRequestManager:

    @pytest.fixture
    def manager(self) -> PendingRequestManager:
        return PendingRequestManager()

    async def test_complete_request_already_done(self, manager: PendingRequestManager) -> None:
        request_id, future = manager.create_request()
        future.set_result("initial")

        manager.complete_request(request_id=request_id, result="new")

        assert future.result() == "initial"
        assert request_id not in manager._requests

    async def test_complete_request_nonexistent(self, manager: PendingRequestManager) -> None:
        manager.complete_request(request_id=999, result="data")

        assert True

    async def test_complete_request_success(self, manager: PendingRequestManager) -> None:
        request_id, future = manager.create_request()

        manager.complete_request(request_id=request_id, result="success_payload")

        assert future.done()
        assert future.result() == "success_payload"
        assert request_id not in manager._requests

    async def test_create_request_generates_unique_ids(self, manager: PendingRequestManager) -> None:
        id1, _ = manager.create_request()
        id2, _ = manager.create_request()

        assert id1 != id2
        assert len(manager._requests) == 2

    async def test_fail_all_with_mixed_states(self, manager: PendingRequestManager) -> None:
        id1, fut1 = manager.create_request()
        id2, fut2 = manager.create_request()
        fut1.set_result("already_done")
        exc = RuntimeError("connection lost")

        manager.fail_all(exception=exc)

        assert fut1.result() == "already_done"
        assert fut2.done()
        assert fut2.exception() == exc
        assert len(manager._requests) == 0

    async def test_fail_request_already_done(self, manager: PendingRequestManager) -> None:
        request_id, future = manager.create_request()
        future.set_result("done")
        exc = ValueError("error")

        manager.fail_request(request_id=request_id, exception=exc)

        assert future.result() == "done"
        assert request_id not in manager._requests

    async def test_fail_request_nonexistent(self, manager: PendingRequestManager) -> None:
        manager.fail_request(request_id=888, exception=RuntimeError())

        assert True

    async def test_fail_request_success(self, manager: PendingRequestManager) -> None:
        request_id, future = manager.create_request()
        exc = ValueError("invalid request")

        manager.fail_request(request_id=request_id, exception=exc)

        assert future.done()
        assert future.exception() == exc
        assert request_id not in manager._requests



================================================
FILE: tests/unit/_adapter/test_server.py
================================================
"""Unit tests for the pywebtransport._adapter.server module."""

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from aioquic.quic.connection import QuicConnection
from pytest_mock import MockerFixture

from pywebtransport import ServerConfig
from pywebtransport._adapter.server import WebTransportServerProtocol, create_server


@pytest.mark.asyncio
class TestCreateServer:

    @pytest.fixture
    def connection_creator(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_create_quic_config(self, mocker: MockerFixture) -> MagicMock:
        return cast(MagicMock, mocker.patch(target="pywebtransport._adapter.server.create_quic_configuration"))

    @pytest.fixture
    def mock_quic_serve(self, mocker: MockerFixture) -> MagicMock:
        return cast(
            MagicMock, mocker.patch(target="pywebtransport._adapter.server.quic_serve", new_callable=mocker.AsyncMock)
        )

    @pytest.fixture
    def server_config(self, valid_cert_paths: tuple[Path, Path]) -> ServerConfig:
        cert, key = valid_cert_paths
        return ServerConfig(certfile=str(cert), keyfile=str(key))

    @pytest.fixture
    def valid_cert_paths(self, tmp_path: Path) -> tuple[Path, Path]:
        cert = tmp_path / "ca.pem"
        key = tmp_path / "key.pem"
        cert.touch()
        key.touch()
        return cert, key

    async def test_create_server_protocol_factory(
        self,
        server_config: ServerConfig,
        connection_creator: MagicMock,
        mock_quic_serve: MagicMock,
        mock_create_quic_config: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(target="pywebtransport._adapter.base.WebTransportCommonProtocol.__init__", return_value=None)

        await create_server(host="127.0.0.1", port=4433, config=server_config, connection_creator=connection_creator)

        factory = mock_quic_serve.call_args.kwargs["create_protocol"]
        protocol = factory(quic=MagicMock(), stream_handler=MagicMock())

        assert isinstance(protocol, WebTransportServerProtocol)
        assert protocol._server_config == server_config
        assert protocol._connection_creator == connection_creator

    async def test_create_server_success(
        self,
        server_config: ServerConfig,
        connection_creator: MagicMock,
        mock_quic_serve: MagicMock,
        mock_create_quic_config: MagicMock,
    ) -> None:
        result = await create_server(
            host="127.0.0.1", port=4433, config=server_config, connection_creator=connection_creator
        )

        assert result == mock_quic_serve.return_value
        mock_create_quic_config.assert_called_once_with(
            alpn_protocols=server_config.alpn_protocols,
            ca_certs=None,
            certfile=server_config.certfile,
            congestion_control_algorithm=server_config.congestion_control_algorithm,
            idle_timeout=server_config.connection_idle_timeout,
            is_client=False,
            keyfile=server_config.keyfile,
            max_datagram_size=server_config.max_datagram_size,
            verify_mode=server_config.verify_mode,
        )
        mock_quic_serve.assert_awaited_once()

    async def test_create_server_with_ca_certs_success(
        self,
        server_config: ServerConfig,
        connection_creator: MagicMock,
        mock_create_quic_config: MagicMock,
        mock_quic_serve: MagicMock,
        tmp_path: Path,
    ) -> None:
        ca_cert = tmp_path / "ca.pem"
        ca_cert.touch()
        server_config.ca_certs = str(ca_cert)

        await create_server(host="127.0.0.1", port=4433, config=server_config, connection_creator=connection_creator)

        assert mock_create_quic_config.call_args.kwargs["ca_certs"] == str(ca_cert)


class TestWebTransportServerProtocol:

    @pytest.fixture
    def mock_connection_creator(self, mocker: MockerFixture) -> MagicMock:
        return cast(MagicMock, mocker.Mock())

    @pytest.fixture
    def mock_loop(self, mocker: MockerFixture) -> MagicMock:
        loop = mocker.Mock(spec=asyncio.AbstractEventLoop)
        mocker.patch(target="asyncio.get_running_loop", return_value=loop)
        return cast(MagicMock, loop)

    @pytest.fixture
    def mock_quic(self, mocker: MockerFixture) -> MagicMock:
        quic = mocker.Mock(spec=QuicConnection)
        quic.host_cid = b"test_cid"
        quic.configuration = mocker.Mock()
        quic.configuration.is_client = False
        return cast(MagicMock, quic)

    @pytest.fixture
    def valid_cert_paths(self, tmp_path: Path) -> tuple[Path, Path]:
        cert = tmp_path / "ca.pem"
        key = tmp_path / "key.pem"
        cert.touch()
        key.touch()
        return cert, key

    @pytest.fixture
    def server_config(self, valid_cert_paths: tuple[Path, Path]) -> ServerConfig:
        cert, key = valid_cert_paths
        return ServerConfig(certfile=str(cert), keyfile=str(key))

    @pytest.fixture
    def protocol(
        self,
        mock_quic: MagicMock,
        server_config: ServerConfig,
        mock_connection_creator: MagicMock,
        mock_loop: MagicMock,
    ) -> WebTransportServerProtocol:
        return WebTransportServerProtocol(
            quic=mock_quic, server_config=server_config, connection_creator=mock_connection_creator, loop=mock_loop
        )

    def test_connection_made(
        self, protocol: WebTransportServerProtocol, mock_connection_creator: MagicMock, mocker: MockerFixture
    ) -> None:
        mock_transport = mocker.Mock(spec=asyncio.DatagramTransport)
        mock_transport.is_closing.return_value = False

        protocol.connection_made(transport=mock_transport)

        assert protocol._transport == mock_transport
        mock_connection_creator.assert_called_once_with(protocol, mock_transport)



================================================
FILE: tests/unit/_adapter/test_utils.py
================================================
"""Unit tests for the pywebtransport._adapter.utils module."""

import pytest
from pytest_mock import MockerFixture

from pywebtransport._adapter.utils import create_quic_configuration


class TestCreateQuicConfiguration:

    def test_basic_initialization(self, mocker: MockerFixture) -> None:
        mock_config_cls = mocker.patch("pywebtransport._adapter.utils.QuicConfiguration", autospec=True)

        config = create_quic_configuration(
            alpn_protocols=["h3"],
            congestion_control_algorithm="reno",
            idle_timeout=60.0,
            is_client=True,
            max_datagram_size=1350,
        )

        assert config == mock_config_cls.return_value
        mock_config_cls.assert_called_once_with(
            alpn_protocols=["h3"],
            cafile=None,
            congestion_control_algorithm="reno",
            idle_timeout=60.0,
            is_client=True,
            max_datagram_frame_size=1350,
            server_name=None,
            verify_mode=None,
        )
        mock_config_cls.return_value.load_cert_chain.assert_not_called()

    @pytest.mark.parametrize("certfile, keyfile", [("cert.pem", None), (None, "key.pem"), (None, None)])
    def test_load_cert_chain_skipped(self, mocker: MockerFixture, certfile: str | None, keyfile: str | None) -> None:
        mock_config_cls = mocker.patch("pywebtransport._adapter.utils.QuicConfiguration", autospec=True)

        create_quic_configuration(
            alpn_protocols=["h3"],
            certfile=certfile,
            congestion_control_algorithm="reno",
            idle_timeout=60.0,
            is_client=True,
            keyfile=keyfile,
            max_datagram_size=1200,
        )

        mock_config_cls.return_value.load_cert_chain.assert_not_called()

    def test_optional_parameters_mapping(self, mocker: MockerFixture) -> None:
        mock_config_cls = mocker.patch("pywebtransport._adapter.utils.QuicConfiguration", autospec=True)
        mock_verify = mocker.Mock()

        create_quic_configuration(
            alpn_protocols=["h3"],
            ca_certs="root.pem",
            congestion_control_algorithm="reno",
            idle_timeout=60.0,
            is_client=True,
            max_datagram_size=1200,
            server_name="example.com",
            verify_mode=mock_verify,
        )

        call_kwargs = mock_config_cls.call_args.kwargs
        assert call_kwargs["cafile"] == "root.pem"
        assert call_kwargs["server_name"] == "example.com"
        assert call_kwargs["verify_mode"] is mock_verify

    def test_with_certificates(self, mocker: MockerFixture) -> None:
        mock_config_cls = mocker.patch("pywebtransport._adapter.utils.QuicConfiguration", autospec=True)

        create_quic_configuration(
            alpn_protocols=["h3"],
            certfile="cert.pem",
            congestion_control_algorithm="cubic",
            idle_timeout=30.0,
            is_client=False,
            keyfile="key.pem",
            max_datagram_size=1200,
        )

        mock_config_cls.return_value.load_cert_chain.assert_called_once_with(certfile="cert.pem", keyfile="key.pem")



================================================
FILE: tests/unit/_protocol/__init__.py
================================================
[Empty file]


================================================
FILE: tests/unit/_protocol/test_events.py
================================================
"""Unit tests for the pywebtransport._protocol.events module."""

from typing import Any

import pytest

from pywebtransport._protocol.events import (
    CapsuleReceived,
    CleanupH3Stream,
    CloseQuicConnection,
    ConnectionClose,
    ConnectStreamClosed,
    CreateH3Session,
    CreateQuicStream,
    DatagramReceived,
    Effect,
    EmitConnectionEvent,
    EmitSessionEvent,
    EmitStreamEvent,
    GoawayReceived,
    H3Event,
    HeadersReceived,
    InternalBindH3Session,
    InternalBindQuicStream,
    InternalCleanupEarlyEvents,
    InternalCleanupResources,
    InternalFailH3Session,
    InternalFailQuicStream,
    InternalReturnStreamData,
    LogH3Frame,
    NotifyRequestDone,
    NotifyRequestFailed,
    ProcessProtocolEvent,
    ProtocolEvent,
    RescheduleQuicTimer,
    ResetQuicStream,
    SendH3Capsule,
    SendH3Datagram,
    SendH3Goaway,
    SendH3Headers,
    SendQuicData,
    SendQuicDatagram,
    SettingsReceived,
    StopQuicStream,
    TransportConnectionTerminated,
    TransportDatagramFrameReceived,
    TransportHandshakeCompleted,
    TransportQuicParametersReceived,
    TransportQuicTimerFired,
    TransportStreamDataReceived,
    TransportStreamReset,
    TriggerQuicTimer,
    UserAcceptSession,
    UserCloseSession,
    UserConnectionGracefulClose,
    UserCreateSession,
    UserCreateStream,
    UserEvent,
    UserGetConnectionDiagnostics,
    UserGetSessionDiagnostics,
    UserGetStreamDiagnostics,
    UserGrantDataCredit,
    UserGrantStreamsCredit,
    UserRejectSession,
    UserResetStream,
    UserSendDatagram,
    UserSendStreamData,
    UserStopStream,
    UserStreamRead,
    WebTransportStreamDataReceived,
)


class TestEffects:

    @pytest.mark.parametrize(
        "effect_class, kwargs, expected_attrs",
        [
            (CleanupH3Stream, {"stream_id": 4}, {"stream_id": 4}),
            (
                CloseQuicConnection,
                {"error_code": 100, "reason": "test close"},
                {"error_code": 100, "reason": "test close"},
            ),
            (
                CreateH3Session,
                {"request_id": 1, "path": "/test", "headers": {b":path": b"/test"}},
                {"request_id": 1, "path": "/test", "headers": {b":path": b"/test"}},
            ),
            (
                CreateQuicStream,
                {"request_id": 1, "session_id": 1, "is_unidirectional": True},
                {"request_id": 1, "session_id": 1, "is_unidirectional": True},
            ),
            (
                EmitConnectionEvent,
                {"event_type": "connected", "data": {"key": "value"}},
                {"event_type": "connected", "data": {"key": "value"}},
            ),
            (
                EmitSessionEvent,
                {"session_id": 1, "event_type": "opened", "data": {}},
                {"session_id": 1, "event_type": "opened", "data": {}},
            ),
            (
                EmitStreamEvent,
                {"stream_id": 4, "event_type": "data_received", "data": {"len": 10}},
                {"stream_id": 4, "event_type": "data_received", "data": {"len": 10}},
            ),
            (
                LogH3Frame,
                {"category": "test", "event": "frame", "data": {"id": 1}},
                {"category": "test", "event": "frame", "data": {"id": 1}},
            ),
            (NotifyRequestDone, {"request_id": 1, "result": "success"}, {"request_id": 1, "result": "success"}),
            (
                NotifyRequestFailed,
                {"request_id": 1, "exception": ValueError("test")},
                {"request_id": 1, "exception": ValueError("test")},
            ),
            (ProcessProtocolEvent, {"event": TransportHandshakeCompleted()}, {"event": TransportHandshakeCompleted()}),
            (RescheduleQuicTimer, {}, {}),
            (ResetQuicStream, {"stream_id": 4, "error_code": 100}, {"stream_id": 4, "error_code": 100}),
            (
                SendH3Capsule,
                {"stream_id": 1, "capsule_type": 0x01, "capsule_data": b"cap", "end_stream": False},
                {"stream_id": 1, "capsule_type": 0x01, "capsule_data": b"cap", "end_stream": False},
            ),
            (SendH3Datagram, {"stream_id": 1, "data": b"dgram"}, {"stream_id": 1, "data": b"dgram"}),
            (SendH3Goaway, {}, {}),
            (
                SendH3Headers,
                {"stream_id": 1, "status": 404, "end_stream": True},
                {"stream_id": 1, "status": 404, "end_stream": True},
            ),
            (
                SendQuicData,
                {"stream_id": 4, "data": b"data", "end_stream": False},
                {"stream_id": 4, "data": b"data", "end_stream": False},
            ),
            (SendQuicDatagram, {"data": b"dgram"}, {"data": b"dgram"}),
            (StopQuicStream, {"stream_id": 4, "error_code": 100}, {"stream_id": 4, "error_code": 100}),
            (TriggerQuicTimer, {}, {}),
        ],
    )
    def test_instantiation(
        self, effect_class: type[Effect], kwargs: dict[str, Any], expected_attrs: dict[str, Any]
    ) -> None:
        if "exception" in kwargs and isinstance(kwargs["exception"], ValueError):
            effect = effect_class(**kwargs)
            assert isinstance(effect, Effect)
            assert getattr(effect, "request_id") == expected_attrs["request_id"]
            assert isinstance(getattr(effect, "exception"), ValueError)
            return

        if "event" in kwargs and isinstance(kwargs["event"], ProtocolEvent):
            effect = effect_class(**kwargs)
            assert isinstance(effect, Effect)
            assert isinstance(getattr(effect, "event"), ProtocolEvent)
            return

        effect = effect_class(**kwargs)

        assert isinstance(effect, Effect)
        for attr, expected_value in expected_attrs.items():
            assert getattr(effect, attr) == expected_value


class TestH3Events:

    @pytest.mark.parametrize(
        "event_class, kwargs, expected_attrs",
        [
            (
                CapsuleReceived,
                {"capsule_data": b"capsule", "capsule_type": 0x01, "stream_id": 1},
                {"capsule_data": b"capsule", "capsule_type": 0x01, "stream_id": 1},
            ),
            (ConnectStreamClosed, {"stream_id": 1}, {"stream_id": 1}),
            (DatagramReceived, {"data": b"datagram", "stream_id": 1}, {"data": b"datagram", "stream_id": 1}),
            (GoawayReceived, {}, {}),
            (
                HeadersReceived,
                {"headers": {b":status": b"200"}, "stream_id": 1, "stream_ended": False},
                {"headers": {b":status": b"200"}, "stream_id": 1, "stream_ended": False},
            ),
            (SettingsReceived, {"settings": {0x01: 0x01}}, {"settings": {0x01: 0x01}}),
            (
                WebTransportStreamDataReceived,
                {"data": b"data", "session_id": 1, "stream_id": 4, "stream_ended": True},
                {"data": b"data", "session_id": 1, "stream_id": 4, "stream_ended": True},
            ),
        ],
    )
    def test_instantiation(
        self, event_class: type[H3Event], kwargs: dict[str, Any], expected_attrs: dict[str, Any]
    ) -> None:
        event = event_class(**kwargs)

        assert isinstance(event, H3Event)
        for attr, expected_value in expected_attrs.items():
            assert getattr(event, attr) == expected_value


class TestInternalProtocolEvents:

    @pytest.mark.parametrize(
        "event_class, kwargs, expected_attrs",
        [
            (InternalBindH3Session, {"request_id": 1, "stream_id": 2}, {"request_id": 1, "stream_id": 2}),
            (
                InternalBindQuicStream,
                {"request_id": 1, "stream_id": 1, "session_id": 1, "is_unidirectional": True},
                {"request_id": 1, "stream_id": 1, "session_id": 1, "is_unidirectional": True},
            ),
            (InternalCleanupEarlyEvents, {}, {}),
            (InternalCleanupResources, {}, {}),
            (
                InternalFailH3Session,
                {"request_id": 1, "exception": ValueError("test")},
                {"request_id": 1, "exception": ValueError("test")},
            ),
            (
                InternalFailQuicStream,
                {"request_id": 1, "session_id": 1, "is_unidirectional": True, "exception": ValueError("test")},
                {"request_id": 1, "session_id": 1, "is_unidirectional": True, "exception": ValueError("test")},
            ),
            (InternalReturnStreamData, {"stream_id": 1, "data": b"returned"}, {"stream_id": 1, "data": b"returned"}),
            (
                TransportConnectionTerminated,
                {"error_code": 100, "reason_phrase": "test reason"},
                {"error_code": 100, "reason_phrase": "test reason"},
            ),
            (TransportDatagramFrameReceived, {"data": b"datagram_data"}, {"data": b"datagram_data"}),
            (TransportHandshakeCompleted, {}, {}),
            (
                TransportQuicParametersReceived,
                {"remote_max_datagram_frame_size": 1500},
                {"remote_max_datagram_frame_size": 1500},
            ),
            (TransportQuicTimerFired, {}, {}),
            (
                TransportStreamDataReceived,
                {"data": b"stream_data", "end_stream": True, "stream_id": 4},
                {"data": b"stream_data", "end_stream": True, "stream_id": 4},
            ),
            (TransportStreamReset, {"error_code": 101, "stream_id": 4}, {"error_code": 101, "stream_id": 4}),
        ],
    )
    def test_instantiation(
        self, event_class: type[ProtocolEvent], kwargs: dict[str, Any], expected_attrs: dict[str, Any]
    ) -> None:
        if "exception" in kwargs and isinstance(kwargs["exception"], ValueError):
            event = event_class(**kwargs)
            assert isinstance(event, ProtocolEvent)
            assert getattr(event, "request_id") == expected_attrs["request_id"]
            assert isinstance(getattr(event, "exception"), ValueError)
            return

        event = event_class(**kwargs)

        assert isinstance(event, ProtocolEvent)
        for attr, expected_value in expected_attrs.items():
            assert getattr(event, attr) == expected_value


class TestUserEvents:

    @pytest.mark.parametrize(
        "event_class, kwargs, expected_attrs",
        [
            (
                ConnectionClose,
                {"request_id": 1, "error_code": 100, "reason": "closing"},
                {"request_id": 1, "error_code": 100, "reason": "closing"},
            ),
            (UserAcceptSession, {"request_id": 1, "session_id": 1}, {"request_id": 1, "session_id": 1}),
            (
                UserCloseSession,
                {"request_id": 1, "session_id": 1, "error_code": 100, "reason": "test"},
                {"request_id": 1, "session_id": 1, "error_code": 100, "reason": "test"},
            ),
            (UserConnectionGracefulClose, {"request_id": 1}, {"request_id": 1}),
            (
                UserCreateSession,
                {"request_id": 1, "path": "/test", "headers": {b":path": b"/test"}},
                {"request_id": 1, "path": "/test", "headers": {b":path": b"/test"}},
            ),
            (
                UserCreateStream,
                {"request_id": 1, "session_id": 1, "is_unidirectional": True},
                {"request_id": 1, "session_id": 1, "is_unidirectional": True},
            ),
            (UserGetConnectionDiagnostics, {"request_id": 1}, {"request_id": 1}),
            (UserGetSessionDiagnostics, {"request_id": 1, "session_id": 1}, {"request_id": 1, "session_id": 1}),
            (UserGetStreamDiagnostics, {"request_id": 1, "stream_id": 4}, {"request_id": 1, "stream_id": 4}),
            (
                UserGrantDataCredit,
                {"request_id": 1, "session_id": 1, "max_data": 1024},
                {"request_id": 1, "session_id": 1, "max_data": 1024},
            ),
            (
                UserGrantStreamsCredit,
                {"request_id": 1, "session_id": 1, "max_streams": 10, "is_unidirectional": False},
                {"request_id": 1, "session_id": 1, "max_streams": 10, "is_unidirectional": False},
            ),
            (
                UserRejectSession,
                {"request_id": 1, "session_id": 1, "status_code": 404},
                {"request_id": 1, "session_id": 1, "status_code": 404},
            ),
            (
                UserResetStream,
                {"request_id": 1, "stream_id": 4, "error_code": 100},
                {"request_id": 1, "stream_id": 4, "error_code": 100},
            ),
            (
                UserSendDatagram,
                {"request_id": 1, "session_id": 1, "data": b"datagram"},
                {"request_id": 1, "session_id": 1, "data": b"datagram"},
            ),
            (
                UserSendStreamData,
                {"request_id": 1, "stream_id": 4, "data": b"data", "end_stream": True},
                {"request_id": 1, "stream_id": 4, "data": b"data", "end_stream": True},
            ),
            (
                UserStopStream,
                {"request_id": 1, "stream_id": 4, "error_code": 100},
                {"request_id": 1, "stream_id": 4, "error_code": 100},
            ),
            (
                UserStreamRead,
                {"request_id": 1, "stream_id": 4, "max_bytes": 1024},
                {"request_id": 1, "stream_id": 4, "max_bytes": 1024},
            ),
        ],
    )
    def test_instantiation(
        self, event_class: type[UserEvent[Any]], kwargs: dict[str, Any], expected_attrs: dict[str, Any]
    ) -> None:
        event = event_class(**kwargs)

        assert isinstance(event, UserEvent)
        for attr, expected_value in expected_attrs.items():
            assert getattr(event, attr) == expected_value



================================================
FILE: tests/unit/client/__init__.py
================================================
[Empty file]


================================================
FILE: tests/unit/client/test_client.py
================================================
"""Unit tests for the pywebtransport.client.client module."""

import asyncio
from typing import Any

import pytest
from pytest_mock import MockerFixture

from pywebtransport import (
    ClientConfig,
    ClientError,
    ConnectionError,
    TimeoutError,
    WebTransportClient,
    WebTransportSession,
)
from pywebtransport.client import ClientDiagnostics, ClientStats
from pywebtransport.connection import WebTransportConnection
from pywebtransport.manager import ConnectionManager
from pywebtransport.types import ConnectionState, EventType


class TestClientDiagnostics:

    @pytest.mark.parametrize(
        "stats_data, expected_issue_part",
        [
            ({}, None),
            ({"connections_attempted": 20, "success_rate": 0.5}, "Low connection success rate"),
            ({"avg_connect_time": 6.5}, "Slow average connection time"),
        ],
    )
    def test_issues_property(
        self, mocker: MockerFixture, stats_data: dict[str, Any], expected_issue_part: str | None
    ) -> None:
        mock_stats = mocker.create_autospec(ClientStats, instance=True)
        mock_stats.to_dict.return_value = stats_data
        diagnostics = ClientDiagnostics(stats=mock_stats, connection_states={})

        issues = diagnostics.issues

        if expected_issue_part:
            assert any(expected_issue_part in issue for issue in issues)
        else:
            assert not issues


class TestClientStats:

    def test_avg_connect_time(self) -> None:
        stats = ClientStats(created_at=0)

        assert stats.avg_connect_time == 0.0

        stats.connections_successful = 2
        stats.total_connect_time = 5.0

        assert stats.avg_connect_time == 2.5

    def test_initialization(self) -> None:
        stats = ClientStats(created_at=1000.0)

        assert stats.created_at == 1000.0
        assert stats.connections_attempted == 0
        assert stats.connections_successful == 0
        assert stats.connections_failed == 0
        assert stats.total_connect_time == 0.0
        assert stats.min_connect_time == float("inf")
        assert stats.max_connect_time == 0.0

    def test_success_rate(self) -> None:
        stats = ClientStats(created_at=0)

        assert stats.success_rate == 1.0

        stats.connections_attempted = 10
        stats.connections_successful = 8

        assert stats.success_rate == 0.8

        stats.connections_attempted = 10
        stats.connections_successful = 0

        assert stats.success_rate == 0.0

    def test_to_dict(self, mocker: MockerFixture) -> None:
        mocker.patch("pywebtransport.client.client.get_timestamp", return_value=1010.0)
        stats = ClientStats(created_at=1000.0)
        stats.min_connect_time = 1.2

        stats_dict = stats.to_dict()

        assert stats_dict["uptime"] == 10.0
        assert stats_dict["min_connect_time"] == 1.2
        assert stats_dict["max_connect_time"] == 0.0

        stats.min_connect_time = float("inf")
        stats_dict = stats.to_dict()

        assert stats_dict["min_connect_time"] == 0.0


class TestWebTransportClient:

    @pytest.fixture
    def client(self, mock_client_config: Any, mock_connection_manager: Any) -> WebTransportClient:
        return WebTransportClient(config=mock_client_config)

    @pytest.fixture
    def mock_client_config(self, mocker: MockerFixture) -> Any:
        mock = mocker.create_autospec(ClientConfig, instance=True)
        mock.connect_timeout = 10.0
        mock.update.return_value = mock
        mock.max_connections = 100
        mock.connection_idle_timeout = 60.0
        mock.max_event_queue_size = 100
        mock.max_event_listeners = 50
        mock.max_event_history_size = 100
        mock.user_agent = None
        return mock

    @pytest.fixture
    def mock_connect_class_method(self, mocker: MockerFixture, mock_webtransport_connection: Any) -> Any:
        return mocker.patch(
            "pywebtransport.client.client.WebTransportConnection.connect",
            return_value=mock_webtransport_connection,
            new_callable=mocker.AsyncMock,
        )

    @pytest.fixture
    def mock_connection_manager(self, mocker: MockerFixture) -> Any:
        manager = mocker.create_autospec(ConnectionManager, instance=True)
        manager.__aenter__ = mocker.AsyncMock()
        manager.__aexit__ = mocker.AsyncMock()
        manager.__len__.return_value = 0
        mocker.patch("pywebtransport.client.client.ConnectionManager", return_value=manager)
        return manager

    @pytest.fixture
    def mock_session(self, mocker: MockerFixture) -> Any:
        session = mocker.create_autospec(WebTransportSession, instance=True)
        session.session_id = "session-123"
        session.is_closed = False
        return session

    @pytest.fixture
    def mock_webtransport_connection(self, mocker: MockerFixture, mock_session: Any) -> Any:
        connection = mocker.create_autospec(WebTransportConnection, instance=True)
        connection.is_closed = False
        connection.state = ConnectionState.CONNECTED
        connection.is_connected = True
        connection.events = mocker.MagicMock()
        connection.events.wait_for = mocker.AsyncMock()
        connection.create_session = mocker.AsyncMock(return_value=mock_session)
        connection.close = mocker.AsyncMock()
        return connection

    @pytest.fixture(autouse=True)
    def setup_common_mocks(self, mocker: MockerFixture) -> None:
        mocker.patch("pywebtransport.client.client.parse_webtransport_url", return_value=("example.com", 443, "/"))
        mocker.patch("pywebtransport.client.client.format_duration")
        mocker.patch("pywebtransport.client.client.get_timestamp", return_value=1000.0)

    @pytest.mark.asyncio
    async def test_close_idempotency_and_concurrency(
        self, client: WebTransportClient, mock_connection_manager: Any
    ) -> None:
        await asyncio.gather(client.close(), client.close())

        assert client.is_closed
        mock_connection_manager.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_sequential_calls(self, client: WebTransportClient, mock_connection_manager: Any) -> None:
        await client.close()

        assert client.is_closed

        await client.close()

        mock_connection_manager.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_failure_certificate(
        self, client: WebTransportClient, mock_connect_class_method: Any
    ) -> None:
        mock_connect_class_method.side_effect = Exception("certificate verify failed")

        with pytest.raises(ConnectionError, match="Certificate verification failed"):
            await client.connect(url="https://example.com")

        assert client._stats.connections_failed == 1

    @pytest.mark.asyncio
    async def test_connect_failure_connection_refused(
        self, client: WebTransportClient, mock_connect_class_method: Any
    ) -> None:
        mock_connect_class_method.side_effect = ConnectionRefusedError()

        with pytest.raises(ConnectionError, match="Connection refused"):
            await client.connect(url="https://example.com")

        assert client._stats.connections_failed == 1

    @pytest.mark.asyncio
    async def test_connect_failure_generic(
        self, client: WebTransportClient, mock_connect_class_method: Any, mock_webtransport_connection: Any
    ) -> None:
        mock_connect_class_method.side_effect = RuntimeError("Generic failure")

        with pytest.raises(ClientError, match="Failed to connect to .*: Generic failure"):
            await client.connect(url="https://example.com")

        mock_webtransport_connection.close.assert_not_awaited()
        assert client._stats.connections_failed == 1

    @pytest.mark.asyncio
    async def test_connect_failure_timeout(self, client: WebTransportClient, mock_connect_class_method: Any) -> None:
        mock_connect_class_method.side_effect = asyncio.TimeoutError()

        with pytest.raises(TimeoutError, match="Connection timeout to .* during .*"):
            await client.connect(url="https://example.com")

        assert client._stats.connections_failed == 1

    @pytest.mark.asyncio
    async def test_connect_fails_during_session_creation(
        self, client: WebTransportClient, mock_webtransport_connection: Any, mock_connect_class_method: Any
    ) -> None:
        mock_webtransport_connection.create_session.side_effect = RuntimeError("Session init failed")

        with pytest.raises(ClientError, match="Session init failed"):
            await client.connect(url="https://example.com")

        mock_webtransport_connection.close.assert_awaited_once()
        assert client._stats.connections_failed == 1

    @pytest.mark.asyncio
    async def test_connect_fails_initial_handshake(
        self, client: WebTransportClient, mock_webtransport_connection: Any, mock_connect_class_method: Any
    ) -> None:
        mock_webtransport_connection.state = ConnectionState.FAILED

        with pytest.raises(ClientError, match="Connection failed state"):
            await client.connect(url="https://example.com")

        mock_webtransport_connection.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_success(
        self,
        client: WebTransportClient,
        mock_connect_class_method: Any,
        mock_connection_manager: Any,
        mock_webtransport_connection: Any,
        mock_session: Any,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("pywebtransport.client.client.get_timestamp", side_effect=[2000.0, 2001.23])

        session = await client.connect(url="https://example.com")

        mock_connect_class_method.assert_awaited_once()
        mock_connection_manager.add_connection.assert_awaited_once_with(connection=mock_webtransport_connection)
        mock_webtransport_connection.create_session.assert_awaited_once()
        args, kwargs = mock_webtransport_connection.create_session.call_args
        assert kwargs["path"] == "/"

        headers = kwargs["headers"]
        if isinstance(headers, dict):
            assert "user-agent" in headers
        else:
            assert any(k == "user-agent" for k, v in headers)

        assert session is mock_session
        stats = client._stats
        assert stats.connections_successful == 1
        assert stats.total_connect_time == pytest.approx(1.23)

    @pytest.mark.asyncio
    async def test_connect_ua_from_config(
        self, client: WebTransportClient, mock_client_config: Any, mock_connect_class_method: Any
    ) -> None:
        mock_client_config.user_agent = "CustomClient/1.2.3"

        await client.connect(url="https://example.com")

        mock_client_config.update.assert_called_once()
        passed_headers = mock_client_config.update.call_args.kwargs["headers"]

        if isinstance(passed_headers, dict):
            assert passed_headers["user-agent"] == "CustomClient/1.2.3"
        else:
            ua_header = next((v for k, v in passed_headers if k == "user-agent"), None)
            assert ua_header == "CustomClient/1.2.3"

    @pytest.mark.asyncio
    async def test_connect_ua_injection_dict_mode(
        self, client: WebTransportClient, mock_connect_class_method: Any, mock_client_config: Any, mocker: MockerFixture
    ) -> None:
        mocker.patch("pywebtransport.client.client.normalize_headers", return_value={"host": "example.com"})

        await client.connect(url="https://example.com")

        mock_client_config.update.assert_called_once()
        passed_headers = mock_client_config.update.call_args.kwargs["headers"]

        assert isinstance(passed_headers, dict)
        assert "user-agent" in passed_headers
        assert "PyWebTransport" in passed_headers["user-agent"]

    @pytest.mark.asyncio
    async def test_connect_waits_for_events_if_not_connected(
        self, client: WebTransportClient, mock_webtransport_connection: Any, mock_connect_class_method: Any
    ) -> None:
        mock_webtransport_connection.state = ConnectionState.CONNECTING

        async def simulate_connect(*args: Any, **kwargs: Any) -> None:
            mock_webtransport_connection.state = ConnectionState.CONNECTED

        mock_webtransport_connection.events.wait_for.side_effect = simulate_connect

        await client.connect(url="https://example.com")

        mock_webtransport_connection.events.wait_for.assert_awaited_once()
        call_args = mock_webtransport_connection.events.wait_for.call_args[1]
        assert EventType.CONNECTION_ESTABLISHED in call_args["event_type"]
        assert EventType.CONNECTION_FAILED in call_args["event_type"]

    @pytest.mark.asyncio
    async def test_connect_when_closed(self, client: WebTransportClient) -> None:
        await client.close()

        with pytest.raises(ClientError, match="Client is closed"):
            await client.connect(url="https://example.com")

    @pytest.mark.asyncio
    async def test_connect_with_explicit_user_agent_header(
        self, client: WebTransportClient, mock_connect_class_method: Any, mock_client_config: Any
    ) -> None:
        custom_ua = "ExplicitUA/1.0"

        await client.connect(url="https://example.com", headers={"user-agent": custom_ua})

        mock_client_config.update.assert_called_once()
        passed_headers = mock_client_config.update.call_args.kwargs["headers"]

        if isinstance(passed_headers, dict):
            assert passed_headers["user-agent"] == custom_ua
        else:
            ua_values = [v for k, v in passed_headers if k == "user-agent"]
            assert custom_ua in ua_values

    @pytest.mark.asyncio
    async def test_connect_with_headers(
        self,
        client: WebTransportClient,
        mock_connect_class_method: Any,
        mock_client_config: Any,
        mock_webtransport_connection: Any,
    ) -> None:
        client.set_default_headers(headers={"default": "header"})

        await client.connect(url="https://example.com", headers={"extra": "header"})

        mock_client_config.update.assert_called_once()
        passed_headers = mock_client_config.update.call_args.kwargs["headers"]

        if isinstance(passed_headers, dict):
            assert passed_headers["default"] == "header"
            assert passed_headers["extra"] == "header"
            assert "user-agent" in passed_headers
        else:
            header_dict = dict(passed_headers)
            assert header_dict["default"] == "header"
            assert header_dict["extra"] == "header"
            assert "user-agent" in header_dict

    @pytest.mark.asyncio
    async def test_context_manager(self, client: WebTransportClient, mock_connection_manager: Any) -> None:
        async with client:
            mock_connection_manager.__aenter__.assert_awaited_once()

        mock_connection_manager.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_diagnostics(
        self, client: WebTransportClient, mock_connection_manager: Any, mocker: MockerFixture
    ) -> None:
        mock_conn = mocker.MagicMock()
        mock_conn.state = ConnectionState.CONNECTED
        mock_connection_manager.get_all_resources = mocker.AsyncMock(return_value=[mock_conn])

        diagnostics = await client.diagnostics()

        assert isinstance(diagnostics, ClientDiagnostics)
        assert diagnostics.stats is client._stats
        assert diagnostics.connection_states == {ConnectionState.CONNECTED: 1}

    def test_initialization_custom_config(self, mocker: MockerFixture) -> None:
        mock_config = mocker.Mock(spec=ClientConfig)
        mock_config.max_connections = 15
        mock_config.connection_idle_timeout = 30.0
        mock_config.max_event_queue_size = 50
        mock_config.max_event_listeners = 20
        mock_config.max_event_history_size = 50
        mock_cm = mocker.patch("pywebtransport.client.client.ConnectionManager", autospec=True)

        client = WebTransportClient(config=mock_config)

        assert client.config is mock_config
        mock_cm.assert_called_once_with(max_connections=15)

    def test_initialization_default(self, mocker: MockerFixture) -> None:
        mock_cm_constructor = mocker.patch("pywebtransport.client.client.ConnectionManager", autospec=True)

        WebTransportClient()

        mock_cm_constructor.assert_called_once_with(max_connections=100)

    def test_str_representation(self, client: WebTransportClient, mock_connection_manager: Any) -> None:
        mock_connection_manager.__len__.return_value = 5

        assert str(client) == "WebTransportClient(status=open, connections=5)"

        client._closed = True

        assert str(client) == "WebTransportClient(status=closed, connections=5)"



================================================
FILE: tests/unit/client/test_fleet.py
================================================
"""Unit tests for the pywebtransport.client.fleet module."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from _pytest.logging import LogCaptureFixture
from pytest_asyncio import fixture as asyncio_fixture
from pytest_mock import MockerFixture

from pywebtransport import ClientError, ConnectionError, WebTransportClient, WebTransportSession
from pywebtransport.client import ClientFleet


class TestClientFleet:

    @asyncio_fixture
    async def fleet(self, fleet_unactivated: ClientFleet) -> AsyncGenerator[ClientFleet, None]:
        async with fleet_unactivated as activated_fleet:
            yield activated_fleet

    @pytest.fixture
    def fleet_unactivated(self, mock_clients: list[Any]) -> ClientFleet:
        return ClientFleet(clients=mock_clients)

    @pytest.fixture
    def mock_clients(self, mocker: MockerFixture) -> list[Any]:
        clients = []
        for i in range(3):
            client = mocker.create_autospec(WebTransportClient, instance=True, name=f"Client-{i}")
            client.__aenter__ = mocker.AsyncMock(return_value=client)
            client.__aexit__ = mocker.AsyncMock(return_value=None)
            client.connect = mocker.AsyncMock(return_value=mocker.create_autospec(WebTransportSession))
            clients.append(client)
        return clients

    @pytest.mark.asyncio
    async def test_aenter_and_aexit_lifecycle(self, fleet_unactivated: ClientFleet, mock_clients: list[Any]) -> None:
        async with fleet_unactivated:
            assert fleet_unactivated._active
            for client in mock_clients:
                cast(AsyncMock, client.__aenter__).assert_awaited_once()

        for client in mock_clients:
            cast(AsyncMock, client.__aexit__).assert_awaited_once()
        assert not fleet_unactivated._active

    @pytest.mark.asyncio
    async def test_aenter_cleanup_error(self, mock_clients: list[Any], caplog: LogCaptureFixture) -> None:
        successful_client = mock_clients[0]
        cast(AsyncMock, successful_client.__aenter__).return_value = successful_client
        cast(AsyncMock, successful_client.__aexit__).side_effect = IOError("Cleanup fail")

        failing_client = mock_clients[1]
        cast(AsyncMock, failing_client.__aenter__).side_effect = RuntimeError("Startup fail")

        fleet = ClientFleet(clients=mock_clients)

        with pytest.raises(ExceptionGroup):
            async with fleet:
                pass

        assert "Error during fleet cleanup after activation failure" in caplog.text

    @pytest.mark.asyncio
    async def test_aenter_rollback_logic(self, mock_clients: list[Any], mocker: MockerFixture) -> None:
        successful_client = mock_clients[0]
        failing_client = mock_clients[1]
        started_event = asyncio.Event()

        async def success_side_effect() -> Any:
            started_event.set()
            return successful_client

        async def fail_side_effect() -> None:
            await started_event.wait()
            raise RuntimeError("Activation failed")

        cast(AsyncMock, successful_client.__aenter__).side_effect = success_side_effect
        cast(AsyncMock, failing_client.__aenter__).side_effect = fail_side_effect

        fleet = ClientFleet(clients=mock_clients)

        with pytest.raises(ExceptionGroup):
            async with fleet:
                pass

        cast(AsyncMock, successful_client.__aexit__).assert_awaited_once()
        cast(AsyncMock, failing_client.__aexit__).assert_not_awaited()

    @pytest.mark.asyncio
    async def test_aexit_logs_errors(
        self, fleet_unactivated: ClientFleet, mock_clients: list[Any], caplog: LogCaptureFixture
    ) -> None:
        cast(AsyncMock, mock_clients[0].__aexit__).side_effect = IOError("Close failed")

        async with fleet_unactivated:
            pass

        assert "Error closing clients in fleet" in caplog.text
        cast(AsyncMock, mock_clients[1].__aexit__).assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_all_concurrency_limit(self, fleet: ClientFleet, mocker: MockerFixture) -> None:
        mock_sem = mocker.MagicMock()
        mock_sem.__aenter__ = mocker.AsyncMock()
        mock_sem.__aexit__ = mocker.AsyncMock()
        fleet._connect_sem = mock_sem

        await fleet.connect_all(url="https://example.com")

        assert mock_sem.__aenter__.await_count == 3

    @pytest.mark.asyncio
    async def test_connect_all_with_mixed_results(
        self, fleet: ClientFleet, mock_clients: list[Any], caplog: LogCaptureFixture
    ) -> None:
        url = "https://example.com"
        error = ConnectionError(message="Failed to connect")
        cast(AsyncMock, mock_clients[1].connect).side_effect = error

        sessions = await fleet.connect_all(url=url)

        assert len(sessions) == 2
        cast(AsyncMock, mock_clients[0].connect).assert_awaited_once_with(url=url)
        cast(AsyncMock, mock_clients[2].connect).assert_awaited_once_with(url=url)
        assert f"Client failed to connect: {error}" in caplog.text

    def test_get_client_after_close(self, fleet_unactivated: ClientFleet) -> None:
        with pytest.raises(ClientError, match="ClientFleet has not been activated"):
            fleet_unactivated.get_client()

    def test_get_client_count(self, fleet_unactivated: ClientFleet, mock_clients: list[Any]) -> None:
        assert fleet_unactivated.get_client_count() == len(mock_clients)

    def test_get_client_round_robin(self, fleet: ClientFleet, mock_clients: list[Any]) -> None:
        client_order = [fleet.get_client() for _ in range(len(mock_clients) + 1)]

        assert client_order[0] is mock_clients[0]
        assert client_order[1] is mock_clients[1]
        assert client_order[2] is mock_clients[2]
        assert client_order[3] is mock_clients[0]

    def test_init_success(self, mock_clients: list[Any]) -> None:
        fleet = ClientFleet(clients=mock_clients, max_concurrent_handshakes=10)

        assert fleet.get_client_count() == len(mock_clients)
        assert not fleet._active
        assert fleet._connect_sem._value == 10

    def test_init_with_no_clients(self) -> None:
        with pytest.raises(ValueError, match="ClientFleet requires at least one client instance"):
            ClientFleet(clients=[])

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method_name", ["connect_all"])
    async def test_methods_raise_if_not_activated_async(self, fleet_unactivated: ClientFleet, method_name: str) -> None:
        method_to_test = getattr(fleet_unactivated, method_name)
        kwargs = {"url": "https://url"} if method_name == "connect_all" else {}

        with pytest.raises(ClientError, match="ClientFleet has not been activated"):
            await method_to_test(**kwargs)



================================================
FILE: tests/unit/client/test_reconnecting.py
================================================
"""Unit tests for the pywebtransport.client.reconnecting module."""

import asyncio
import logging
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from _pytest.logging import LogCaptureFixture
from pytest_mock import MockerFixture

from pywebtransport import (
    ClientConfig,
    ClientError,
    ConnectionError,
    TimeoutError,
    WebTransportClient,
    WebTransportSession,
)
from pywebtransport.client import ReconnectingClient
from pywebtransport.types import EventType, SessionState


class TestReconnectingClient:

    URL = "https://example.com"

    @pytest.fixture
    def client(self, mock_underlying_client: Any) -> ReconnectingClient:
        return ReconnectingClient(url=self.URL, client=mock_underlying_client)

    @pytest.fixture
    def mock_session(self, mocker: MockerFixture) -> Any:
        session = mocker.create_autospec(WebTransportSession, instance=True)
        type(session).state = mocker.PropertyMock(return_value=SessionState.CONNECTED)
        session.is_closed = False
        session.close = mocker.AsyncMock(return_value=None)
        session._connection = mocker.Mock(return_value=mocker.AsyncMock())
        session.events = mocker.MagicMock()
        session.events.wait_for = mocker.AsyncMock()
        return session

    @pytest.fixture
    def mock_underlying_client(self, mocker: MockerFixture, mock_session: Any) -> Any:
        client = mocker.create_autospec(WebTransportClient, instance=True)
        client.connect = mocker.AsyncMock(return_value=mock_session)
        client.config = ClientConfig()
        return client

    @pytest.mark.asyncio
    async def test_aenter_and_aexit_lifecycle(self, client: ReconnectingClient, mocker: MockerFixture) -> None:
        mock_tg = mocker.AsyncMock(spec=asyncio.TaskGroup)
        mock_tg.create_task.return_value = mocker.Mock(spec=asyncio.Task)
        mocker.patch("asyncio.TaskGroup", return_value=mock_tg)

        connect_mock = cast(MagicMock, client._client.connect)
        connect_mock.side_effect = asyncio.CancelledError

        async with client:
            assert client._is_initialized
            assert client._tg is mock_tg
            mock_tg.__aenter__.assert_awaited_once()
            mock_tg.create_task.assert_called_once()

            call_args = mock_tg.create_task.call_args
            if call_args and "coro" in call_args.kwargs:
                call_args.kwargs["coro"].close()

        mock_tg.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_aenter_is_idempotent(self, client: ReconnectingClient, mocker: MockerFixture) -> None:
        mock_tg = mocker.AsyncMock(spec=asyncio.TaskGroup)
        mocker.patch("asyncio.TaskGroup", return_value=mock_tg)

        async with client:
            mock_tg.create_task.assert_called_once()

            call_args = mock_tg.create_task.call_args
            if call_args and "coro" in call_args.kwargs:
                call_args.kwargs["coro"].close()

            async with client as new_client:
                assert new_client is client

            mock_tg.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_aenter_on_closed_client(self, client: ReconnectingClient) -> None:
        await client.close()

        with pytest.raises(ClientError, match="Client is already closed"):
            async with client:
                pass

    @pytest.mark.asyncio
    async def test_aexit_closes_on_exception(self, client: ReconnectingClient, mocker: MockerFixture) -> None:
        close_spy = mocker.spy(client, "close")
        mock_tg = mocker.AsyncMock(spec=asyncio.TaskGroup)
        mocker.patch("asyncio.TaskGroup", return_value=mock_tg)

        with pytest.raises(RuntimeError, match="Test exception"):
            async with client:
                call_args = mock_tg.create_task.call_args
                if call_args and "coro" in call_args.kwargs:
                    call_args.kwargs["coro"].close()
                raise RuntimeError("Test exception")

        close_spy.assert_awaited_once()
        mock_tg.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_aexit_without_aenter(self, client: ReconnectingClient, mocker: MockerFixture) -> None:
        client._tg = None
        await client.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_close_idempotency(self, client: ReconnectingClient, mocker: MockerFixture) -> None:
        mock_tg = mocker.AsyncMock(spec=asyncio.TaskGroup)
        mock_task = mocker.Mock(spec=asyncio.Task)
        mock_task.done.return_value = False
        mock_tg.create_task.return_value = mock_task
        mocker.patch("asyncio.TaskGroup", return_value=mock_tg)

        await client.__aenter__()
        mock_tg.create_task.call_args.kwargs["coro"].close()

        assert client._reconnect_task is not None

        await client.close()
        mock_task.cancel.assert_called_once()

        mock_task.reset_mock()
        await client.close()
        mock_task.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_logs_session_close_error(
        self, client: ReconnectingClient, mock_session: Any, caplog: LogCaptureFixture
    ) -> None:
        client._session = mock_session
        mock_session.close.side_effect = RuntimeError("Close failed")

        await client.close()

        assert "Error closing session: Close failed" in caplog.text
        assert client._session is None

    @pytest.mark.asyncio
    async def test_close_with_active_session(
        self, client: ReconnectingClient, mock_session: Any, mocker: MockerFixture
    ) -> None:
        mock_tg = mocker.AsyncMock(spec=asyncio.TaskGroup)
        mocker.patch("asyncio.TaskGroup", return_value=mock_tg)

        async with client:
            mock_tg.create_task.call_args.kwargs["coro"].close()
            client._session = mock_session
            await client.close()
            mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_session_client_closed_while_waiting(
        self, client: ReconnectingClient, mocker: MockerFixture
    ) -> None:
        client._connected_event = asyncio.Event()
        client._tg = mocker.AsyncMock(spec=asyncio.TaskGroup)

        mock_task = mocker.Mock(spec=asyncio.Task)
        cast(MagicMock, mock_task.done).return_value = False
        client._reconnect_task = mock_task

        async def simulate_close_during_wait() -> None:
            client._closed = True
            assert client._connected_event is not None
            client._connected_event.set()

        mocker.patch.object(client._connected_event, "wait", side_effect=simulate_close_during_wait)

        with pytest.raises(ClientError, match="Client closed while waiting for session"):
            await client.get_session()

    @pytest.mark.asyncio
    async def test_get_session_crashes_propagation(self, client: ReconnectingClient) -> None:
        client._closed = False
        crash_error = ValueError("Unexpected crash")
        client._crashed_exception = crash_error
        client._connected_event = asyncio.Event()

        with pytest.raises(ClientError, match="Background reconnection task crashed") as exc_info:
            await client.get_session()

        assert exc_info.value.__cause__ is crash_error

    @pytest.mark.asyncio
    async def test_get_session_crashes_propagation_in_loop(
        self, client: ReconnectingClient, mocker: MockerFixture
    ) -> None:
        client._connected_event = asyncio.Event()
        client._tg = mocker.AsyncMock(spec=asyncio.TaskGroup)

        crash_error = ValueError("Crash during wait")

        async def wait_side_effect() -> None:
            client._crashed_exception = crash_error

        mocker.patch.object(client._connected_event, "wait", side_effect=wait_side_effect)

        with pytest.raises(ClientError, match="Background task crashed") as exc_info:
            await client.get_session()

        assert exc_info.value.__cause__ is crash_error

    @pytest.mark.asyncio
    async def test_get_session_defensive_task_check(self, client: ReconnectingClient, mocker: MockerFixture) -> None:
        client._connected_event = asyncio.Event()
        client._tg = mocker.AsyncMock(spec=asyncio.TaskGroup)
        client._reconnect_task = None
        call_count = 0

        async def side_effect() -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                client._closed = True

        mocker.patch.object(client._connected_event, "wait", side_effect=side_effect)

        with pytest.raises(ClientError, match="Client closed while waiting"):
            await client.get_session(wait_timeout=0.1)

    @pytest.mark.asyncio
    async def test_get_session_fails_if_task_done(self, client: ReconnectingClient, mocker: MockerFixture) -> None:
        client._connected_event = asyncio.Event()
        client._tg = mocker.AsyncMock(spec=asyncio.TaskGroup)

        mock_task = mocker.Mock(spec=asyncio.Task)
        cast(MagicMock, mock_task.done).return_value = True
        cast(MagicMock, mock_task.cancelled).return_value = False
        cast(MagicMock, mock_task.exception).return_value = None

        client._reconnect_task = mock_task

        async def simulate_event_wait() -> None:
            return

        mocker.patch.object(client._connected_event, "wait", side_effect=simulate_event_wait)

        with pytest.raises(ClientError, match="Reconnection task finished unexpectedly"):
            await client.get_session()

    @pytest.mark.asyncio
    async def test_get_session_on_closed_client(self, client: ReconnectingClient) -> None:
        await client.close()

        with pytest.raises(ClientError, match="Client is closed"):
            await client.get_session()

    @pytest.mark.asyncio
    async def test_get_session_succeeds_when_connected(
        self, client: ReconnectingClient, mock_session: Any, mocker: MockerFixture
    ) -> None:
        client._session = mock_session
        client._connected_event = asyncio.Event()
        client._connected_event.set()
        client._tg = mocker.AsyncMock(spec=asyncio.TaskGroup)

        session = await client.get_session(wait_timeout=0.1)

        assert session is mock_session

    @pytest.mark.asyncio
    async def test_get_session_task_cancelled_error(self, client: ReconnectingClient, mocker: MockerFixture) -> None:
        client._connected_event = asyncio.Event()
        client._tg = mocker.AsyncMock(spec=asyncio.TaskGroup)

        mock_task = mocker.Mock(spec=asyncio.Task)
        cast(MagicMock, mock_task.done).return_value = True
        cast(MagicMock, mock_task.cancelled).return_value = True
        client._reconnect_task = mock_task

        async def simulate_event_wait() -> None:
            return

        mocker.patch.object(client._connected_event, "wait", side_effect=simulate_event_wait)

        with pytest.raises(ClientError, match="Reconnection task cancelled"):
            await client.get_session()

    @pytest.mark.asyncio
    async def test_get_session_task_exception(self, client: ReconnectingClient, mocker: MockerFixture) -> None:
        client._connected_event = asyncio.Event()
        client._tg = mocker.AsyncMock(spec=asyncio.TaskGroup)

        mock_task = mocker.Mock(spec=asyncio.Task)
        cast(MagicMock, mock_task.done).return_value = True
        cast(MagicMock, mock_task.cancelled).return_value = False
        original_error = RuntimeError("Task died")
        cast(MagicMock, mock_task.exception).return_value = original_error

        client._reconnect_task = mock_task

        async def simulate_event_wait() -> None:
            return

        mocker.patch.object(client._connected_event, "wait", side_effect=simulate_event_wait)

        with pytest.raises(ClientError, match="Reconnection task failed: Task died") as exc_info:
            await client.get_session()

        assert exc_info.value.__cause__ is original_error

    @pytest.mark.asyncio
    async def test_get_session_timeout(self, client: ReconnectingClient, mock_underlying_client: Any) -> None:
        async def sleep_forever(*args: Any, **kwargs: Any) -> Any:
            await asyncio.sleep(10)

        mock_underlying_client.connect.side_effect = sleep_forever
        mock_underlying_client.config.max_connection_retries = 5

        async with client:
            with pytest.raises(asyncio.TimeoutError):
                await client.get_session(wait_timeout=0.01)

    @pytest.mark.asyncio
    async def test_get_session_uninitialized(self, client: ReconnectingClient) -> None:
        with pytest.raises(ClientError, match="ReconnectingClient has not been activated"):
            await client.get_session()

    @pytest.mark.asyncio
    async def test_get_session_waits_and_succeeds(
        self, client: ReconnectingClient, mock_session: Any, mocker: MockerFixture
    ) -> None:
        session_available = asyncio.Event()

        async def wait_side_effect(*args: Any, **kwargs: Any) -> None:
            await session_available.wait()
            client._session = mock_session

        client._connected_event = asyncio.Event()
        client._tg = mocker.AsyncMock(spec=asyncio.TaskGroup)
        mocker.patch.object(client._connected_event, "wait", side_effect=wait_side_effect)

        task = asyncio.create_task(client.get_session(wait_timeout=1.0))
        await asyncio.sleep(0.01)
        session_available.set()
        session = await task

        assert session is mock_session

    def test_init(self, mock_underlying_client: Any) -> None:
        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)

        assert client._url == self.URL
        assert client._client is mock_underlying_client
        assert client._config is mock_underlying_client.config
        assert client._session is None
        assert not client._closed
        assert not client._is_initialized

    @pytest.mark.parametrize(
        ("session_state", "event_is_set", "expected"),
        [
            (SessionState.CONNECTED, True, True),
            (SessionState.CONNECTING, True, False),
            (SessionState.CONNECTED, False, False),
        ],
    )
    def test_is_connected_property(
        self,
        client: ReconnectingClient,
        mock_session: Any,
        mocker: MockerFixture,
        session_state: SessionState,
        event_is_set: bool,
        expected: bool,
    ) -> None:
        type(mock_session).state = mocker.PropertyMock(return_value=session_state)
        client._session = mock_session
        client._connected_event = asyncio.Event()
        if event_is_set:
            client._connected_event.set()

        assert client.is_connected is expected

    def test_is_connected_property_when_uninitialized(self, client: ReconnectingClient) -> None:
        assert not client.is_connected

    @pytest.mark.asyncio
    async def test_reconnect_loop_cancels_during_sleep(
        self, mock_underlying_client: Any, mocker: MockerFixture
    ) -> None:
        sleep_started = asyncio.Event()
        config = ClientConfig(retry_delay=10, max_connection_retries=1)
        mock_underlying_client.config = config
        mock_underlying_client.connect.side_effect = ConnectionError("Failed to connect")

        original_sleep = asyncio.sleep

        async def sleep_side_effect(delay: float) -> Any:
            sleep_started.set()
            await original_sleep(delay=delay)

        mocker.patch("asyncio.sleep", side_effect=sleep_side_effect)
        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)

        async with client:
            async with asyncio.timeout(delay=1):
                await sleep_started.wait()

            assert client._reconnect_task is not None
            client._reconnect_task.cancel()
            try:
                await client._reconnect_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_reconnect_loop_cleanup_edge_cases(
        self, mock_underlying_client: Any, mock_session: Any, caplog: LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)

        mock_underlying_client.connect.return_value = mock_session

        async def wait_forever(*args: Any, **kwargs: Any) -> None:
            await asyncio.sleep(10)

        mock_session.events.wait_for.side_effect = wait_forever

        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)
        async with client:
            await asyncio.sleep(0.01)
            assert client._reconnect_task
            client._reconnect_task.cancel()
            try:
                await client._reconnect_task
            except asyncio.CancelledError:
                pass

        assert client._session is None

    @pytest.mark.asyncio
    async def test_reconnect_loop_cleanup_error(
        self, mock_underlying_client: Any, mock_session: Any, caplog: LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)

        mock_underlying_client.connect.return_value = mock_session

        async def wait_forever(*args: Any, **kwargs: Any) -> None:
            await asyncio.sleep(10)

        mock_session.events.wait_for.side_effect = wait_forever

        mock_session.close.side_effect = RuntimeError("Cleanup failed")

        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)

        async with client:
            await asyncio.sleep(0.01)

            assert client._reconnect_task is not None
            client._reconnect_task.cancel()
            try:
                await client._reconnect_task
            except asyncio.CancelledError:
                pass

        assert "Error closing old session during reconnect: Cleanup failed" in caplog.text

    @pytest.mark.asyncio
    async def test_reconnect_loop_crash_after_connect(
        self, client: ReconnectingClient, mock_underlying_client: Any, mock_session: Any, mocker: MockerFixture
    ) -> None:
        mock_underlying_client.connect.return_value = mock_session

        mock_emit = mocker.patch.object(client, "emit", new_callable=mocker.AsyncMock)
        mock_emit.side_effect = RuntimeError("Crash after connect")

        async with client:
            try:
                assert client._reconnect_task
                await client._reconnect_task
            except RuntimeError:
                pass

        assert isinstance(client._crashed_exception, RuntimeError)

    @pytest.mark.asyncio
    async def test_reconnect_loop_crash_during_session_wait(
        self, client: ReconnectingClient, mock_underlying_client: Any, mock_session: Any
    ) -> None:
        mock_underlying_client.connect.return_value = mock_session

        mock_session.events.wait_for.side_effect = ValueError("Unexpected crash in wait")

        async with client:
            try:
                assert client._reconnect_task
                await client._reconnect_task
            except ValueError:
                pass

        assert isinstance(client._crashed_exception, ValueError)

    @pytest.mark.asyncio
    async def test_reconnect_loop_crashes_and_sets_event(
        self, client: ReconnectingClient, mock_underlying_client: Any, mocker: MockerFixture
    ) -> None:
        mock_underlying_client.connect.side_effect = ValueError("Fatal crash")
        event_set_spy = mocker.spy(asyncio.Event, "set")

        async with client:
            assert client._reconnect_task is not None
            await client._reconnect_task

        assert client._crashed_exception is not None
        assert isinstance(client._crashed_exception, ValueError)
        assert client._connected_event.is_set()
        event_set_spy.assert_called()

    @pytest.mark.asyncio
    async def test_reconnect_loop_delay_capping(
        self, mock_underlying_client: Any, mock_session: Any, mocker: MockerFixture
    ) -> None:
        connection_established = asyncio.Event()
        mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
        config = ClientConfig(retry_delay=0.1, retry_backoff=2.0, max_retry_delay=0.15)
        mock_underlying_client.config = config
        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)
        mock_emit = mocker.patch.object(client, "emit", new_callable=mocker.AsyncMock)
        mock_emit.side_effect = lambda *args, **kwargs: connection_established.set()

        mock_session.events.wait_for.side_effect = asyncio.CancelledError

        mock_underlying_client.connect.side_effect = [
            ConnectionError(message="Fail 1"),
            ConnectionError(message="Fail 2"),
            mock_session,
        ]

        async with client:
            async with asyncio.timeout(delay=1):
                await connection_established.wait()

        mock_sleep.assert_has_awaits([mocker.call(delay=0.1), mocker.call(delay=0.15)])

    @pytest.mark.asyncio
    async def test_reconnect_loop_full_cycle(
        self, mock_underlying_client: Any, mock_session: Any, caplog: LogCaptureFixture, mocker: MockerFixture
    ) -> None:
        config = ClientConfig(max_connection_retries=5, retry_delay=0.01)
        mock_underlying_client.config = config
        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)

        connect_attempts = 0
        attempt_event = asyncio.Event()

        async def connect_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal connect_attempts
            connect_attempts += 1
            attempt_event.set()
            if connect_attempts == 1:
                return mock_session
            if connect_attempts == 2:
                raise ConnectionError("Simulated network fail")
            if connect_attempts == 3:
                return mock_session
            await asyncio.Future()
            return mock_session

        mock_underlying_client.connect.side_effect = connect_side_effect

        session1_closed = asyncio.Event()

        async def wait_for_side_effect(*args: Any, **kwargs: Any) -> None:
            if connect_attempts == 1:
                return
            await session1_closed.wait()

        mock_session.events.wait_for.side_effect = wait_for_side_effect

        mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

        async with client:
            try:
                async with asyncio.timeout(2.0):
                    while connect_attempts < 3:
                        await attempt_event.wait()
                        attempt_event.clear()
            except asyncio.TimeoutError:
                pytest.fail(f"Timed out waiting for connection attempts. Current: {connect_attempts}")

            assert connect_attempts >= 3
            assert "Connection to https://example.com lost, attempting to reconnect..." in caplog.text
            assert any("Connection attempt 1 failed" in r.message for r in caplog.records)

            session1_closed.set()
            client._closed = True

    @pytest.mark.asyncio
    async def test_reconnect_loop_infinite_retries(self, mock_underlying_client: Any, mocker: MockerFixture) -> None:
        failed_event = asyncio.Event()
        original_sleep = asyncio.sleep
        mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

        config_mock = MagicMock()
        config_mock.max_connection_retries = -1
        config_mock.retry_delay = 0.01
        config_mock.retry_backoff = 1.0
        config_mock.max_retry_delay = 1.0
        config_mock.max_event_queue_size = 100
        config_mock.max_event_listeners = 100
        config_mock.max_event_history_size = 100
        mock_underlying_client.config = config_mock

        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)

        fail_count = 0

        async def connect_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal fail_count
            fail_count += 1
            if fail_count >= 5:
                failed_event.set()
            await original_sleep(0)
            raise TimeoutError("Fail")

        mock_underlying_client.connect.side_effect = connect_side_effect

        async with client:
            async with asyncio.timeout(delay=2.0):
                await failed_event.wait()

            assert client._reconnect_task is not None
            client._reconnect_task.cancel()
            try:
                await client._reconnect_task
            except asyncio.CancelledError:
                pass

        assert mock_underlying_client.connect.call_count >= 5

    @pytest.mark.asyncio
    async def test_reconnect_loop_max_retries_exceeded(
        self, mock_underlying_client: Any, mocker: MockerFixture
    ) -> None:
        failed_event = asyncio.Event()
        mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
        config = ClientConfig(max_connection_retries=2, retry_delay=0.01)
        mock_underlying_client.config = config
        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)
        mock_emit = mocker.patch.object(client, "emit", new_callable=mocker.AsyncMock)

        async def emit_side_effect(*, event_type: EventType, data: Any) -> None:
            if event_type == EventType.CONNECTION_FAILED:
                failed_event.set()

        mock_emit.side_effect = emit_side_effect
        mock_underlying_client.connect.side_effect = ClientError(message="Failed")

        async with client:
            async with asyncio.timeout(delay=1):
                await failed_event.wait()

        assert mock_underlying_client.connect.call_count == 3
        mock_emit.assert_awaited_with(
            event_type=EventType.CONNECTION_FAILED,
            data={"reason": "max_retries_exceeded", "last_error": str(ClientError(message="Failed"))},
        )

    @pytest.mark.asyncio
    async def test_reconnect_loop_respects_closed_flag(self, client: ReconnectingClient) -> None:
        client._closed = True
        await client._reconnect_loop()

    @pytest.mark.asyncio
    async def test_reconnect_loop_retries_multiple_times(
        self, mock_underlying_client: Any, mock_session: Any, mocker: MockerFixture
    ) -> None:
        connection_established = asyncio.Event()
        mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
        config = ClientConfig(retry_delay=0.01, max_connection_retries=5)
        mock_underlying_client.config = config
        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)
        mock_emit = mocker.patch.object(client, "emit", new_callable=mocker.AsyncMock)
        mock_emit.side_effect = lambda *args, **kwargs: connection_established.set()
        mock_session.events.wait_for.side_effect = asyncio.CancelledError
        errors = [ConnectionError(message="Fail")] * 5
        mock_underlying_client.connect.side_effect = [*errors, mock_session]

        async with client:
            async with asyncio.timeout(delay=1):
                await connection_established.wait()

        assert mock_underlying_client.connect.call_count == 6
        assert mock_sleep.call_count == 5

    @pytest.mark.asyncio
    async def test_reconnect_loop_skips_wait_if_session_closed(
        self, mock_underlying_client: Any, mock_session: Any, mocker: MockerFixture
    ) -> None:
        type(mock_session).state = mocker.PropertyMock(return_value=SessionState.CLOSED)

        mock_underlying_client.connect.side_effect = [mock_session, asyncio.CancelledError]

        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)

        async with client:
            await asyncio.sleep(0.01)

        mock_session.events.wait_for.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconnect_loop_success_and_disconnect(
        self, mock_underlying_client: Any, mock_session: Any, caplog: LogCaptureFixture, mocker: MockerFixture
    ) -> None:
        first_connection_made = asyncio.Event()
        connection_lost = asyncio.Event()
        closed_future: asyncio.Future[None] = asyncio.Future()

        async def wait_for_side_effect(*args: Any, **kwargs: Any) -> None:
            await closed_future

        mock_session.events.wait_for.side_effect = wait_for_side_effect

        mock_underlying_client.connect.side_effect = [mock_session, ConnectionError(message="Reconnect failed")]
        config = ClientConfig(max_connection_retries=0, retry_delay=0.01)
        mock_underlying_client.config = config
        client = ReconnectingClient(url=self.URL, client=mock_underlying_client)
        mock_emit = mocker.patch.object(client, "emit", new_callable=mocker.AsyncMock)

        async def emit_side_effect(*, event_type: EventType, data: Any) -> None:
            if event_type == EventType.CONNECTION_ESTABLISHED:
                first_connection_made.set()
            elif event_type == EventType.CONNECTION_LOST:
                connection_lost.set()

        mock_emit.side_effect = emit_side_effect

        async with client:
            async with asyncio.timeout(delay=1):
                await first_connection_made.wait()
            mock_session.events.wait_for.assert_called()
            closed_future.set_result(None)
            async with asyncio.timeout(delay=1):
                await connection_lost.wait()

        mock_emit.assert_any_call(
            event_type=EventType.CONNECTION_ESTABLISHED, data={"session": mock_session, "attempt": 1}
        )
        mock_emit.assert_any_call(event_type=EventType.CONNECTION_LOST, data={"url": self.URL})
        assert f"Connection to {self.URL} lost, attempting to reconnect..." in caplog.text



================================================
FILE: tests/unit/client/test_utils.py
================================================
"""Unit tests for the pywebtransport.client.utils module."""

import pytest

from pywebtransport import Headers
from pywebtransport.client.utils import normalize_headers, parse_webtransport_url


class TestNormalizeHeaders:

    def test_normalize_headers_dict(self) -> None:
        headers: Headers = {"Content-Type": "application/json", "USER-AGENT": "test-client"}

        normalized = normalize_headers(headers=headers)

        assert isinstance(normalized, dict)
        assert normalized == {"content-type": "application/json", "user-agent": "test-client"}

    def test_normalize_headers_list(self) -> None:
        headers: Headers = [("Content-Type", "application/json"), ("USER-AGENT", "test-client")]

        normalized = normalize_headers(headers=headers)

        assert isinstance(normalized, list)
        assert normalized == [("content-type", "application/json"), ("user-agent", "test-client")]


class TestUrlUtils:

    @pytest.mark.parametrize(
        "url, error_msg",
        [
            ("ftp://example.com", "Unsupported scheme 'ftp'"),
            ("http://example.com", "Unsupported scheme 'http'"),
            ("https://", "Missing hostname in URL"),
        ],
    )
    def test_parse_webtransport_url_raises_error(self, url: str, error_msg: str) -> None:
        with pytest.raises(ValueError, match=error_msg):
            parse_webtransport_url(url=url)

    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://example.com", ("example.com", 443, "/")),
            ("https://example.com:0", ("example.com", 0, "/")),
            ("https://localhost:8080/path", ("localhost", 8080, "/path")),
            ("https://[::1]:9090/q?a=1#f", ("::1", 9090, "/q?a=1")),
        ],
    )
    def test_parse_webtransport_url_success(self, url: str, expected: tuple[str, int, str]) -> None:
        parsed_url = parse_webtransport_url(url=url)

        assert parsed_url == expected



================================================
FILE: tests/unit/manager/__init__.py
================================================
[Empty file]


================================================
FILE: tests/unit/manager/test_base.py
================================================
"""Unit tests for the pywebtransport.manager._base module."""

import asyncio
import logging
from typing import cast

import pytest
from _pytest.logging import LogCaptureFixture
from pytest_mock import MockerFixture

from pywebtransport.events import Event, EventEmitter
from pywebtransport.manager._base import BaseResourceManager
from pywebtransport.types import EventType


class MockResource:

    def __init__(self, resource_id: str) -> None:
        self.resource_id = resource_id
        self.events = EventEmitter()
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    @property
    def is_closed(self) -> bool:
        return self.closed


class FalsyResource(MockResource):

    def __bool__(self) -> bool:
        return False


class ConcreteResourceManager(BaseResourceManager[str, MockResource]):

    _resource_closed_event_type = EventType.CONNECTION_CLOSED

    async def _close_resource(self, *, resource: MockResource) -> None:
        await resource.close()

    def _get_resource_id(self, *, resource: MockResource) -> str:
        return resource.resource_id


@pytest.mark.asyncio
class TestBaseResourceManager:

    @pytest.fixture
    def manager(self) -> ConcreteResourceManager:
        return ConcreteResourceManager(resource_name="test_item", max_resources=5)

    async def test_abstract_methods_raise(self) -> None:
        resource = MockResource("r1")

        class PartialManager(BaseResourceManager[str, MockResource]):
            _resource_closed_event_type = EventType.CONNECTION_CLOSED

            async def _close_resource(self, *, resource: MockResource) -> None:
                await getattr(BaseResourceManager, "_close_resource")(self, resource=resource)

            def _get_resource_id(self, *, resource: MockResource) -> str:
                return cast(str, getattr(BaseResourceManager, "_get_resource_id")(self, resource=resource))

        manager = PartialManager(resource_name="test", max_resources=1)

        with pytest.raises(NotImplementedError):
            await manager._close_resource(resource=resource)

        with pytest.raises(NotImplementedError):
            manager._get_resource_id(resource=resource)

    async def test_add_resource(self, manager: ConcreteResourceManager) -> None:
        resource = MockResource("r1")

        async with manager:
            await manager.add_resource(resource=resource)
            assert len(manager) == 1
            stats = await manager.get_stats()
            assert stats["total_created"] == 1
            assert stats["current_count"] == 1

            retrieved = await manager.get_resource(resource_id="r1")
            assert retrieved is resource

    async def test_add_resource_closed_during_registration(
        self, manager: ConcreteResourceManager, mocker: MockerFixture
    ) -> None:
        resource = MockResource("r1")
        mocker.patch.object(manager, "_check_is_closed", return_value=True)
        mock_off = mocker.patch.object(resource.events, "off", side_effect=ValueError("Handler not found"))

        async with manager:
            with pytest.raises(RuntimeError, match="closed during registration"):
                await manager.add_resource(resource=resource)

        mock_off.assert_called_once()
        assert len(manager) == 0

    async def test_add_resource_closed_handler_invalid_data(
        self, manager: ConcreteResourceManager, mocker: MockerFixture
    ) -> None:
        resource = MockResource("r1")

        async with manager:
            await manager.add_resource(resource=resource)

            event = Event(type=EventType.CONNECTION_CLOSED, data="invalid")
            resource.events.emit_nowait(event_type=EventType.CONNECTION_CLOSED, data=event.data)
            await asyncio.sleep(0.01)

            assert len(manager) == 0

    async def test_add_resource_closed_handler_mismatch_id(
        self, manager: ConcreteResourceManager, caplog: LogCaptureFixture
    ) -> None:
        resource = MockResource("r1")

        async with manager:
            await manager.add_resource(resource=resource)

            event = Event(type=EventType.CONNECTION_CLOSED, data={"test_item_id": "other"})
            resource.events.emit_nowait(event_type=EventType.CONNECTION_CLOSED, data=event.data)
            await asyncio.sleep(0.01)

            assert len(manager) == 0
            assert "Resource ID mismatch in close event" in caplog.text
            assert "test_item" in caplog.text
            assert "other" in caplog.text

    async def test_add_resource_closed_inside_lock(self, manager: ConcreteResourceManager) -> None:
        class FlakyClosedResource(MockResource):
            def __init__(self, resource_id: str) -> None:
                super().__init__(resource_id)
                self._access_count = 0

            @property
            def is_closed(self) -> bool:
                self._access_count += 1
                return self._access_count > 1

        resource = FlakyClosedResource("r1")

        async with manager:
            with pytest.raises(RuntimeError, match="Cannot add closed test_item"):
                await manager.add_resource(resource=resource)

        assert len(manager) == 0

    async def test_add_resource_duplicate(self, manager: ConcreteResourceManager, caplog: LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG)
        resource = MockResource("r1")

        async with manager:
            await manager.add_resource(resource=resource)
            await manager.add_resource(resource=resource)

            assert len(manager) == 1
            stats = await manager.get_stats()
            assert stats["total_created"] == 1

            assert "Resource r1 already managed." in caplog.text

    async def test_add_resource_initially_closed(self, manager: ConcreteResourceManager) -> None:
        resource = MockResource("r1")
        await resource.close()

        async with manager:
            with pytest.raises(RuntimeError, match="Cannot add closed test_item"):
                await manager.add_resource(resource=resource)

        assert len(manager) == 0

    async def test_add_resource_limit_reached(self, manager: ConcreteResourceManager) -> None:
        manager._max_resources = 1
        r1 = MockResource("r1")
        r2 = MockResource("r2")

        async with manager:
            await manager.add_resource(resource=r1)

            with pytest.raises(RuntimeError, match="Maximum test_item limit reached"):
                await manager.add_resource(resource=r2)

            assert len(manager) == 1
            assert r2.closed is True

    async def test_add_resource_not_activated(self, manager: ConcreteResourceManager) -> None:
        resource = MockResource("r1")

        with pytest.raises(RuntimeError, match="is not activated"):
            await manager.add_resource(resource=resource)

    async def test_add_resource_shutting_down(self, manager: ConcreteResourceManager) -> None:
        resource = MockResource("r1")

        async with manager:
            await manager.shutdown()
            with pytest.raises(RuntimeError, match="is shutting down"):
                await manager.add_resource(resource=resource)
            assert resource.closed is True

    async def test_close_all_resources_event_off_error(
        self, manager: ConcreteResourceManager, mocker: MockerFixture
    ) -> None:
        resource = MockResource("r1")
        mocker.patch.object(resource.events, "off", side_effect=ValueError("Cleanup error"))

        async with manager:
            await manager.add_resource(resource=resource)
            await manager.shutdown()

        assert len(manager) == 0

    async def test_close_all_resources_no_lock(self, manager: ConcreteResourceManager) -> None:
        await manager._close_all_resources()

        assert len(manager) == 0

    async def test_close_all_resources_stats_update(self, manager: ConcreteResourceManager) -> None:
        async with manager:
            pass

        assert manager._stats["total_closed"] == 0

    async def test_context_manager_lifecycle(self, manager: ConcreteResourceManager) -> None:
        assert manager._lock is None

        async def run_context() -> None:
            async with manager:
                assert manager._lock is not None
                assert not manager._is_shutting_down

        await run_context()

        assert manager._is_shutting_down is True

    async def test_get_all_resources(self, manager: ConcreteResourceManager) -> None:
        r1 = MockResource("r1")
        r2 = MockResource("r2")

        async with manager:
            await manager.add_resource(resource=r1)
            await manager.add_resource(resource=r2)

            all_res = await manager.get_all_resources()
            assert len(all_res) == 2
            assert r1 in all_res
            assert r2 in all_res

    async def test_get_all_resources_no_lock(self, manager: ConcreteResourceManager) -> None:
        assert await manager.get_all_resources() == []

    async def test_get_resource_no_lock(self, manager: ConcreteResourceManager) -> None:
        assert await manager.get_resource(resource_id="r1") is None

    async def test_get_stats_no_lock(self, manager: ConcreteResourceManager) -> None:
        assert await manager.get_stats() == {}

    async def test_handle_resource_closed_allowed_during_shutdown(
        self, manager: ConcreteResourceManager, mocker: MockerFixture
    ) -> None:
        manager._is_shutting_down = True
        manager._lock = asyncio.Lock()
        manager._resources["r1"] = MockResource("r1")

        await manager._handle_resource_closed(resource_id="r1")

        assert "r1" not in manager._resources
        assert manager._stats["total_closed"] == 1

    async def test_handle_resource_closed_falsy_resource(self, manager: ConcreteResourceManager) -> None:
        resource = FalsyResource("r_falsy")

        async with manager:
            await manager.add_resource(resource=resource)
            await manager._handle_resource_closed(resource_id="r_falsy")

            assert len(manager) == 0
            stats = await manager.get_stats()
            assert stats["total_closed"] == 1

    async def test_handle_resource_closed_no_lock(self, manager: ConcreteResourceManager) -> None:
        await manager._handle_resource_closed(resource_id="r1")

    async def test_handle_resource_closed_resource_not_found(self, manager: ConcreteResourceManager) -> None:
        manager._lock = asyncio.Lock()

        await manager._handle_resource_closed(resource_id="non_existent")

        assert manager._stats["total_closed"] == 0

    async def test_resource_closed_event_handling(self, manager: ConcreteResourceManager) -> None:
        resource = MockResource("r1")

        async with manager:
            await manager.add_resource(resource=resource)
            assert len(manager) == 1

            event = Event(type=EventType.CONNECTION_CLOSED, data={"test_item_id": "r1"})
            resource.events.emit_nowait(event_type=EventType.CONNECTION_CLOSED, data=event.data)

            await asyncio.sleep(0.01)

            assert len(manager) == 0
            stats = await manager.get_stats()
            assert stats["total_closed"] == 1

    async def test_shutdown_closes_resources(self, manager: ConcreteResourceManager) -> None:
        r1 = MockResource("r1")
        r2 = MockResource("r2")

        async with manager:
            await manager.add_resource(resource=r1)
            await manager.add_resource(resource=r2)

        assert r1.closed
        assert r2.closed
        assert len(manager) == 0
        assert manager._stats["total_closed"] == 2

    async def test_shutdown_handles_multiple_close_errors(
        self, manager: ConcreteResourceManager, mocker: MockerFixture, caplog: LogCaptureFixture
    ) -> None:
        r1 = MockResource("r1")
        r2 = MockResource("r2")
        mocker.patch.object(r1, "close", side_effect=ValueError("Fail 1"))
        mocker.patch.object(r2, "close", side_effect=RuntimeError("Fail 2"))

        async with manager:
            await manager.add_resource(resource=r1)
            await manager.add_resource(resource=r2)

        assert "Errors occurred while closing managed test_items" in caplog.text
        assert "Fail 1" in caplog.text or "Fail 2" in caplog.text
        assert len(manager) == 0

    async def test_shutdown_idempotent(self, manager: ConcreteResourceManager) -> None:
        async with manager:
            await manager.shutdown()
            await manager.shutdown()

        assert manager._is_shutting_down



================================================
FILE: tests/unit/manager/test_connection.py
================================================
"""Unit tests for the pywebtransport.manager.connection module."""

import asyncio
from typing import cast
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from pywebtransport.connection import WebTransportConnection
from pywebtransport.events import EventEmitter
from pywebtransport.manager import ConnectionManager
from pywebtransport.types import ConnectionState


class TestConnectionManager:

    @pytest.fixture
    def manager(self) -> ConnectionManager:
        return ConnectionManager(max_connections=10)

    @pytest.fixture
    def mock_connection(self, mocker: MockerFixture) -> MagicMock:
        conn = mocker.Mock(spec=WebTransportConnection)
        conn.connection_id = "conn-1"
        conn.state = ConnectionState.CONNECTED
        conn.is_closed = False
        conn.events = EventEmitter()
        conn.close = mocker.AsyncMock()
        return cast(MagicMock, conn)

    @pytest.mark.asyncio
    async def test_add_connection(self, manager: ConnectionManager, mock_connection: MagicMock) -> None:
        async with manager:
            conn_id = await manager.add_connection(connection=mock_connection)

            assert conn_id == "conn-1"
            assert len(manager) == 1
            assert await manager.get_resource(resource_id="conn-1") is mock_connection

    @pytest.mark.asyncio
    async def test_close_resource_idempotency(self, manager: ConnectionManager, mock_connection: MagicMock) -> None:
        mock_connection.is_closed = True

        await manager._close_resource(resource=mock_connection)

        mock_connection.close.assert_not_called()

    def test_get_resource_id(self, manager: ConnectionManager, mock_connection: MagicMock) -> None:
        assert manager._get_resource_id(resource=mock_connection) == "conn-1"

    @pytest.mark.asyncio
    async def test_get_stats_includes_states(self, manager: ConnectionManager, mocker: MockerFixture) -> None:
        c1 = mocker.Mock(spec=WebTransportConnection)
        c1.connection_id = "c1"
        c1.events = EventEmitter()
        c1.state = ConnectionState.CONNECTED
        c1.is_closed = False

        c2 = mocker.Mock(spec=WebTransportConnection)
        c2.connection_id = "c2"
        c2.events = EventEmitter()
        c2.state = ConnectionState.CONNECTING
        c2.is_closed = False

        async with manager:
            await manager.add_connection(connection=c1)
            await manager.add_connection(connection=c2)

            stats = await manager.get_stats()

            assert stats["current_count"] == 2
            assert stats["states"]["connected"] == 1
            assert stats["states"]["connecting"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_no_lock(self, manager: ConnectionManager) -> None:
        stats = await manager.get_stats()

        assert stats == {}

    @pytest.mark.asyncio
    async def test_handle_resource_closed_guards_no_lock(self, manager: ConnectionManager) -> None:
        await manager._handle_resource_closed(resource_id="c1")

    @pytest.mark.asyncio
    async def test_handle_resource_closed_schedules_close(
        self, manager: ConnectionManager, mock_connection: MagicMock
    ) -> None:
        async with manager:
            await manager.add_connection(connection=mock_connection)

            await manager._handle_resource_closed(resource_id="conn-1")

            assert len(manager) == 0
            await asyncio.sleep(0)
            mock_connection.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_resource_closed_task_lifecycle(
        self, manager: ConnectionManager, mock_connection: MagicMock
    ) -> None:
        close_finished = asyncio.Event()

        async def close_side_effect() -> None:
            await close_finished.wait()

        mock_connection.close.side_effect = close_side_effect

        async with manager:
            await manager.add_connection(connection=mock_connection)

            await manager._handle_resource_closed(resource_id="conn-1")

            assert len(manager._closing_tasks) == 1

            close_finished.set()

            for _ in range(5):
                if len(manager._closing_tasks) == 0:
                    break
                await asyncio.sleep(0)

            assert len(manager._closing_tasks) == 0

    @pytest.mark.asyncio
    async def test_handle_resource_closed_unmanaged(
        self, manager: ConnectionManager, mock_connection: MagicMock
    ) -> None:
        async with manager:
            await manager._handle_resource_closed(resource_id="conn-1")

            mock_connection.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_remove_connection(self, manager: ConnectionManager, mock_connection: MagicMock) -> None:
        async with manager:
            await manager.add_connection(connection=mock_connection)

            removed = await manager.remove_connection(connection_id="conn-1")

            assert removed is mock_connection
            assert len(manager) == 0
            await asyncio.sleep(0)
            mock_connection.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_connection_missing(self, manager: ConnectionManager) -> None:
        async with manager:
            removed = await manager.remove_connection(connection_id="missing")

            assert removed is None

    @pytest.mark.asyncio
    async def test_remove_connection_no_lock(self, manager: ConnectionManager) -> None:
        assert await manager.remove_connection(connection_id="c1") is None

    def test_schedule_close_idempotency(self, manager: ConnectionManager, mock_connection: MagicMock) -> None:
        mock_connection.is_closed = True

        manager._schedule_close(connection=mock_connection)

        mock_connection.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_closing_tasks(
        self, manager: ConnectionManager, mock_connection: MagicMock
    ) -> None:
        close_event = asyncio.Event()

        async def delayed_close() -> None:
            await close_event.wait()

        mock_connection.close.side_effect = delayed_close

        async with manager:
            await manager.add_connection(connection=mock_connection)
            await manager.remove_connection(connection_id="conn-1")

            assert len(manager._closing_tasks) == 1

            shutdown_task = asyncio.create_task(manager.shutdown())
            await asyncio.sleep(0.01)

            assert not shutdown_task.done()

            close_event.set()
            await shutdown_task

        assert len(manager._closing_tasks) == 0



================================================
FILE: tests/unit/manager/test_session.py
================================================
"""Unit tests for the pywebtransport.manager.session module."""

from typing import cast
from unittest.mock import MagicMock, Mock

import pytest
from pytest_mock import MockerFixture

from pywebtransport.constants import ErrorCodes
from pywebtransport.events import EventEmitter
from pywebtransport.manager.session import SessionManager
from pywebtransport.session import WebTransportSession
from pywebtransport.types import SessionState


class FalsySession(Mock):

    def __bool__(self) -> bool:
        return False


class TestSessionManager:

    @pytest.fixture
    def manager(self) -> SessionManager:
        return SessionManager(max_sessions=10)

    @pytest.fixture
    def mock_session(self, mocker: MockerFixture) -> MagicMock:
        session = mocker.Mock(spec=WebTransportSession)
        session.session_id = 1
        session.state = SessionState.CONNECTED
        session.is_closed = False
        session.events = EventEmitter()
        session.close = mocker.AsyncMock()
        return cast(MagicMock, session)

    @pytest.mark.asyncio
    async def test_add_session(self, manager: SessionManager, mock_session: MagicMock) -> None:
        async with manager:
            session_id = await manager.add_session(session=mock_session)

            assert session_id == 1
            assert len(manager) == 1
            assert await manager.get_resource(resource_id=1) is mock_session

    @pytest.mark.asyncio
    async def test_close_resource_already_closed(self, manager: SessionManager, mock_session: MagicMock) -> None:
        mock_session.is_closed = True

        await manager._close_resource(resource=mock_session)

        mock_session.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_resource_open(self, manager: SessionManager, mock_session: MagicMock) -> None:
        mock_session.is_closed = False

        await manager._close_resource(resource=mock_session)

        mock_session.close.assert_awaited_once_with(error_code=ErrorCodes.NO_ERROR, reason="Session manager shutdown")

    def test_get_resource_id(self, manager: SessionManager, mock_session: MagicMock) -> None:
        assert manager._get_resource_id(resource=mock_session) == 1

    @pytest.mark.asyncio
    async def test_get_sessions_by_state(self, manager: SessionManager, mocker: MockerFixture) -> None:
        s1 = mocker.Mock(spec=WebTransportSession, session_id=1, events=EventEmitter())
        s1.state = SessionState.CONNECTED
        s1.is_closed = False
        s2 = mocker.Mock(spec=WebTransportSession, session_id=2, events=EventEmitter())
        s2.state = SessionState.CLOSING
        s2.is_closed = False
        s3 = mocker.Mock(spec=WebTransportSession, session_id=3, events=EventEmitter())
        s3.state = SessionState.CONNECTED
        s3.is_closed = False

        async with manager:
            await manager.add_session(session=s1)
            await manager.add_session(session=s2)
            await manager.add_session(session=s3)

            connected = await manager.get_sessions_by_state(state=SessionState.CONNECTED)
            assert len(connected) == 2
            assert s1 in connected
            assert s3 in connected

            closing = await manager.get_sessions_by_state(state=SessionState.CLOSING)
            assert len(closing) == 1
            assert s2 in closing

    @pytest.mark.asyncio
    async def test_get_sessions_by_state_no_lock(self, manager: SessionManager) -> None:
        assert await manager.get_sessions_by_state(state=SessionState.CONNECTED) == []

    @pytest.mark.asyncio
    async def test_get_stats_includes_states(self, manager: SessionManager, mocker: MockerFixture) -> None:
        s1 = mocker.Mock(spec=WebTransportSession, session_id=1, events=EventEmitter())
        s1.state = SessionState.CONNECTED
        s1.is_closed = False
        s2 = mocker.Mock(spec=WebTransportSession, session_id=2, events=EventEmitter())
        s2.state = SessionState.DRAINING
        s2.is_closed = False

        async with manager:
            await manager.add_session(session=s1)
            await manager.add_session(session=s2)

            stats = await manager.get_stats()

            assert stats["current_count"] == 2
            assert stats["states"]["connected"] == 1
            assert stats["states"]["draining"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_no_lock(self, manager: SessionManager) -> None:
        stats = await manager.get_stats()

        assert stats == {}

    def test_init(self, manager: SessionManager) -> None:
        assert len(manager) == 0

    @pytest.mark.asyncio
    async def test_remove_session(
        self, manager: SessionManager, mock_session: MagicMock, mocker: MockerFixture
    ) -> None:
        spy_off = mocker.spy(mock_session.events, "off")

        async with manager:
            await manager.add_session(session=mock_session)
            assert len(manager) == 1

            removed = await manager.remove_session(session_id=1)

            assert removed is mock_session
            assert len(manager) == 0
            stats = await manager.get_stats()
            assert stats["total_closed"] == 1
            spy_off.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_session_falsy(self, manager: SessionManager, mocker: MockerFixture) -> None:
        session = FalsySession(spec=WebTransportSession)
        session.session_id = 1
        session.events = EventEmitter()
        session.is_closed = False
        session.state = SessionState.CONNECTED

        async with manager:
            await manager.add_session(session=cast(WebTransportSession, session))

            removed = await manager.remove_session(session_id=1)

            assert removed is session
            stats = await manager.get_stats()
            assert stats["total_closed"] == 1

    @pytest.mark.asyncio
    async def test_remove_session_handler_error(
        self, manager: SessionManager, mock_session: MagicMock, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(mock_session.events, "off", side_effect=ValueError("Handler not found"))

        async with manager:
            await manager.add_session(session=mock_session)

            removed = await manager.remove_session(session_id=1)

            assert removed is mock_session
            assert len(manager) == 0

    @pytest.mark.asyncio
    async def test_remove_session_missing(self, manager: SessionManager) -> None:
        async with manager:
            removed = await manager.remove_session(session_id=999)

            assert removed is None

    @pytest.mark.asyncio
    async def test_remove_session_no_lock(self, manager: SessionManager) -> None:
        assert await manager.remove_session(session_id=1) is None



================================================
FILE: tests/unit/messaging/__init__.py
================================================
[Empty file]


================================================
FILE: tests/unit/messaging/test_datagram.py
================================================
"""Unit tests for the pywebtransport.messaging.datagram module."""

import struct
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_asyncio import fixture as asyncio_fixture

from pywebtransport import ConfigurationError, Event, SessionError, StructuredDatagramTransport, TimeoutError
from pywebtransport.exceptions import SerializationError
from pywebtransport.types import EventType


class TestStructuredDatagramTransport:

    @pytest.fixture
    def mock_serializer(self) -> Mock:
        serializer = Mock()
        serializer.serialize.side_effect = lambda obj: str(obj).encode("utf-8")
        serializer.deserialize.side_effect = lambda data, obj_type: int(data.tobytes().decode("utf-8"))
        return serializer

    @pytest.fixture
    def mock_session(self) -> Mock:
        session = Mock()
        session.is_closed = False
        session.session_id = "test_session_id"
        session.events = Mock()
        session.send_datagram = AsyncMock()
        return session

    @pytest.fixture
    def registry(self) -> dict[int, type[Any]]:
        return {1: int, 2: str}

    @asyncio_fixture
    async def transport(
        self, mock_session: Mock, mock_serializer: Mock, registry: dict[int, type[Any]]
    ) -> StructuredDatagramTransport:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)
        transport.initialize()
        return transport

    @pytest.mark.asyncio
    async def test_aenter_aexit(
        self, mock_session: Mock, mock_serializer: Mock, registry: dict[int, type[Any]]
    ) -> None:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)

        async with transport as t:
            assert t is transport
            assert t._is_initialized
            mock_session.events.on.assert_called_once()
            assert not t.is_closed

        assert transport.is_closed
        mock_session.events.off.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_behavior(self, mock_session: Mock, transport: StructuredDatagramTransport) -> None:
        await transport.close()

        assert transport.is_closed
        mock_session.events.off.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error", [KeyError("Handler key error"), ValueError("Handler not found")])
    async def test_close_handles_events_off_errors(
        self, mock_session: Mock, transport: StructuredDatagramTransport, error: Exception
    ) -> None:
        mock_session.events.off.side_effect = error

        await transport.close()

        assert transport.is_closed
        mock_session.events.off.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_garbage_collected_session(
        self, mock_session: Mock, transport: StructuredDatagramTransport
    ) -> None:
        with patch.object(transport, "_session", return_value=None):
            await transport.close()

        assert transport.is_closed
        mock_session.events.off.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_idempotency(self, mock_session: Mock, transport: StructuredDatagramTransport) -> None:
        await transport.close()
        await transport.close()

        mock_session.events.off.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_uninitialized_transport(
        self, mock_session: Mock, mock_serializer: Mock, registry: dict[int, type[Any]]
    ) -> None:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)

        await transport.close()

        assert transport.is_closed
        mock_session.events.off.assert_not_called()

    @pytest.mark.asyncio
    async def test_handler_delegates_to_internal_method(
        self, mock_session: Mock, mock_serializer: Mock, registry: dict[int, type[Any]]
    ) -> None:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)
        transport.initialize()
        handler = mock_session.events.on.call_args.kwargs["handler"]
        event = Event(type=EventType.DATAGRAM_RECEIVED, data={"data": b"dummy"})

        with patch.object(transport, "_on_datagram_received", new_callable=AsyncMock) as mock_method:
            await handler(event)
            mock_method.assert_awaited_once_with(event=event)

    @pytest.mark.asyncio
    async def test_handler_weakref_behavior(
        self, mock_session: Mock, mock_serializer: Mock, registry: dict[int, type[Any]]
    ) -> None:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)
        mock_weakref = Mock(return_value=None)

        with patch("weakref.ref", return_value=mock_weakref):
            transport.initialize()

        handler = mock_session.events.on.call_args.kwargs["handler"]
        event = Event(type=EventType.DATAGRAM_RECEIVED, data={"data": b"dummy"})

        with patch.object(transport, "_on_datagram_received", new_callable=AsyncMock) as mock_method:
            await handler(event)
            mock_method.assert_not_called()

    def test_init_raises_configuration_error_on_duplicate_types(
        self, mock_session: Mock, mock_serializer: Mock
    ) -> None:
        registry: dict[int, type[Any]] = {1: int, 2: int}

        with pytest.raises(ConfigurationError):
            StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)

    def test_initialize_garbage_collected_session_raises_error(
        self, mock_session: Mock, mock_serializer: Mock, registry: dict[int, type[Any]]
    ) -> None:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)

        with patch.object(transport, "_session", return_value=None):
            with pytest.raises(SessionError, match="parent session is already gone"):
                transport.initialize()

    def test_initialize_session_closed_raises_error(
        self, mock_session: Mock, mock_serializer: Mock, registry: dict[int, type[Any]]
    ) -> None:
        mock_session.is_closed = True
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)

        with pytest.raises(SessionError, match="parent session is closed"):
            transport.initialize()

    def test_initialize_success_and_idempotency(
        self, mock_session: Mock, transport: StructuredDatagramTransport
    ) -> None:
        transport.initialize()

        assert mock_session.events.on.call_count == 1
        call_args = mock_session.events.on.call_args
        assert call_args.kwargs["event_type"] == EventType.DATAGRAM_RECEIVED
        assert callable(call_args.kwargs["handler"])

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "session_state, transport_state, expected_closed",
        [("active", "open", False), ("active", "closed", True), ("closed", "open", True), ("collected", "open", True)],
    )
    async def test_is_closed_property(
        self,
        mock_session: Mock,
        transport: StructuredDatagramTransport,
        session_state: str,
        transport_state: str,
        expected_closed: bool,
    ) -> None:
        if transport_state == "closed":
            await transport.close()

        if session_state == "closed":
            mock_session.is_closed = True
        elif session_state == "collected":
            with patch.object(transport, "_session", return_value=None):
                assert transport.is_closed is expected_closed
                return

        assert transport.is_closed is expected_closed

    @pytest.mark.asyncio
    async def test_on_datagram_received_errors(
        self, transport: StructuredDatagramTransport, mock_serializer: Mock
    ) -> None:
        header = struct.pack("!H", 1)
        payload = b"123"
        event = Event(type=EventType.DATAGRAM_RECEIVED, data={"data": header + payload})
        mock_serializer.deserialize.side_effect = RuntimeError("Generic failure")

        with patch("pywebtransport.messaging.datagram.logger") as mock_logger:
            await transport._on_datagram_received(event=event)
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "event_data, closed_state, expect_process",
        [
            ({"data": struct.pack("!H", 1) + b"valid"}, False, True),
            ({"data": struct.pack("!H", 1) + b"valid"}, True, False),
            ("not a dict", False, False),
            ({}, False, False),
            ({"data": None}, False, False),
            ({"data": b"1"}, False, False),
        ],
    )
    async def test_on_datagram_received_ignored_cases(
        self,
        transport: StructuredDatagramTransport,
        mock_serializer: Mock,
        event_data: Any,
        closed_state: bool,
        expect_process: bool,
    ) -> None:
        if closed_state:
            await transport.close()

        event = Event(type=EventType.DATAGRAM_RECEIVED, data=event_data)
        await transport._on_datagram_received(event=event)

        if expect_process:
            mock_serializer.deserialize.assert_called()
        else:
            mock_serializer.deserialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_datagram_received_queue_full(
        self, mock_session: Mock, mock_serializer: Mock, registry: dict[int, type[Any]]
    ) -> None:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)
        transport.initialize(queue_size=1)
        header = struct.pack("!H", 1)
        payload = b"123"
        event = Event(type=EventType.DATAGRAM_RECEIVED, data={"data": header + payload})

        with patch("pywebtransport.messaging.datagram.logger") as mock_logger:
            await transport._on_datagram_received(event=event)
            await transport._on_datagram_received(event=event)
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_on_datagram_received_queue_full_session_collected(
        self, mock_session: Mock, mock_serializer: Mock, registry: dict[int, type[Any]]
    ) -> None:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)
        transport.initialize(queue_size=1)
        header = struct.pack("!H", 1)
        payload = b"123"
        event = Event(type=EventType.DATAGRAM_RECEIVED, data={"data": header + payload})

        with patch("pywebtransport.messaging.datagram.logger") as mock_logger:
            await transport._on_datagram_received(event=event)
            with patch.object(transport, "_session", return_value=None):
                await transport._on_datagram_received(event=event)

            assert mock_logger.warning.call_count == 1
            args, _ = mock_logger.warning.call_args
            assert "unknown" in args

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "header_val, payload, error_type", [(1, b"invalid", SerializationError), (999, b"123", SerializationError)]
    )
    async def test_receive_obj_drops_bad_datagrams(
        self,
        transport: StructuredDatagramTransport,
        mock_serializer: Mock,
        header_val: int,
        payload: bytes,
        error_type: type[Exception],
    ) -> None:
        if header_val == 999:
            pass
        else:
            mock_serializer.deserialize.side_effect = error_type("fail")

        header = struct.pack("!H", header_val)
        event = Event(type=EventType.DATAGRAM_RECEIVED, data={"data": header + payload})

        with patch("pywebtransport.messaging.datagram.logger") as mock_logger:
            await transport._on_datagram_received(event=event)
            mock_logger.warning.assert_called()

        with pytest.raises(TimeoutError):
            await transport.receive_obj(timeout=0.01)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario, expected_error, match",
        [
            ("uninitialized", SessionError, "not been initialized"),
            ("closed_transport", SessionError, "is closed"),
            ("poison_pill", SessionError, "closed while receiving"),
            ("timeout", TimeoutError, "Receive object timeout"),
        ],
    )
    async def test_receive_obj_errors(
        self,
        mock_session: Mock,
        mock_serializer: Mock,
        registry: dict[int, type[Any]],
        scenario: str,
        expected_error: type[Exception],
        match: str,
    ) -> None:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)

        if scenario != "uninitialized":
            transport.initialize()

        if scenario == "closed_transport":
            await transport.close()

        if scenario == "poison_pill":
            assert transport._incoming_obj_queue is not None
            transport._incoming_obj_queue.put_nowait(item=transport._sentinel)

        if scenario == "timeout":
            kwargs = {"timeout": 0.01}
        else:
            kwargs = {}

        with pytest.raises(expected_error, match=match):
            await transport.receive_obj(**kwargs)

    @pytest.mark.asyncio
    async def test_receive_obj_success(self, transport: StructuredDatagramTransport) -> None:
        header = struct.pack("!H", 1)
        payload = b"123"
        event = Event(type=EventType.DATAGRAM_RECEIVED, data={"data": header + payload})

        await transport._on_datagram_received(event=event)
        obj = await transport.receive_obj()

        assert obj == 123

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario, expected_error, match",
        [
            ("uninitialized", SessionError, "not been initialized"),
            ("session_closed", SessionError, "Session is closed"),
            ("session_collected", SessionError, "Session is closed"),
            ("unregistered_type", SerializationError, "not registered"),
        ],
    )
    async def test_send_obj_errors(
        self,
        mock_session: Mock,
        mock_serializer: Mock,
        registry: dict[int, type[Any]],
        scenario: str,
        expected_error: type[Exception],
        match: str,
    ) -> None:
        transport = StructuredDatagramTransport(session=mock_session, serializer=mock_serializer, registry=registry)

        if scenario != "uninitialized":
            transport.initialize()

        obj: Any = 123
        patcher = None

        if scenario == "session_closed":
            mock_session.is_closed = True
        elif scenario == "session_collected":
            patcher = patch.object(transport, "_session", return_value=None)
            patcher.start()
        elif scenario == "unregistered_type":
            obj = 1.23

        try:
            with pytest.raises(expected_error, match=match):
                await transport.send_obj(obj=obj)
        finally:
            if patcher:
                patcher.stop()

    @pytest.mark.asyncio
    async def test_send_obj_success(
        self, mock_session: Mock, mock_serializer: Mock, transport: StructuredDatagramTransport
    ) -> None:
        obj = 123
        expected_header = struct.pack("!H", 1)
        expected_payload = b"123"

        await transport.send_obj(obj=obj)

        mock_serializer.serialize.assert_called_once_with(obj=obj)
        mock_session.send_datagram.assert_awaited_once_with(data=[expected_header, expected_payload])



================================================
FILE: tests/unit/messaging/test_stream.py
================================================
"""Unit tests for the pywebtransport.messaging.stream module."""

import asyncio
import struct
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from pywebtransport import ConfigurationError, ErrorCodes, StreamError, StructuredStream, WebTransportStream
from pywebtransport.constants import DEFAULT_MAX_MESSAGE_SIZE
from pywebtransport.exceptions import SerializationError
from pywebtransport.types import Serializer


class MockMsgA:
    pass


class MockMsgB:
    pass


class TestStructuredStream:

    @pytest.fixture
    def mock_serializer(self, mocker: MockerFixture) -> MagicMock:
        return mocker.create_autospec(Serializer, spec_set=True, instance=True)

    @pytest.fixture
    def mock_stream(self, mocker: MockerFixture) -> AsyncMock:
        mock = mocker.create_autospec(WebTransportStream, spec_set=True, instance=True)
        mock.readexactly = AsyncMock()
        mock.write = AsyncMock()
        mock.close = AsyncMock()
        mock.stop_receiving = AsyncMock()
        return mock

    @pytest.fixture
    def registry(self) -> dict[int, type[Any]]:
        return {1: MockMsgA, 2: MockMsgB}

    @pytest.fixture
    def structured_stream(
        self, mock_stream: AsyncMock, mock_serializer: MagicMock, registry: dict[int, type[Any]]
    ) -> StructuredStream:
        return StructuredStream(
            stream=mock_stream, serializer=mock_serializer, registry=registry, max_message_size=DEFAULT_MAX_MESSAGE_SIZE
        )

    @pytest.mark.asyncio
    async def test_anext_raises_on_protocol_error(
        self, structured_stream: StructuredStream, mocker: MockerFixture
    ) -> None:
        error = StreamError(message="Protocol error", error_code=ErrorCodes.H3_MESSAGE_ERROR)
        mocker.patch.object(structured_stream, "receive_obj", side_effect=error)

        with pytest.raises(StreamError) as exc_info:
            await structured_stream.__anext__()
        assert exc_info.value is error

    @pytest.mark.asyncio
    async def test_anext_stops_on_clean_close(self, structured_stream: StructuredStream, mocker: MockerFixture) -> None:
        error = StreamError(message="Clean close", error_code=ErrorCodes.NO_ERROR)
        mocker.patch.object(structured_stream, "receive_obj", side_effect=error)

        with pytest.raises(StopAsyncIteration):
            await structured_stream.__anext__()

    @pytest.mark.asyncio
    async def test_async_iteration(self, structured_stream: StructuredStream, mocker: MockerFixture) -> None:
        obj1, obj2 = MockMsgA(), MockMsgB()
        receive_obj_mock = AsyncMock(
            side_effect=[obj1, obj2, StreamError(message="Done", error_code=ErrorCodes.NO_ERROR)]
        )
        mocker.patch.object(structured_stream, "receive_obj", new=receive_obj_mock)
        received_objs = []

        async for obj in structured_stream:
            received_objs.append(obj)

        assert received_objs == [obj1, obj2]
        assert receive_obj_mock.await_count == 3

    @pytest.mark.asyncio
    async def test_close_method(self, structured_stream: StructuredStream, mock_stream: AsyncMock) -> None:
        await structured_stream.close()

        mock_stream.close.assert_awaited_once()

    def test_init(
        self,
        structured_stream: StructuredStream,
        mock_stream: AsyncMock,
        mock_serializer: MagicMock,
        registry: dict[int, type[Any]],
    ) -> None:
        expected_class_to_id = {MockMsgA: 1, MockMsgB: 2}

        assert structured_stream._stream is mock_stream
        assert structured_stream._serializer is mock_serializer
        assert structured_stream._registry is registry
        assert structured_stream._class_to_id == expected_class_to_id
        assert structured_stream._max_message_size == DEFAULT_MAX_MESSAGE_SIZE
        assert isinstance(structured_stream._write_lock, asyncio.Lock)

    def test_init_with_duplicate_registry_types_raises_error(
        self, mock_stream: AsyncMock, mock_serializer: MagicMock
    ) -> None:
        faulty_registry = {1: MockMsgA, 2: MockMsgA}

        with pytest.raises(ConfigurationError, match="Types in the structured stream registry must be unique"):
            StructuredStream(
                stream=mock_stream, serializer=mock_serializer, registry=faulty_registry, max_message_size=1024
            )

    @pytest.mark.parametrize("closed_status", [True, False])
    def test_is_closed_property(
        self, structured_stream: StructuredStream, mock_stream: AsyncMock, closed_status: bool
    ) -> None:
        type(mock_stream).is_closed = closed_status

        assert structured_stream.is_closed is closed_status

    @pytest.mark.asyncio
    async def test_receive_obj_eof_clean(self, structured_stream: StructuredStream, mock_stream: AsyncMock) -> None:
        mock_stream.readexactly.side_effect = asyncio.IncompleteReadError(b"", 8)

        with pytest.raises(StreamError) as exc_info:
            await structured_stream.receive_obj()

        assert exc_info.value.error_code == ErrorCodes.NO_ERROR
        assert "Stream closed cleanly" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_receive_obj_exceeds_max_message_size_raises_error(
        self, mock_stream: AsyncMock, mock_serializer: MagicMock, registry: dict[int, type[Any]]
    ) -> None:
        stream = StructuredStream(
            stream=mock_stream, serializer=mock_serializer, registry=registry, max_message_size=100
        )
        type_id = 1
        large_payload_len = 101
        header = struct.pack("!HI", type_id, large_payload_len)
        mock_stream.readexactly.return_value = header

        with pytest.raises(SerializationError, match="exceeds the configured limit"):
            await stream.receive_obj()

        mock_stream.stop_receiving.assert_awaited_once_with(error_code=ErrorCodes.APPLICATION_ERROR)

    @pytest.mark.asyncio
    async def test_receive_obj_incomplete_header_raises_stream_error(
        self, structured_stream: StructuredStream, mock_stream: AsyncMock
    ) -> None:
        mock_stream.readexactly.side_effect = asyncio.IncompleteReadError(b"part", 8)

        with pytest.raises(StreamError) as exc_info:
            await structured_stream.receive_obj()

        assert exc_info.value.error_code == ErrorCodes.H3_MESSAGE_ERROR
        assert "waiting for message header" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_receive_obj_incomplete_payload_raises_stream_error(
        self, structured_stream: StructuredStream, mock_stream: AsyncMock
    ) -> None:
        type_id = 1
        payload_len = 100
        header = struct.pack("!HI", type_id, payload_len)
        mock_stream.readexactly.side_effect = [header, asyncio.IncompleteReadError(b"partial", payload_len)]

        with pytest.raises(StreamError) as exc_info:
            await structured_stream.receive_obj()

        assert exc_info.value.error_code == ErrorCodes.H3_MESSAGE_ERROR
        assert "reading payload" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_receive_obj_successful(
        self, structured_stream: StructuredStream, mock_stream: AsyncMock, mock_serializer: MagicMock
    ) -> None:
        type_id = 1
        message_class = MockMsgA
        payload = b"payload_data"
        header = struct.pack("!HI", type_id, len(payload))
        mock_stream.readexactly.side_effect = [header, payload]
        deserialized_obj = MockMsgA()
        mock_serializer.deserialize.return_value = deserialized_obj

        result = await structured_stream.receive_obj()

        assert mock_stream.readexactly.await_count == 2
        mock_stream.readexactly.assert_any_await(n=struct.calcsize("!HI"))
        mock_stream.readexactly.assert_any_await(n=len(payload))
        mock_serializer.deserialize.assert_called_once_with(data=payload, obj_type=message_class)
        assert result is deserialized_obj

    @pytest.mark.asyncio
    async def test_receive_obj_unknown_type_id_raises_error(
        self, structured_stream: StructuredStream, mock_stream: AsyncMock, mock_serializer: MagicMock
    ) -> None:
        unknown_type_id = 99
        header = struct.pack("!HI", unknown_type_id, 10)
        mock_stream.readexactly.return_value = header

        with pytest.raises(SerializationError, match=f"Received unknown message type ID: {unknown_type_id}"):
            await structured_stream.receive_obj()

        mock_stream.readexactly.assert_awaited_once()
        mock_serializer.deserialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_obj_concurrency_lock(
        self, structured_stream: StructuredStream, mock_stream: AsyncMock, mock_serializer: MagicMock
    ) -> None:
        obj = MockMsgA()
        mock_serializer.serialize.return_value = b"data"

        async def slow_write(data: bytes) -> None:
            await asyncio.sleep(0.01)

        mock_stream.write.side_effect = slow_write

        await asyncio.gather(structured_stream.send_obj(obj=obj), structured_stream.send_obj(obj=obj))

        assert mock_stream.write.await_count == 2

    @pytest.mark.asyncio
    async def test_send_obj_successful(
        self, structured_stream: StructuredStream, mock_stream: AsyncMock, mock_serializer: MagicMock
    ) -> None:
        obj_to_send = MockMsgB()
        type_id = 2
        serialized_payload = b"some_serialized_data"
        mock_serializer.serialize.return_value = serialized_payload

        await structured_stream.send_obj(obj=obj_to_send)

        mock_serializer.serialize.assert_called_once_with(obj=obj_to_send)
        header = struct.pack("!HI", type_id, len(serialized_payload))
        full_packet = header + serialized_payload

        mock_stream.write.assert_awaited_once_with(data=full_packet)

    @pytest.mark.asyncio
    async def test_send_obj_unregistered_raises_error(
        self, structured_stream: StructuredStream, mock_stream: AsyncMock, mock_serializer: MagicMock
    ) -> None:
        class UnregisteredMsg:
            pass

        with pytest.raises(SerializationError):
            await structured_stream.send_obj(obj=UnregisteredMsg())

        mock_serializer.serialize.assert_not_called()
        mock_stream.write.assert_not_awaited()

    def test_stream_id_property(self, structured_stream: StructuredStream, mock_stream: AsyncMock) -> None:
        expected_id = 123
        type(mock_stream).stream_id = expected_id

        assert structured_stream.stream_id == expected_id



================================================
FILE: tests/unit/serializer/__init__.py
================================================
[Empty file]


================================================
FILE: tests/unit/serializer/test_base.py
================================================
"""Unit tests for the pywebtransport.serializer._base module."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Union

import pytest

from pywebtransport.exceptions import SerializationError
from pywebtransport.serializer._base import BaseDataclassSerializer


@dataclass(kw_only=True)
class SimpleDataclass:
    value_int: int
    value_str: str


@dataclass(kw_only=True)
class ComplexDataclass:
    simple: SimpleDataclass
    items: list[int]
    mapping: dict[str, SimpleDataclass]
    optional_value: Any = None
    defaults: str = "default"


@dataclass(kw_only=True)
class DataclassWithMissingField:
    required: str
    optional_with_default: int = 123


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Mode(Enum):
    FAST = "fast"
    SLOW = "slow"


class CustomType:
    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CustomType):
            return NotImplemented
        return self.value == other.value


class FailingType:
    def __init__(self, value: Any) -> None:
        raise ValueError("fail")


class IntSubclass(int):
    pass


class TestBaseDataclassSerializer:

    @pytest.fixture
    def serializer(self) -> BaseDataclassSerializer:
        return BaseDataclassSerializer()

    def test_convert_callable_failure_fallback(self, serializer: BaseDataclassSerializer) -> None:
        data = "test"
        result = serializer.convert_to_type(data=data, target_type=FailingType)
        assert result == "test"

    def test_convert_custom_callable(self, serializer: BaseDataclassSerializer) -> None:
        result = serializer.convert_to_type(data="test", target_type=CustomType)
        assert isinstance(result, CustomType)
        assert result.value == "test"

    def test_convert_ignores_extra_fields(self, serializer: BaseDataclassSerializer) -> None:
        data = {"value_int": 1, "value_str": "text", "extra_field": "ignore"}
        result = serializer.convert_to_type(data=data, target_type=SimpleDataclass)
        assert isinstance(result, SimpleDataclass)
        assert not hasattr(result, "extra_field")

    def test_convert_to_complex_dataclass(self, serializer: BaseDataclassSerializer) -> None:
        data = {
            "simple": {"value_int": 1, "value_str": "nested"},
            "items": ["2", "3", "4"],
            "mapping": {
                "first": {"value_int": 100, "value_str": "a"},
                "second": {"value_int": 200, "value_str": "b"},
            },
            "optional_value": "provided",
        }
        result = serializer.convert_to_type(data=data, target_type=ComplexDataclass)
        assert isinstance(result, ComplexDataclass)
        assert isinstance(result.simple, SimpleDataclass)
        assert result.simple.value_int == 1
        assert result.items == [2, 3, 4]
        assert isinstance(result.mapping["first"], SimpleDataclass)
        assert result.mapping["second"].value_int == 200
        assert result.optional_value == "provided"
        assert result.defaults == "default"

    def test_convert_to_simple_dataclass(self, serializer: BaseDataclassSerializer) -> None:
        data = {"value_int": 10, "value_str": "hello"}
        result = serializer.convert_to_type(data=data, target_type=SimpleDataclass)
        assert isinstance(result, SimpleDataclass)
        assert result.value_int == 10
        assert result.value_str == "hello"

    @pytest.mark.parametrize(
        "data, target_type, expected",
        [
            (None, int, None),
            (123, Any, 123),
            ([1], Any, [1]),
            ("42", int, 42),
            (42, str, "42"),
            ("not-an-int", int, "not-an-int"),
            ([1, "a"], list, [1, "a"]),
            ([1, "a"], tuple, (1, "a")),
            ([1, "a", 1], set, {1, "a"}),
            ({"k": "v"}, dict, {"k": "v"}),
            (123, list, 123),
            (123, tuple, 123),
            (123, set, 123),
            (123, dict, 123),
            (["1", "2"], list[int], [1, 2]),
            (("1",), tuple[int], (1,)),
            (["1", "2", "1"], set[int], {1, 2}),
            ({"key": "123"}, dict[str, int], {"key": 123}),
            ({"1": "value"}, dict[int, str], {1: "value"}),
            (
                [{"value_int": "1", "value_str": "a"}],
                list[SimpleDataclass],
                [SimpleDataclass(value_int=1, value_str="a")],
            ),
            (None, int | None, None),
            (None, int | str, None),
            (10, int | str, 10),
            ("hello", int | str, "hello"),
            ("1.5", float | int, 1.5),
            ("123", int | float, 123),
            ("123", Union[int, str], "123"),
            ("not-num", int | float, "not-num"),
        ],
    )
    def test_convert_to_type_various(
        self, serializer: BaseDataclassSerializer, data: Any, target_type: Any, expected: Any
    ) -> None:
        result = serializer.convert_to_type(data=data, target_type=target_type)
        assert result == expected

    def test_enum_conversion_failure(self, serializer: BaseDataclassSerializer) -> None:
        with pytest.raises(SerializationError, match="Invalid value 'invalid' for enum Status"):
            serializer.convert_to_type(data="invalid", target_type=Status)

    def test_enum_conversion_success(self, serializer: BaseDataclassSerializer) -> None:
        result = serializer.convert_to_type(data="active", target_type=Status)
        assert result == Status.ACTIVE

    def test_from_dict_recursion_limit(self, serializer: BaseDataclassSerializer) -> None:
        with pytest.raises(SerializationError, match="Maximum recursion depth exceeded"):
            serializer.from_dict_to_dataclass(data={}, cls=SimpleDataclass, depth=65)

    def test_from_dict_to_dataclass_raises_serialization_error(self, serializer: BaseDataclassSerializer) -> None:
        data = {"optional_with_default": 456}
        with pytest.raises(SerializationError) as exc_info:
            serializer.from_dict_to_dataclass(data=data, cls=DataclassWithMissingField, depth=0)
        assert "Failed to unpack dictionary" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, TypeError)

    def test_non_type_target_passthrough(self, serializer: BaseDataclassSerializer) -> None:
        result_str = serializer.convert_to_type(data="data", target_type="not-a-type-instance")
        result_int = serializer.convert_to_type(data=123, target_type=456)
        assert result_str == "data"
        assert result_int == 123

    def test_recursion_limit_exceeded(self, serializer: BaseDataclassSerializer) -> None:
        data = {"value_int": 1, "value_str": "text"}
        with pytest.raises(SerializationError, match="Maximum recursion depth exceeded"):
            serializer.convert_to_type(data=data, target_type=SimpleDataclass, depth=65)

    def test_regular_class_passthrough(self, serializer: BaseDataclassSerializer) -> None:
        data = 42
        result = serializer.convert_to_type(data=data, target_type=IntSubclass)
        assert isinstance(result, IntSubclass)
        assert result == 42

    def test_union_conversion_with_enum_retry(self, serializer: BaseDataclassSerializer) -> None:
        result = serializer.convert_to_type(data="123", target_type=Union[Status, int])
        assert result == 123

    def test_union_fallthrough_all_failures(self, serializer: BaseDataclassSerializer) -> None:
        data = "invalid"
        result = serializer.convert_to_type(data=data, target_type=Union[Status, Mode])
        assert result == "invalid"



================================================
FILE: tests/unit/serializer/test_json.py
================================================
"""Unit tests for the pywebtransport.serializer.json module."""

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import pytest

from pywebtransport.exceptions import SerializationError
from pywebtransport.serializer import JSONSerializer


@dataclass(kw_only=True)
class BinaryData:
    content: bytes


class NonSerializable:
    pass


@dataclass(kw_only=True)
class SimpleData:
    id: int
    name: str


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class TestJSONSerializer:

    @pytest.fixture
    def serializer(self) -> JSONSerializer:
        return JSONSerializer()

    def test_deserialize_base64_bytes(self, serializer: JSONSerializer) -> None:
        raw = b"hello world"
        encoded = base64.b64encode(raw).decode("ascii")
        json_data = f'{{"content": "{encoded}"}}'.encode("utf-8")

        result = serializer.deserialize(data=json_data, obj_type=BinaryData)

        assert isinstance(result, BinaryData)
        assert result.content == raw

    def test_deserialize_bytearray(self, serializer: JSONSerializer) -> None:
        raw = b"bytearray content"
        encoded = base64.b64encode(raw).decode("ascii")
        json_data = f'"{encoded}"'.encode("utf-8")

        result = serializer.deserialize(data=json_data, obj_type=bytearray)

        assert isinstance(result, bytearray)
        assert result == raw

    def test_deserialize_invalid_base64_fallback(self, serializer: JSONSerializer) -> None:
        data = b'"invalid-base64!"'

        result = serializer.deserialize(data=data, obj_type=bytes)

        assert result == "invalid-base64!"

    @pytest.mark.parametrize("invalid_data", [b"{'id': 1, 'name': 'test'}", b'{"id": 1, "name": "test"', b"not json"])
    def test_deserialize_invalid_json_raises_error(self, serializer: JSONSerializer, invalid_data: bytes) -> None:
        with pytest.raises(SerializationError, match="Data is not valid JSON"):
            serializer.deserialize(data=invalid_data)

    def test_deserialize_memoryview_input(self, serializer: JSONSerializer) -> None:
        data = b'{"id": 1, "name": "test"}'
        mv = memoryview(data)

        result = serializer.deserialize(data=mv, obj_type=SimpleData)

        assert result == SimpleData(id=1, name="test")

    def test_deserialize_to_dataclass(self, serializer: JSONSerializer) -> None:
        data = b'{"id": 1, "name": "test"}'

        result = serializer.deserialize(data=data, obj_type=SimpleData)

        assert result == SimpleData(id=1, name="test")

    def test_deserialize_to_dataclass_with_type_conversion(self, serializer: JSONSerializer) -> None:
        data = b'{"id": "1", "name": 123}'

        result = serializer.deserialize(data=data, obj_type=SimpleData)

        assert result == SimpleData(id=1, name="123")

    def test_deserialize_to_dict(self, serializer: JSONSerializer) -> None:
        data = b'{"id": 1, "name": "test"}'

        result = serializer.deserialize(data=data)

        assert result == {"id": 1, "name": "test"}

    def test_deserialize_type_mismatch_raises_error(self, serializer: JSONSerializer) -> None:
        data = b'{"name": "test"}'

        with pytest.raises(SerializationError, match="Failed to unpack"):
            serializer.deserialize(data=data, obj_type=SimpleData)

    def test_init_with_dump_kwargs(self) -> None:
        serializer = JSONSerializer(dump_kwargs={"indent": 2, "sort_keys": True})
        instance = SimpleData(id=1, name="test")
        expected = b'{\n  "id": 1,\n  "name": "test"\n}'

        result = serializer.serialize(obj=instance)

        assert result == expected

    def test_init_with_load_kwargs(self) -> None:
        serializer = JSONSerializer(load_kwargs={"parse_float": str})
        data = b'{"value": 1.5}'

        result = serializer.deserialize(data=data)

        assert result["value"] == "1.5"

    def test_serialize_custom_default_handler(self) -> None:
        def custom_default(o: Any) -> Any:
            if isinstance(o, complex):
                return f"complex({o.real}, {o.imag})"
            raise TypeError(f"Unknown type {type(o)}")

        serializer = JSONSerializer(dump_kwargs={"default": custom_default})
        data = complex(1, 2)
        expected = b'"complex(1.0, 2.0)"'

        result = serializer.serialize(obj=data)

        assert result == expected

    def test_serialize_dataclass(self, serializer: JSONSerializer) -> None:
        instance = SimpleData(id=1, name="test")
        expected = b'{"id": 1, "name": "test"}'

        result = serializer.serialize(obj=instance)

        assert result == expected

    def test_serialize_dict(self, serializer: JSONSerializer) -> None:
        data = {"key": "value", "items": [1, True, None]}
        expected = b'{"key": "value", "items": [1, true, null]}'

        result = serializer.serialize(obj=data)

        assert result == expected

    def test_serialize_extended_types(self, serializer: JSONSerializer) -> None:
        test_uuid = uuid.uuid4()
        test_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        data = {
            "bytes": b"test",
            "uuid": test_uuid,
            "enum": Status.ACTIVE,
            "set": {1, 2},
            "datetime": test_time,
        }

        json_bytes = serializer.serialize(obj=data)
        result = serializer.deserialize(data=json_bytes)

        assert result["bytes"] == base64.b64encode(b"test").decode("ascii")
        assert result["uuid"] == str(test_uuid)
        assert result["enum"] == "active"
        assert set(result["set"]) == {1, 2}
        assert result["datetime"] == test_time.isoformat()

    def test_serialize_unsupported_type_raises_error(self, serializer: JSONSerializer) -> None:
        with pytest.raises(SerializationError) as exc_info:
            serializer.serialize(obj=NonSerializable())

        assert "is not JSON serializable" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, TypeError)



================================================
FILE: tests/unit/serializer/test_msgpack.py
================================================
"""Unit tests for the pywebtransport.serializer.msgpack module."""

import importlib
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import pytest

from pywebtransport.exceptions import ConfigurationError, SerializationError

try:
    import msgpack
except ImportError:
    msgpack = None


class NonSerializable:
    pass


@dataclass(kw_only=True)
class SimpleData:
    id: int
    name: str


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


def test_module_import_handles_missing_msgpack() -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "msgpack", None)
        if "pywebtransport.serializer.msgpack" in sys.modules:
            del sys.modules["pywebtransport.serializer.msgpack"]

        import pywebtransport.serializer.msgpack

        assert getattr(pywebtransport.serializer.msgpack, "msgpack") is None

    if "pywebtransport.serializer.msgpack" in sys.modules:
        del sys.modules["pywebtransport.serializer.msgpack"]
    importlib.import_module("pywebtransport.serializer.msgpack")


@pytest.mark.skipif(msgpack is None, reason="msgpack library not installed")
class TestMsgPackSerializer:

    @pytest.fixture
    def serializer(self) -> Any:
        from pywebtransport.serializer.msgpack import MsgPackSerializer

        return MsgPackSerializer()

    def test_deserialize_invalid_data_raises_error(self, serializer: Any) -> None:
        with pytest.raises(SerializationError, match="Data is not valid MsgPack"):
            serializer.deserialize(data=b"\xc1")

    def test_deserialize_memoryview_input(self, serializer: Any) -> None:
        data = msgpack.packb({"id": 1, "name": "test"})
        mv = memoryview(data)

        result = serializer.deserialize(data=mv, obj_type=SimpleData)

        assert result == SimpleData(id=1, name="test")

    def test_deserialize_to_dataclass(self, serializer: Any) -> None:
        data = msgpack.packb({"id": 1, "name": "test"})

        result = serializer.deserialize(data=data, obj_type=SimpleData)

        assert result == SimpleData(id=1, name="test")

    def test_deserialize_to_dict(self, serializer: Any) -> None:
        data = msgpack.packb({"id": 1, "name": "test"})

        result = serializer.deserialize(data=data)

        assert result == {"id": 1, "name": "test"}

    def test_deserialize_type_mismatch_raises_error(self, serializer: Any) -> None:
        data = msgpack.packb({"name": "test"})

        with pytest.raises(SerializationError, match="Failed to unpack"):
            serializer.deserialize(data=data, obj_type=SimpleData)

    def test_deserialize_with_unpack_kwargs(self) -> None:
        from pywebtransport.serializer.msgpack import MsgPackSerializer

        serializer = MsgPackSerializer(unpack_kwargs={"use_list": False})
        data = msgpack.packb([1, 2, 3])

        result = serializer.deserialize(data=data)

        assert isinstance(result, tuple)
        assert result == (1, 2, 3)

    def test_init_raises_configuration_error_if_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("pywebtransport.serializer.msgpack.msgpack", None)
        from pywebtransport.serializer.msgpack import MsgPackSerializer

        with pytest.raises(ConfigurationError, match="library is required"):
            MsgPackSerializer()

    def test_serialize_custom_default_handler(self) -> None:
        def custom_default(o: Any) -> Any:
            if isinstance(o, complex):
                return {"real": o.real, "imag": o.imag}
            raise TypeError(f"Unknown type {type(o)}")

        from pywebtransport.serializer.msgpack import MsgPackSerializer

        serializer = MsgPackSerializer(pack_kwargs={"default": custom_default})
        data = complex(1, 2)

        result = serializer.serialize(obj=data)
        unpacked = serializer.deserialize(data=result)

        assert unpacked == {"real": 1.0, "imag": 2.0}

    def test_serialize_dataclass(self, serializer: Any) -> None:
        instance = SimpleData(id=1, name="test")

        result = serializer.serialize(obj=instance)
        unpacked = msgpack.unpackb(result)

        assert unpacked == {"id": 1, "name": "test"}

    def test_serialize_dict(self, serializer: Any) -> None:
        data = {"key": "value", "items": [1, True, None]}

        result = serializer.serialize(obj=data)
        unpacked = msgpack.unpackb(result)

        assert unpacked == data

    def test_serialize_extended_types(self, serializer: Any) -> None:
        test_uuid = uuid.uuid4()
        test_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        data = {
            "uuid": test_uuid,
            "enum": Status.ACTIVE,
            "set": {1, 2},
            "frozenset": frozenset([3, 4]),
            "datetime": test_time,
        }

        packed = serializer.serialize(obj=data)
        result = serializer.deserialize(data=packed)

        assert result["uuid"] == str(test_uuid)
        assert result["enum"] == "active"
        assert set(result["set"]) == {1, 2}
        assert set(result["frozenset"]) == {3, 4}
        assert result["datetime"] == test_time.isoformat()

    def test_serialize_unsupported_type_raises_error(self, serializer: Any) -> None:
        with pytest.raises(SerializationError) as exc_info:
            serializer.serialize(obj=NonSerializable())

        assert "is not MsgPack serializable" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, TypeError)

    def test_serialize_with_pack_kwargs(self) -> None:
        from pywebtransport.serializer.msgpack import MsgPackSerializer

        serializer = MsgPackSerializer(pack_kwargs={"use_single_float": True})
        data = 1.5

        result = serializer.serialize(obj=data)

        assert isinstance(result, bytes)



================================================
FILE: tests/unit/serializer/test_protobuf.py
================================================
"""Unit tests for the pywebtransport.serializer.protobuf module."""

import importlib
import sys
from typing import Any

import pytest

from pywebtransport.exceptions import ConfigurationError, SerializationError

try:
    from google.protobuf.message import DecodeError, Message
except ImportError:
    Message = None
    DecodeError = None


class MockBaseMessage:
    pass


class MockProtoMessage(MockBaseMessage):
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    def SerializeToString(self) -> bytes:
        if hasattr(self, "_raise_on_serialize"):
            raise RuntimeError("Serialization failed")
        return b"serialized_data"

    def ParseFromString(self, serialized: bytes) -> None:
        if serialized == b"invalid_data":
            raise RuntimeError("Decode failed")
        self.id = 1
        self.name = "parsed"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MockProtoMessage):
            return NotImplemented
        return self.__dict__ == other.__dict__


class NotAMessage:
    pass


def test_environment_missing_dependency() -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "google.protobuf.message", None)
        if "pywebtransport.serializer.protobuf" in sys.modules:
            del sys.modules["pywebtransport.serializer.protobuf"]

        import pywebtransport.serializer.protobuf

        assert getattr(pywebtransport.serializer.protobuf, "Message") is None

    if "pywebtransport.serializer.protobuf" in sys.modules:
        del sys.modules["pywebtransport.serializer.protobuf"]
    importlib.import_module("pywebtransport.serializer.protobuf")


class TestProtobufSerializer:

    @pytest.fixture(autouse=True)
    def setup_dependencies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("pywebtransport.serializer.protobuf.Message", MockBaseMessage)
        monkeypatch.setattr("pywebtransport.serializer.protobuf.DecodeError", RuntimeError)

    @pytest.fixture
    def serializer(self) -> Any:
        from pywebtransport.serializer.protobuf import ProtobufSerializer

        return ProtobufSerializer()

    def test_deserialize_invalid_data_raises_error(self, serializer: Any) -> None:
        data = b"invalid_data"

        with pytest.raises(SerializationError, match="Failed to deserialize data"):
            serializer.deserialize(data=data, obj_type=MockProtoMessage)

    def test_deserialize_invalid_obj_type_raises_error(self, serializer: Any) -> None:
        with pytest.raises(SerializationError, match="is not a valid Protobuf Message"):
            serializer.deserialize(data=b"data", obj_type=NotAMessage)

    def test_deserialize_memoryview_input(self, serializer: Any) -> None:
        data = b"valid_data"
        mv = memoryview(data)

        result = serializer.deserialize(data=mv, obj_type=MockProtoMessage)

        assert result == MockProtoMessage(id=1, name="parsed")

    def test_deserialize_requires_obj_type(self, serializer: Any) -> None:
        with pytest.raises(SerializationError, match="requires a specific 'obj_type'"):
            serializer.deserialize(data=b"data")

    def test_deserialize_success(self, serializer: Any) -> None:
        data = b"valid_data"

        result = serializer.deserialize(data=data, obj_type=MockProtoMessage)

        assert isinstance(result, MockProtoMessage)
        assert result.id == 1
        assert result.name == "parsed"

    def test_init_raises_configuration_error_if_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("pywebtransport.serializer.protobuf.Message", None)
        from pywebtransport.serializer.protobuf import ProtobufSerializer

        with pytest.raises(ConfigurationError, match="library is required"):
            ProtobufSerializer()

    def test_serialize_internal_failure_raises_error(self, serializer: Any) -> None:
        message = MockProtoMessage(_raise_on_serialize=True)

        with pytest.raises(SerializationError, match="Failed to serialize"):
            serializer.serialize(obj=message)

    def test_serialize_success(self, serializer: Any) -> None:
        message = MockProtoMessage(id=1, name="test")

        result = serializer.serialize(obj=message)

        assert result == b"serialized_data"

    def test_serialize_wrong_object_type_raises_error(self, serializer: Any) -> None:
        message = NotAMessage()

        with pytest.raises(SerializationError, match="is not a valid Protobuf Message"):
            serializer.serialize(obj=message)



================================================
FILE: tests/unit/server/__init__.py
================================================
[Empty file]


================================================
FILE: tests/unit/server/test_app.py
================================================
"""Unit tests for the pywebtransport.server.app module."""

import asyncio
import http
from typing import Any, cast

import pytest
from pytest_mock import MockerFixture

from pywebtransport import ConnectionError, Event, ServerApp, ServerConfig, ServerError, WebTransportSession
from pywebtransport._protocol.events import UserAcceptSession, UserCloseSession, UserRejectSession
from pywebtransport.connection import WebTransportConnection
from pywebtransport.server import MiddlewareProtocol, MiddlewareRejected, StatefulMiddlewareProtocol, WebTransportServer
from pywebtransport.types import EventType


class TestServerApp:

    @pytest.fixture
    def app(self, mock_server: Any, mock_router: Any, mock_middleware_manager: Any) -> ServerApp:
        return ServerApp()

    @pytest.fixture
    def mock_connection(self, mocker: MockerFixture, mock_future: asyncio.Future[Any]) -> Any:
        conn = mocker.create_autospec(WebTransportConnection, instance=True)
        conn.is_connected = True
        conn.connection_id = "conn_1"

        mock_protocol = mocker.Mock()
        mock_protocol.create_request.return_value = (123, mock_future)
        mock_protocol.send_event = mocker.Mock()
        conn._protocol = mock_protocol

        return conn

    @pytest.fixture
    def mock_future(self) -> asyncio.Future[Any]:
        fut: asyncio.Future[Any] = asyncio.Future()
        fut.set_result(None)
        return fut

    @pytest.fixture
    def mock_middleware_manager(self, mocker: MockerFixture) -> Any:
        manager_instance = mocker.MagicMock()
        manager_instance.process_request = mocker.AsyncMock(return_value=None)
        mocker.patch("pywebtransport.server.app.MiddlewareManager", return_value=manager_instance)
        return manager_instance

    @pytest.fixture
    def mock_router(self, mocker: MockerFixture) -> Any:
        router_instance = mocker.MagicMock()
        mocker.patch("pywebtransport.server.app.RequestRouter", return_value=router_instance)
        return router_instance

    @pytest.fixture
    def mock_server(self, mocker: MockerFixture) -> Any:
        server_instance = mocker.create_autospec(WebTransportServer, instance=True)
        server_instance.session_manager = mocker.MagicMock()
        server_instance.session_manager.add_session = mocker.AsyncMock()
        server_instance.config = ServerConfig(bind_host="0.0.0.0", bind_port=4433)
        server_instance.close = mocker.AsyncMock()
        mocker.patch("pywebtransport.server.app.WebTransportServer", return_value=server_instance)
        return server_instance

    @pytest.fixture
    def mock_session(self, mocker: MockerFixture, mock_connection: Any) -> Any:
        session_instance = mocker.MagicMock(name="WebTransportSession")
        session_instance.__class__ = WebTransportSession

        session_instance.session_id = 100
        session_instance.path = "/"
        session_instance.is_closed = False
        session_instance.close = mocker.AsyncMock()

        session_instance._connection = mocker.Mock(return_value=mock_connection)
        return session_instance

    @pytest.mark.asyncio
    async def test_aexit_cleanup_without_startup(self, app: ServerApp, mock_server: Any) -> None:
        app._tg = None
        await app.__aexit__(None, None, None)

        mock_server.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, app: ServerApp, mock_server: Any, mocker: MockerFixture) -> None:
        mock_startup = mocker.patch.object(app, "startup", new_callable=mocker.AsyncMock)
        mock_shutdown = mocker.patch.object(app, "shutdown", new_callable=mocker.AsyncMock)

        async with app as a:
            assert a is app
            assert app._tg is not None
            mock_server.__aenter__.assert_awaited_once()
            mock_startup.assert_awaited_once()

        mock_shutdown.assert_awaited_once()
        mock_server.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_with_exception(
        self, app: ServerApp, mock_server: Any, mocker: MockerFixture
    ) -> None:
        mock_startup = mocker.patch.object(app, "startup", new_callable=mocker.AsyncMock)
        mock_shutdown = mocker.patch.object(app, "shutdown", new_callable=mocker.AsyncMock)

        with pytest.raises((ValueError, ExceptionGroup)):
            async with app:
                mock_server.__aenter__.assert_awaited_once()
                mock_startup.assert_awaited_once()
                raise ValueError("Test error")

        mock_shutdown.assert_awaited_once()
        mock_server.close.assert_awaited_once()

    def test_decorators(self, app: ServerApp, mock_router: Any, mock_middleware_manager: Any) -> None:
        @app.route(path="/test")
        async def handler1(session: WebTransportSession) -> None:
            pass

        @app.pattern_route(pattern="/other/.*")
        async def handler2(session: WebTransportSession) -> None:
            pass

        mock_router.add_route.assert_called_once_with(path="/test", handler=handler1)
        mock_router.add_pattern_route.assert_called_once_with(pattern="/other/.*", handler=handler2)

        async def middleware(session: WebTransportSession) -> None:
            pass

        middleware_proto = cast(MiddlewareProtocol, middleware)
        registered_middleware = app.middleware(middleware_proto)

        assert registered_middleware is middleware_proto
        mock_middleware_manager.add_middleware.assert_called_once_with(middleware=middleware_proto)

        @app.on_startup
        def startup_handler() -> None:
            pass

        @app.on_shutdown
        def shutdown_handler() -> None:
            pass

        assert startup_handler in app._startup_handlers
        assert shutdown_handler in app._shutdown_handlers

    @pytest.mark.asyncio
    async def test_dispatch_to_handler_accept_exception(
        self, app: ServerApp, mock_session: Any, mock_router: Any, mock_connection: Any, mocker: MockerFixture
    ) -> None:
        mock_handler = mocker.AsyncMock()
        mock_router.route_request.return_value = (mock_handler, {})

        error_future: asyncio.Future[None] = asyncio.Future()
        error_future.set_exception(ValueError("Accept failed"))
        mock_connection._protocol.create_request.return_value = (1, error_future)

        mock_logger_error = mocker.patch("pywebtransport.server.app.logger.error")

        await app._dispatch_to_handler(session=mock_session)

        mock_logger_error.assert_called()
        assert not app._handler_tasks

    @pytest.mark.asyncio
    async def test_dispatch_to_handler_connection_missing(
        self, app: ServerApp, mock_session: Any, mock_router: Any, mocker: MockerFixture
    ) -> None:
        mock_session._connection.return_value = None
        mock_logger_error = mocker.patch("pywebtransport.server.app.logger.error")

        await app._dispatch_to_handler(session=mock_session)

        mock_logger_error.assert_called_with("Cannot dispatch handler, connection is missing.")
        mock_router.route_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_to_handler_no_route(
        self,
        app: ServerApp,
        mock_session: Any,
        mock_router: Any,
        mock_connection: Any,
        mock_future: asyncio.Future[Any],
    ) -> None:
        mock_router.route_request.return_value = None
        req_id = 99
        mock_connection._protocol.create_request.return_value = (req_id, mock_future)

        await app._dispatch_to_handler(session=mock_session)

        mock_connection._protocol.create_request.assert_called_once()
        mock_connection._protocol.send_event.assert_called_once()

        call_args = mock_connection._protocol.send_event.call_args
        event = call_args.kwargs["event"]
        assert isinstance(event, UserRejectSession)
        assert event.request_id == req_id
        assert event.session_id == mock_session.session_id
        assert event.status_code == http.HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_dispatch_to_handler_no_task_group(
        self, app: ServerApp, mock_session: Any, mock_router: Any, mock_connection: Any, mocker: MockerFixture
    ) -> None:
        mock_handler = mocker.AsyncMock()
        mock_router.route_request.return_value = (mock_handler, {})
        mock_logger_error = mocker.patch("pywebtransport.server.app.logger.error")
        app._tg = None

        await app._dispatch_to_handler(session=mock_session)

        mock_logger_error.assert_called_with("TaskGroup not initialized. Handler cannot be dispatched.")

    @pytest.mark.asyncio
    async def test_dispatch_to_handler_success(
        self,
        app: ServerApp,
        mock_session: Any,
        mock_router: Any,
        mock_connection: Any,
        mocker: MockerFixture,
        mock_future: asyncio.Future[Any],
    ) -> None:
        mock_handler = mocker.AsyncMock()
        mock_router.route_request.return_value = (mock_handler, {"id": "123"})

        req_id = 55
        mock_connection._protocol.create_request.return_value = (req_id, mock_future)

        mock_tg = mocker.Mock()
        mock_task = mocker.Mock(spec=asyncio.Task)
        mock_tg.create_task.return_value = mock_task
        app._tg = mock_tg

        await app._dispatch_to_handler(session=mock_session)

        mock_connection._protocol.create_request.assert_called_once()
        mock_connection._protocol.send_event.assert_called_once()

        call_args = mock_connection._protocol.send_event.call_args
        event = call_args.kwargs["event"]
        assert isinstance(event, UserAcceptSession)
        assert event.request_id == req_id
        assert event.session_id == mock_session.session_id

        mock_tg.create_task.assert_called_once()
        assert mock_task in app._handler_tasks

        coro = mock_tg.create_task.call_args.kwargs["coro"]
        coro.close()

    @pytest.mark.asyncio
    async def test_get_session_from_event_disconnected(
        self, app: ServerApp, mocker: MockerFixture, mock_connection: Any, mock_session: Any
    ) -> None:
        mock_connection.is_connected = False
        mock_logger_warning = mocker.patch("pywebtransport.server.app.logger.warning")

        event = Event(
            type=EventType.SESSION_REQUEST,
            data={"connection": mock_connection, "session": mock_session, "session_id": 100},
        )

        session = await app._get_session_from_event(event=event)

        assert session is None
        mock_logger_warning.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data_override, description",
        [
            ({"session": "not_a_session"}, "invalid_session_type"),
            ({"connection": "not_a_connection"}, "invalid_connection_type"),
            ({"session": None}, "missing_session_obj"),
            ({"connection": None}, "missing_connection"),
        ],
    )
    async def test_get_session_from_event_failures(
        self, app: ServerApp, mocker: MockerFixture, data_override: dict[str, Any], description: str
    ) -> None:
        mock_conn = mocker.create_autospec(WebTransportConnection, instance=True)
        mock_session = mocker.MagicMock(name="WebTransportSession")
        mock_session.__class__ = WebTransportSession
        mock_session._connection.return_value = mock_conn

        base_data = {"connection": mock_conn, "session": mock_session, "session_id": 100}
        base_data.update(data_override)

        event = Event(type=EventType.SESSION_REQUEST, data=base_data)

        session = await app._get_session_from_event(event=event)

        assert session is None

    @pytest.mark.asyncio
    async def test_get_session_from_event_invalid_data_type(self, app: ServerApp, mocker: MockerFixture) -> None:
        mock_logger_warning = mocker.patch("pywebtransport.server.app.logger.warning")
        event = Event(type=EventType.SESSION_REQUEST, data="not_a_dict")

        session = await app._get_session_from_event(event=event)

        assert session is None
        mock_logger_warning.assert_called_with("Session request event data is not a dictionary")

    @pytest.mark.asyncio
    async def test_get_session_from_event_manager_exception(
        self, app: ServerApp, mock_connection: Any, mock_session: Any, mock_server: Any, mocker: MockerFixture
    ) -> None:
        mock_server.session_manager.add_session.side_effect = ValueError("Manager error")
        mock_logger_error = mocker.patch("pywebtransport.server.app.logger.error")

        event = Event(
            type=EventType.SESSION_REQUEST,
            data={"connection": mock_connection, "session": mock_session, "session_id": 100},
        )

        session = await app._get_session_from_event(event=event)

        assert session is mock_session
        mock_logger_error.assert_called()

    @pytest.mark.asyncio
    async def test_get_session_from_event_mismatched_connection(
        self, app: ServerApp, mocker: MockerFixture, mock_connection: Any
    ) -> None:
        other_conn = mocker.create_autospec(WebTransportConnection, instance=True)
        other_conn.connection_id = "conn_other"

        mock_session = mocker.MagicMock(name="WebTransportSession")
        mock_session.__class__ = WebTransportSession
        mock_session._connection.return_value = other_conn

        event = Event(
            type=EventType.SESSION_REQUEST,
            data={"connection": mock_connection, "session": mock_session, "session_id": 100},
        )

        session = await app._get_session_from_event(event=event)

        assert session is None

    @pytest.mark.asyncio
    async def test_get_session_from_event_no_session_manager(
        self, app: ServerApp, mock_connection: Any, mock_session: Any
    ) -> None:
        cast(Any, app.server).session_manager = None

        event = Event(
            type=EventType.SESSION_REQUEST,
            data={"connection": mock_connection, "session": mock_session, "session_id": 100},
        )

        session = await app._get_session_from_event(event=event)

        assert session is mock_session

    @pytest.mark.asyncio
    async def test_get_session_from_event_success(
        self, app: ServerApp, mock_connection: Any, mock_session: Any, mock_server: Any
    ) -> None:
        event = Event(
            type=EventType.SESSION_REQUEST,
            data={"connection": mock_connection, "session": mock_session, "session_id": 100},
        )

        session = await app._get_session_from_event(event=event)

        assert session is mock_session
        mock_server.session_manager.add_session.assert_awaited_once_with(session=mock_session)

    @pytest.mark.asyncio
    async def test_handle_session_request_exception_cleanup(
        self,
        app: ServerApp,
        mocker: MockerFixture,
        mock_connection: Any,
        mock_session: Any,
        mock_future: asyncio.Future[Any],
    ) -> None:
        mocker.patch.object(app, "_get_session_from_event", side_effect=ValueError("Unexpected"))

        req_id = 77
        mock_connection._protocol.create_request.return_value = (req_id, mock_future)

        event = Event(
            type=EventType.SESSION_REQUEST,
            data={"connection": mock_connection, "session_id": 100, "session": mock_session},
        )

        await app._handle_session_request(event=event)

        mock_connection._protocol.send_event.assert_called_once()
        call_args = mock_connection._protocol.send_event.call_args
        event_sent = call_args.kwargs["event"]
        assert isinstance(event_sent, UserCloseSession)
        assert event_sent.request_id == req_id
        assert event_sent.session_id == 100

    @pytest.mark.asyncio
    async def test_handle_session_request_exception_cleanup_branches(
        self, app: ServerApp, mocker: MockerFixture, mock_connection: Any, mock_session: Any
    ) -> None:
        mocker.patch.object(app, "_get_session_from_event", side_effect=ValueError("Unexpected"))

        event_no_id = Event(type=EventType.SESSION_REQUEST, data={"connection": mock_connection})
        await app._handle_session_request(event=event_no_id)

        mock_connection._protocol.send_event.assert_not_called()

        mock_connection.reset_mock()

        event_no_conn = Event(type=EventType.SESSION_REQUEST, data={"session_id": 100})
        await app._handle_session_request(event=event_no_conn)

        mock_connection._protocol.send_event.assert_not_called()

        mock_session.is_closed = True
        event_closed = Event(
            type=EventType.SESSION_REQUEST,
            data={"connection": mock_connection, "session_id": 100, "session": mock_session},
        )

        await app._handle_session_request(event=event_closed)
        mock_session.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_session_request_exception_cleanup_error(
        self, app: ServerApp, mocker: MockerFixture, mock_connection: Any
    ) -> None:
        mocker.patch.object(app, "_get_session_from_event", side_effect=ValueError("Unexpected"))
        mock_connection._protocol.create_request.side_effect = ValueError("Cleanup error")
        mock_logger_error = mocker.patch("pywebtransport.server.app.logger.error")

        event = Event(type=EventType.SESSION_REQUEST, data={"connection": mock_connection, "session_id": 100})

        await app._handle_session_request(event=event)

        mock_logger_error.assert_any_call(
            "Error during session request error cleanup: %s", mocker.ANY, exc_info=mocker.ANY
        )

    @pytest.mark.asyncio
    async def test_handle_session_request_exception_cleanup_with_session(
        self,
        app: ServerApp,
        mocker: MockerFixture,
        mock_session: Any,
        mock_connection: Any,
        mock_future: asyncio.Future[Any],
    ) -> None:
        mocker.patch.object(app, "_get_session_from_event", return_value=mock_session)
        mocker.patch.object(app, "_middleware_manager")
        mocker.patch.object(app, "_dispatch_to_handler", side_effect=ValueError("Dispatch error"))

        mock_session.close.side_effect = ValueError("Session close error")
        mock_logger_error = mocker.patch("pywebtransport.server.app.logger.error")

        req_id = 88
        mock_connection._protocol.create_request.return_value = (req_id, mock_future)

        event = Event(type=EventType.SESSION_REQUEST, data={})

        await app._handle_session_request(event=event)

        mock_session.close.assert_awaited_once()
        mock_logger_error.assert_any_call(
            "Error during session request error cleanup: %s", mocker.ANY, exc_info=mocker.ANY
        )

    @pytest.mark.asyncio
    async def test_handle_session_request_happy_path(
        self, app: ServerApp, mock_middleware_manager: Any, mocker: MockerFixture, mock_session: Any
    ) -> None:
        mock_get_session = mocker.patch.object(
            app, "_get_session_from_event", new_callable=mocker.AsyncMock, return_value=mock_session
        )
        mock_dispatch = mocker.patch.object(app, "_dispatch_to_handler", new_callable=mocker.AsyncMock)

        event = Event(type=EventType.SESSION_REQUEST, data={})

        await app._handle_session_request(event=event)

        mock_get_session.assert_awaited_once_with(event=event)
        mock_middleware_manager.process_request.assert_awaited_once_with(session=mock_session)
        mock_dispatch.assert_awaited_once_with(session=mock_session)

    @pytest.mark.asyncio
    async def test_handle_session_request_middleware_rejection(
        self,
        app: ServerApp,
        mock_middleware_manager: Any,
        mocker: MockerFixture,
        mock_session: Any,
        mock_connection: Any,
        mock_future: asyncio.Future[Any],
    ) -> None:
        mocker.patch.object(app, "_get_session_from_event", return_value=mock_session)
        mock_middleware_manager.process_request.side_effect = MiddlewareRejected(status_code=403)

        req_id = 66
        mock_connection._protocol.create_request.return_value = (req_id, mock_future)

        event = Event(type=EventType.SESSION_REQUEST, data={"connection": mock_connection})

        await app._handle_session_request(event=event)

        mock_connection._protocol.create_request.assert_called_once()
        mock_connection._protocol.send_event.assert_called_once()
        call_args = mock_connection._protocol.send_event.call_args
        event_sent = call_args.kwargs["event"]
        assert isinstance(event_sent, UserRejectSession)
        assert event_sent.request_id == req_id
        assert event_sent.status_code == 403

        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_session_request_middleware_rejection_branches(
        self,
        app: ServerApp,
        mock_middleware_manager: Any,
        mocker: MockerFixture,
        mock_session: Any,
        mock_connection: Any,
        mock_future: asyncio.Future[Any],
    ) -> None:
        mocker.patch.object(app, "_get_session_from_event", return_value=mock_session)
        mock_middleware_manager.process_request.side_effect = MiddlewareRejected(status_code=403)

        req_id = 66
        mock_connection._protocol.create_request.return_value = (req_id, mock_future)

        event = Event(type=EventType.SESSION_REQUEST, data={"connection": mock_connection})
        await app._handle_session_request(event=event)

        mock_session.close.assert_awaited_once()

        mock_session.close.reset_mock()
        mock_connection._protocol.create_request.reset_mock()

        mock_session.is_closed = True
        await app._handle_session_request(event=event)
        mock_session.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_session_request_middleware_rejection_no_connection(
        self, app: ServerApp, mock_middleware_manager: Any, mocker: MockerFixture, mock_session: Any
    ) -> None:
        mocker.patch.object(app, "_get_session_from_event", return_value=mock_session)
        mock_middleware_manager.process_request.side_effect = MiddlewareRejected(status_code=403)

        event = Event(type=EventType.SESSION_REQUEST, data={})

        await app._handle_session_request(event=event)

        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_session_request_no_session(self, app: ServerApp, mocker: MockerFixture) -> None:
        mocker.patch.object(app, "_get_session_from_event", new_callable=mocker.AsyncMock, return_value=None)
        mock_middleware = mocker.patch.object(app, "_middleware_manager")

        event = Event(type=EventType.SESSION_REQUEST, data={})
        await app._handle_session_request(event=event)

        mock_middleware.process_request.assert_not_called()

    def test_init(self, app: ServerApp, mock_server: Any) -> None:
        assert app.server is mock_server
        mock_server.on.assert_called_once_with(
            event_type=EventType.SESSION_REQUEST, handler=app._handle_session_request
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "run_kwargs, serve_kwargs",
        [
            ({"host": "localhost", "port": 1234}, {"host": "localhost", "port": 1234}),
            ({}, {"host": "0.0.0.0", "port": 4433}),
        ],
        ids=["with_args", "with_defaults"],
    )
    async def test_run(
        self, app: ServerApp, mocker: MockerFixture, run_kwargs: dict[str, Any], serve_kwargs: dict[str, Any]
    ) -> None:
        mocker.patch.object(app, "serve", new_callable=mocker.AsyncMock)
        mock_asyncio_run = mocker.patch("asyncio.run")

        app.run(**run_kwargs)

        mock_asyncio_run.assert_called_once()
        call_args = mock_asyncio_run.call_args
        main_coro = call_args.args[0] if call_args.args else call_args.kwargs.get("main")
        if asyncio.iscoroutine(main_coro):
            await main_coro

    @pytest.mark.asyncio
    async def test_run_handler_exception(self, app: ServerApp, mocker: MockerFixture, mock_session: Any) -> None:
        handler_mock = mocker.AsyncMock(side_effect=ValueError("Handler error"))

        await app._run_handler_safely(handler=handler_mock, session=mock_session, params={})

        handler_mock.assert_awaited_once_with(mock_session)
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_handler_safely_close_fails(
        self, app: ServerApp, mocker: MockerFixture, mock_session: Any
    ) -> None:
        handler_mock = mocker.AsyncMock()
        mock_session.is_closed = False
        mock_session.close.side_effect = RuntimeError("Close failed")

        await app._run_handler_safely(handler=handler_mock, session=mock_session, params={})

        handler_mock.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_handler_safely_connection_error(
        self, app: ServerApp, mocker: MockerFixture, mock_session: Any
    ) -> None:
        handler_mock = mocker.AsyncMock()
        mock_session.is_closed = False
        mock_session.close.side_effect = ConnectionError("Engine stopped")
        mock_logger_debug = mocker.patch("pywebtransport.server.app.logger.debug")

        await app._run_handler_safely(handler=handler_mock, session=mock_session, params={})

        mock_session.close.assert_awaited_once()
        mock_logger_debug.assert_any_call(
            "Session %s cleanup: Connection closed implicitly or Engine stopped (%s).",
            mock_session.session_id,
            mocker.ANY,
        )

    @pytest.mark.asyncio
    async def test_run_handler_session_already_closed(
        self, app: ServerApp, mocker: MockerFixture, mock_session: Any
    ) -> None:
        handler_mock = mocker.AsyncMock()
        mock_session.is_closed = True

        await app._run_handler_safely(handler=handler_mock, session=mock_session, params={})

        handler_mock.assert_awaited_once()
        mock_session.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_handler_with_params(self, app: ServerApp, mocker: MockerFixture, mock_session: Any) -> None:
        handler_mock = mocker.AsyncMock()
        params = {"id": "123", "action": "test"}

        await app._run_handler_safely(handler=handler_mock, session=mock_session, params=params)

        handler_mock.assert_awaited_once_with(mock_session, id="123", action="test")
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_with_exception(self, app: ServerApp, mocker: MockerFixture) -> None:
        def consume_coro_and_raise(*args: Any, **kwargs: Any) -> Any:
            coro = kwargs.get("main") or (args[0] if args else None)
            if asyncio.iscoroutine(coro):
                coro.close()
            raise ValueError("Run error")

        mock_asyncio_run = mocker.patch("asyncio.run", side_effect=consume_coro_and_raise)

        with pytest.raises(ValueError, match="Run error"):
            app.run()

        mock_asyncio_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_keyboard_interrupt(self, app: ServerApp, mocker: MockerFixture) -> None:
        mocker.patch.object(app, "serve", new_callable=mocker.AsyncMock)
        mock_logger_info = mocker.patch("pywebtransport.server.app.logger.info")

        def consume_coro_and_raise(*args: Any, **kwargs: Any) -> Any:
            coro = kwargs.get("main") or (args[0] if args else None)
            if asyncio.iscoroutine(coro):
                coro.close()
            raise KeyboardInterrupt

        mock_asyncio_run = mocker.patch("asyncio.run", side_effect=consume_coro_and_raise)

        app.run()

        mock_asyncio_run.assert_called_once()
        mock_logger_info.assert_called_with("Server stopped by user.")

    @pytest.mark.asyncio
    async def test_serve(self, app: ServerApp, mock_server: Any, mocker: MockerFixture) -> None:
        app._tg = mocker.Mock()
        await app.serve(host="localhost", port=8080)
        mock_server.listen.assert_awaited_once_with(host="localhost", port=8080)
        mock_server.serve_forever.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_serve_not_activated(self, app: ServerApp) -> None:
        with pytest.raises(ServerError, match="ServerApp has not been activated"):
            await app.serve()

    @pytest.mark.asyncio
    async def test_serve_with_default_host_port(self, app: ServerApp, mock_server: Any, mocker: MockerFixture) -> None:
        app._tg = mocker.Mock()
        await app.serve()
        mock_server.listen.assert_awaited_once_with(host="0.0.0.0", port=4433)
        mock_server.serve_forever.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_active_tasks(self, app: ServerApp, mocker: MockerFixture) -> None:
        mock_task_1 = mocker.MagicMock(spec=asyncio.Task)
        mock_task_1.done.return_value = False
        mock_task_2 = mocker.MagicMock(spec=asyncio.Task)
        mock_task_2.done.return_value = True

        app._handler_tasks.add(mock_task_1)
        app._handler_tasks.add(mock_task_2)

        await app.shutdown()

        mock_task_1.cancel.assert_called_once()
        mock_task_2.cancel.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("is_async", [True, False])
    async def test_startup_and_shutdown_handlers(self, app: ServerApp, mocker: MockerFixture, is_async: bool) -> None:
        mocker.patch("asyncio.iscoroutinefunction", return_value=is_async)

        startup_handler = mocker.AsyncMock() if is_async else mocker.MagicMock()
        shutdown_handler = mocker.AsyncMock() if is_async else mocker.MagicMock()

        app.on_startup(startup_handler)
        app.on_shutdown(shutdown_handler)

        await app.startup()
        if is_async:
            startup_handler.assert_awaited_once()
        else:
            startup_handler.assert_called_once()

        await app.shutdown()
        if is_async:
            shutdown_handler.assert_awaited_once()
        else:
            shutdown_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_and_shutdown_stateful_middleware(self, app: ServerApp, mocker: MockerFixture) -> None:
        stateful_middleware = mocker.MagicMock(spec=StatefulMiddlewareProtocol)
        stateful_middleware.__aenter__ = mocker.AsyncMock()
        stateful_middleware.__aexit__ = mocker.AsyncMock()
        app.add_middleware(middleware=stateful_middleware)

        await app.startup()
        stateful_middleware.__aenter__.assert_awaited_once()

        await app.shutdown()
        stateful_middleware.__aexit__.assert_awaited_once_with(None, None, None)

    @pytest.mark.asyncio
    async def test_startup_shutdown_defensive_checks(self, app: ServerApp, mocker: MockerFixture) -> None:
        middleware = mocker.MagicMock(spec=StatefulMiddlewareProtocol)
        middleware.__aenter__ = mocker.AsyncMock()
        middleware.__aexit__ = mocker.AsyncMock()

        app._stateful_middleware.append(middleware)

        await app.startup()
        middleware.__aenter__.assert_awaited_once()

        await app.shutdown()
        middleware.__aexit__.assert_awaited_once()



================================================
FILE: tests/unit/server/test_cluster.py
================================================
"""Unit tests for the pywebtransport.server.cluster module."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import pytest
from pytest_asyncio import fixture as asyncio_fixture
from pytest_mock import MockerFixture

from pywebtransport import ServerConfig, ServerError
from pywebtransport.server import ServerCluster, WebTransportServer
from pywebtransport.types import ConnectionState, SessionState


class TestServerCluster:

    @asyncio_fixture
    async def cluster(
        self, server_configs: list[ServerConfig], mock_webtransport_server_class: Any
    ) -> AsyncGenerator[ServerCluster, None]:
        cluster_instance = ServerCluster(configs=server_configs)
        async with cluster_instance:
            yield cluster_instance

    @pytest.fixture
    def mock_webtransport_server_class(self, mocker: MockerFixture) -> Any:
        mock_server_class = mocker.patch("pywebtransport.server.cluster.WebTransportServer")

        def new_server_instance(*args: Any, **kwargs: Any) -> Any:
            instance = mocker.create_autospec(WebTransportServer, instance=True)
            instance.__aenter__ = mocker.AsyncMock(return_value=instance)
            instance.listen = mocker.AsyncMock()
            instance.close = mocker.AsyncMock()

            mock_stats = mocker.Mock()
            mock_stats.connections_accepted = 1
            mock_stats.connections_rejected = 1
            mock_diagnostics = mocker.Mock()
            mock_diagnostics.stats = mock_stats
            mock_diagnostics.connection_states = {ConnectionState.CONNECTED: 1}
            mock_diagnostics.session_states = {SessionState.CONNECTED: 1}
            instance.diagnostics = mocker.AsyncMock(return_value=mock_diagnostics)

            if "config" in kwargs:
                instance.config = kwargs["config"]
                if hasattr(kwargs["config"], "bind_port"):
                    local_address = ("127.0.0.1", kwargs["config"].bind_port)
                    type(instance).local_address = mocker.PropertyMock(return_value=local_address)

            return instance

        mock_server_class.side_effect = new_server_instance
        return mock_server_class

    @pytest.fixture
    def server_configs(self, tmp_path: Path) -> list[ServerConfig]:
        c1 = tmp_path / "c1.pem"
        k1 = tmp_path / "k1.pem"
        c2 = tmp_path / "c2.pem"
        k2 = tmp_path / "k2.pem"
        c1.touch()
        k1.touch()
        c2.touch()
        k2.touch()

        return [
            ServerConfig(bind_host="127.0.0.1", bind_port=8001, certfile=str(c1), keyfile=str(k1)),
            ServerConfig(bind_host="127.0.0.1", bind_port=8002, certfile=str(c2), keyfile=str(k2)),
        ]

    @pytest.mark.asyncio
    async def test_add_server(self, cluster: ServerCluster, tmp_path: Path) -> None:
        c3 = tmp_path / "c3.pem"
        k3 = tmp_path / "k3.pem"
        c3.touch()
        k3.touch()
        new_config = ServerConfig(bind_port=8003, certfile=str(c3), keyfile=str(k3))

        result = await cluster.add_server(config=new_config)

        assert result is not None
        assert len(cluster._servers) == 3
        cast(Any, result.listen).assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_server_failure_during_listen(
        self, cluster: ServerCluster, mocker: MockerFixture, mock_webtransport_server_class: Any, tmp_path: Path
    ) -> None:
        mock_fail_instance = mocker.create_autospec(WebTransportServer, instance=True)
        mock_fail_instance.__aenter__ = mocker.AsyncMock(return_value=mock_fail_instance)
        mock_fail_instance.listen = mocker.AsyncMock(side_effect=ValueError("Listen failed"))
        mock_fail_instance.close = mocker.AsyncMock()
        mock_webtransport_server_class.side_effect = [mock_fail_instance]

        c3 = tmp_path / "c3.pem"
        k3 = tmp_path / "k3.pem"
        c3.touch()
        k3.touch()
        new_config = ServerConfig(bind_port=8003, certfile=str(c3), keyfile=str(k3))

        result = await cluster.add_server(config=new_config)

        assert result is None
        cast(Any, mock_fail_instance.close).assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_server_failure_on_creation(
        self, cluster: ServerCluster, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        initial_count = await cluster.get_server_count()
        mocker.patch.object(cluster, "_create_and_start_server", side_effect=IOError("Failed to bind"))
        c3 = tmp_path / "c3.pem"
        k3 = tmp_path / "k3.pem"
        c3.touch()
        k3.touch()
        new_config = ServerConfig(bind_port=8003, certfile=str(c3), keyfile=str(k3))

        result = await cluster.add_server(config=new_config)

        assert result is None
        assert await cluster.get_server_count() == initial_count

    @pytest.mark.asyncio
    async def test_add_server_race_condition_on_stop(
        self, cluster: ServerCluster, mocker: MockerFixture, mock_webtransport_server_class: Any, tmp_path: Path
    ) -> None:
        c3 = tmp_path / "c3.pem"
        k3 = tmp_path / "k3.pem"
        c3.touch()
        k3.touch()
        new_config = ServerConfig(bind_port=8003, certfile=str(c3), keyfile=str(k3))

        mock_instance = mocker.create_autospec(WebTransportServer, instance=True)
        mock_instance.__aenter__ = mocker.AsyncMock(return_value=mock_instance)
        mock_instance.listen = mocker.AsyncMock()
        mock_instance.close = mocker.AsyncMock()

        async def create_and_stop_cluster(*args: Any, **kwargs: Any) -> Any:
            if cluster._lock:
                async with cluster._lock:
                    cluster._running = False
            return mock_instance

        mocker.patch.object(cluster, "_create_and_start_server", side_effect=create_and_stop_cluster)

        result = await cluster.add_server(config=new_config)

        assert result is None
        cast(Any, mock_instance.close).assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_server_while_stopped(self, cluster: ServerCluster, tmp_path: Path) -> None:
        await cluster.stop_all()
        assert not cluster.is_running

        c3 = tmp_path / "c3.pem"
        k3 = tmp_path / "k3.pem"
        c3.touch()
        k3.touch()
        new_config = ServerConfig(bind_port=8003, certfile=str(c3), keyfile=str(k3))

        result = await cluster.add_server(config=new_config)

        assert result is None
        assert len(cluster._servers) == 0
        assert len(cluster._configs) == 3

    @pytest.mark.asyncio
    async def test_async_context_manager(self, server_configs: list[ServerConfig], mocker: MockerFixture) -> None:
        cluster = ServerCluster(configs=server_configs)
        mock_start = mocker.patch.object(cluster, "start_all", new_callable=mocker.AsyncMock)
        mock_stop = mocker.patch.object(cluster, "stop_all", new_callable=mocker.AsyncMock)

        async with cluster:
            mock_start.assert_awaited_once()
            mock_stop.assert_not_called()

        mock_stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_cluster_stats(self, cluster: ServerCluster) -> None:
        stats = await cluster.get_cluster_stats()

        assert stats["server_count"] == 2
        assert stats["total_connections_accepted"] == 2
        assert stats["total_connections_rejected"] == 2
        assert stats["total_connections_active"] == 2
        assert stats["total_sessions_active"] == 2

    @pytest.mark.asyncio
    async def test_get_cluster_stats_empty(self, mocker: MockerFixture) -> None:
        cluster = ServerCluster(configs=[])
        async with cluster:
            stats = await cluster.get_cluster_stats()
            assert stats == {
                "server_count": 0,
                "total_connections_accepted": 0,
                "total_connections_rejected": 0,
                "total_connections_active": 0,
                "total_sessions_active": 0,
            }

    @pytest.mark.asyncio
    async def test_get_cluster_stats_with_partial_failure(self, cluster: ServerCluster) -> None:
        server_to_fail = cluster._servers[0]
        cast(Any, server_to_fail.diagnostics).side_effect = ValueError("Stats failed")

        with pytest.raises(ExceptionGroup):
            await cluster.get_cluster_stats()

    @pytest.mark.asyncio
    async def test_get_server_count(self, cluster: ServerCluster) -> None:
        assert await cluster.get_server_count() == 2

    @pytest.mark.asyncio
    async def test_get_servers(self, cluster: ServerCluster) -> None:
        servers_copy = await cluster.get_servers()

        assert len(servers_copy) == 2
        assert servers_copy is not cluster._servers

    def test_init(self, server_configs: list[ServerConfig]) -> None:
        cluster = ServerCluster(configs=server_configs)

        assert cluster._configs is not server_configs
        assert not cluster.is_running
        assert not cluster._servers

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method_name, method_args, expected_match",
        [
            ("start_all", {}, "ServerCluster has not been activated"),
            ("stop_all", {}, "ServerCluster has not been activated"),
            ("add_server", {"config": None}, "ServerCluster has not been activated"),
            ("remove_server", {"host": "localhost", "port": 8000}, "ServerCluster has not been activated"),
            ("get_cluster_stats", {}, "ServerCluster has not been activated"),
            ("get_server_count", {}, "Cluster not activated"),
            ("get_servers", {}, "Cluster not activated"),
        ],
    )
    async def test_public_methods_raise_if_not_activated(
        self,
        server_configs: list[ServerConfig],
        method_name: str,
        method_args: Any,
        expected_match: str,
        tmp_path: Path,
    ) -> None:
        cluster = ServerCluster(configs=server_configs)
        method = getattr(cluster, method_name)

        if method_name == "add_server":
            c = tmp_path / "c_p.pem"
            k = tmp_path / "k_p.pem"
            c.touch()
            k.touch()
            method_args = {"config": ServerConfig(certfile=str(c), keyfile=str(k))}

        with pytest.raises(ServerError, match=expected_match):
            await method(**method_args)

    @pytest.mark.asyncio
    async def test_remove_server(self, cluster: ServerCluster) -> None:
        initial_servers = await cluster.get_servers()
        assert len(initial_servers) == 2

        removed = await cluster.remove_server(host="127.0.0.1", port=8001)

        assert removed is True
        assert await cluster.get_server_count() == 1
        remaining_servers = await cluster.get_servers()
        assert remaining_servers[0] is initial_servers[1]
        cast(Any, initial_servers[0].close).assert_awaited_once()

        removed_again = await cluster.remove_server(host="127.0.0.1", port=9999)

        assert removed_again is False
        assert await cluster.get_server_count() == 1

    @pytest.mark.asyncio
    async def test_serve_forever(self, cluster: ServerCluster) -> None:
        await cluster.start_all()
        serve_task = asyncio.create_task(cluster.serve_forever())

        await asyncio.sleep(0.01)
        assert not serve_task.done()

        cluster._shutdown_event.set()

        await serve_task
        assert serve_task.done()

    @pytest.mark.asyncio
    async def test_serve_forever_cancellation(self, cluster: ServerCluster, caplog: pytest.LogCaptureFixture) -> None:
        await cluster.start_all()
        serve_task = asyncio.create_task(cluster.serve_forever())
        await asyncio.sleep(0.01)

        with caplog.at_level(logging.INFO):
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass

        assert "serve_forever cancelled" in caplog.text

    @pytest.mark.asyncio
    async def test_serve_forever_not_activated(self, server_configs: list[ServerConfig]) -> None:
        cluster = ServerCluster(configs=server_configs)
        with pytest.raises(ServerError, match="Cluster not activated"):
            await cluster.serve_forever()

    @pytest.mark.asyncio
    async def test_serve_forever_not_running(self, cluster: ServerCluster) -> None:
        await cluster.stop_all()
        with pytest.raises(ServerError, match="Cluster is not running"):
            await cluster.serve_forever()

    @pytest.mark.asyncio
    async def test_serve_forever_wait_exception(self, cluster: ServerCluster, mocker: MockerFixture) -> None:
        await cluster.start_all()
        mocker.patch.object(cluster._shutdown_event, "wait", side_effect=ValueError("Unexpected error"))
        mock_logger = mocker.patch("pywebtransport.server.cluster.logger")

        await cluster.serve_forever()

        mock_logger.error.assert_called_with("Error during serve_forever wait: %s", mocker.ANY)

    @pytest.mark.asyncio
    async def test_start_all_failure(
        self, server_configs: list[ServerConfig], mock_webtransport_server_class: Any, mocker: MockerFixture
    ) -> None:
        mock_server_fail = mocker.create_autospec(WebTransportServer, instance=True)
        mock_server_fail.__aenter__ = mocker.AsyncMock(return_value=mock_server_fail)
        mock_server_fail.listen = mocker.AsyncMock(side_effect=ValueError("Listen failed"))
        mock_server_fail.close = mocker.AsyncMock()

        mock_server_ok = mocker.create_autospec(WebTransportServer, instance=True)
        mock_server_ok.__aenter__ = mocker.AsyncMock(return_value=mock_server_ok)
        mock_server_ok.listen = mocker.AsyncMock()
        mock_server_ok.close = mocker.AsyncMock()

        mock_webtransport_server_class.side_effect = [mock_server_fail, mock_server_ok]
        cluster = ServerCluster(configs=server_configs)
        cluster._lock = asyncio.Lock()

        await cluster.start_all()

        assert cluster.is_running
        assert len(cluster._servers) == 1
        assert cluster._servers[0] is mock_server_ok
        cast(Any, mock_server_fail.close).assert_awaited()

    @pytest.mark.asyncio
    async def test_start_all_failure_during_cleanup(
        self, server_configs: list[ServerConfig], mock_webtransport_server_class: Any, mocker: MockerFixture
    ) -> None:
        mock_server_fail = mocker.create_autospec(WebTransportServer, instance=True)
        mock_server_fail.__aenter__ = mocker.AsyncMock(return_value=mock_server_fail)
        mock_server_fail.listen = mocker.AsyncMock(side_effect=ValueError("Listen failed"))
        mock_server_fail.close = mocker.AsyncMock(side_effect=IOError("Cleanup failed"))

        mock_server_ok = mocker.create_autospec(WebTransportServer, instance=True)
        mock_server_ok.__aenter__ = mocker.AsyncMock(return_value=mock_server_ok)
        mock_server_ok.listen = mocker.AsyncMock()
        mock_server_ok.close = mocker.AsyncMock()

        mock_webtransport_server_class.side_effect = [mock_server_fail, mock_server_ok]
        cluster = ServerCluster(configs=server_configs)
        cluster._lock = asyncio.Lock()

        await cluster.start_all()

        assert cluster.is_running
        assert len(cluster._servers) == 1

    @pytest.mark.asyncio
    async def test_start_and_stop_all(self, cluster: ServerCluster) -> None:
        assert cluster.is_running
        assert len(cluster._servers) == 2
        for server in cluster._servers:
            cast(Any, server.listen).assert_awaited_once()

        servers_to_stop = await cluster.get_servers()
        await cluster.stop_all()

        for server in servers_to_stop:
            cast(Any, server.close).assert_awaited_once()

        assert await cluster.get_server_count() == 0
        assert not cluster.is_running

    @pytest.mark.asyncio
    async def test_start_and_stop_idempotency(self, cluster: ServerCluster) -> None:
        assert cluster.is_running

        await cluster.start_all()
        assert len(cluster._servers) == 2

        await cluster.stop_all()
        assert not cluster._servers

        await cluster.stop_all()
        assert not cluster._servers

    @pytest.mark.asyncio
    async def test_stop_all_failure(self, cluster: ServerCluster) -> None:
        server_to_fail = cluster._servers[0]
        cast(Any, server_to_fail.close).side_effect = ValueError("Close failed")

        with pytest.raises(ExceptionGroup):
            await cluster.stop_all()

        assert not cluster.is_running
        assert not cluster._servers

    @pytest.mark.asyncio
    async def test_stop_all_with_no_servers(self, cluster: ServerCluster) -> None:
        await cluster.stop_all()
        assert not cluster.is_running

        await cluster.stop_all()
        assert not cluster.is_running



================================================
FILE: tests/unit/server/test_middleware.py
================================================
"""Unit tests for the pywebtransport.server.middleware module."""

import asyncio
import http
import logging
from collections import deque
from collections.abc import AsyncGenerator
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from _pytest.logging import LogCaptureFixture
from pytest_asyncio import fixture as asyncio_fixture
from pytest_mock import MockerFixture

from pywebtransport import ServerError, WebTransportSession
from pywebtransport.server import (
    MiddlewareManager,
    MiddlewareRejected,
    create_auth_middleware,
    create_cors_middleware,
    create_logging_middleware,
    create_rate_limit_middleware,
)
from pywebtransport.server.middleware import RateLimiter


class TestMiddlewareFactories:

    @pytest.fixture
    def mock_session(self, mocker: MockerFixture) -> Any:
        session = mocker.Mock(spec=WebTransportSession)
        session.path = "/test"
        session.headers = {"origin": "https://example.com", "x-auth": "good-token"}
        session.remote_address = ("1.2.3.4", 12345)
        return session

    @pytest.mark.asyncio
    async def test_create_auth_middleware_failure(self, mock_session: Any, mocker: MockerFixture) -> None:
        auth_handler = mocker.AsyncMock(return_value=False)
        auth_middleware = create_auth_middleware(auth_handler=auth_handler)

        with pytest.raises(MiddlewareRejected) as exc_info:
            await auth_middleware(session=mock_session)

        assert exc_info.value.status_code == http.HTTPStatus.UNAUTHORIZED
        auth_handler.assert_awaited_once_with(headers=mock_session.headers)

    @pytest.mark.asyncio
    async def test_create_auth_middleware_handler_exception(self, mock_session: Any, mocker: MockerFixture) -> None:
        auth_handler = mocker.AsyncMock(side_effect=ValueError("Auth error"))
        auth_middleware = create_auth_middleware(auth_handler=auth_handler)

        with pytest.raises(MiddlewareRejected) as exc_info:
            await auth_middleware(session=mock_session)

        assert exc_info.value.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_create_auth_middleware_success(self, mock_session: Any, mocker: MockerFixture) -> None:
        auth_handler = mocker.AsyncMock(return_value=True)
        auth_middleware = create_auth_middleware(auth_handler=auth_handler)

        await auth_middleware(session=mock_session)

        auth_handler.assert_awaited_once_with(headers=mock_session.headers)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "origin, allowed_origins, should_pass",
        [
            ("https://example.com", ["https://example.com"], True),
            ("https://evil.com", ["https://example.com"], False),
            ("https://any.com", ["*"], True),
            ("https://sub.example.com", ["*.example.com"], True),
            (None, ["https://example.com"], False),
        ],
    )
    async def test_create_cors_middleware(
        self, mock_session: Any, origin: str | None, allowed_origins: list[str], should_pass: bool
    ) -> None:
        mock_session.headers = {"origin": origin} if origin else {}
        cors_middleware = create_cors_middleware(allowed_origins=allowed_origins)

        if should_pass:
            await cors_middleware(session=mock_session)
        else:
            with pytest.raises(MiddlewareRejected) as exc_info:
                await cors_middleware(session=mock_session)
            assert exc_info.value.status_code == http.HTTPStatus.FORBIDDEN

    @pytest.mark.asyncio
    async def test_create_logging_middleware(self, mock_session: Any, caplog: LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        logging_middleware = create_logging_middleware()

        await logging_middleware(session=mock_session)

        assert "Session request: path='/test' from=1.2.3.4:12345" in caplog.text

    @pytest.mark.asyncio
    async def test_create_logging_middleware_no_remote_address(
        self, mocker: MockerFixture, caplog: LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)
        session = mocker.Mock(spec=WebTransportSession)
        session.path = "/no-addr"
        session.remote_address = None
        logging_middleware = create_logging_middleware()

        await logging_middleware(session=session)

        assert "from=unknown" in caplog.text

    def test_create_rate_limit_middleware(self) -> None:
        limiter = create_rate_limit_middleware(max_requests=50, window_seconds=30)

        assert isinstance(limiter, RateLimiter)
        assert limiter._max_requests == 50
        assert limiter._window_seconds == 30

    @pytest.mark.asyncio
    async def test_middleware_with_generic_session(self, caplog: LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        generic_session = MagicMock()
        generic_session.path = "/generic"
        generic_session.headers = {}
        generic_session.remote_address = None

        logging_middleware = create_logging_middleware()
        await logging_middleware(session=generic_session)
        assert "Session request: path='/generic' from=unknown" in caplog.text

        async with RateLimiter() as rate_limiter:
            await rate_limiter(session=generic_session)
            assert rate_limiter._lock is not None
            async with rate_limiter._lock:
                assert "unknown" in rate_limiter._requests


@pytest.mark.asyncio
class TestMiddlewareManager:

    @pytest.fixture
    def mock_session(self, mocker: MockerFixture) -> Any:
        return mocker.create_autospec(WebTransportSession, instance=True)

    async def test_add_remove_middleware(self) -> None:
        manager = MiddlewareManager()
        assert manager.get_middleware_count() == 0

        async def middleware1(*, session: Any) -> None:
            pass

        manager.add_middleware(middleware=middleware1)
        assert manager.get_middleware_count() == 1

        manager.remove_middleware(middleware=middleware1)
        assert manager.get_middleware_count() == 0

        manager.remove_middleware(middleware=middleware1)
        assert manager.get_middleware_count() == 0

    async def test_process_request_all_pass(self, mock_session: Any, mocker: MockerFixture) -> None:
        manager = MiddlewareManager()
        middleware1 = mocker.AsyncMock(return_value=None)
        middleware2 = mocker.AsyncMock(return_value=None)
        manager.add_middleware(middleware=middleware1)
        manager.add_middleware(middleware=middleware2)

        await manager.process_request(session=mock_session)

        middleware1.assert_awaited_once_with(session=mock_session)
        middleware2.assert_awaited_once_with(session=mock_session)

    async def test_process_request_exception(
        self, mock_session: Any, mocker: MockerFixture, caplog: LogCaptureFixture
    ) -> None:
        manager = MiddlewareManager()
        middleware1 = mocker.AsyncMock(side_effect=ValueError("Middleware error"))
        manager.add_middleware(middleware=middleware1)

        with pytest.raises(MiddlewareRejected) as exc_info:
            await manager.process_request(session=mock_session)

        assert exc_info.value.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR
        assert "Middleware error: Middleware error" in caplog.text

    async def test_process_request_rejection(self, mock_session: Any, mocker: MockerFixture) -> None:
        manager = MiddlewareManager()
        middleware1 = mocker.AsyncMock(return_value=None)
        middleware2 = mocker.AsyncMock(side_effect=MiddlewareRejected(status_code=http.HTTPStatus.FORBIDDEN))
        middleware3 = mocker.AsyncMock(return_value=None)
        manager.add_middleware(middleware=middleware1)
        manager.add_middleware(middleware=middleware2)
        manager.add_middleware(middleware=middleware3)

        with pytest.raises(MiddlewareRejected) as exc_info:
            await manager.process_request(session=mock_session)

        assert exc_info.value.status_code == http.HTTPStatus.FORBIDDEN
        middleware1.assert_awaited_once_with(session=mock_session)
        middleware2.assert_awaited_once_with(session=mock_session)
        middleware3.assert_not_called()


@pytest.mark.asyncio
class TestRateLimiter:

    @pytest.fixture
    def mock_session(self, mocker: MockerFixture) -> Any:
        session = mocker.Mock(spec=WebTransportSession)
        session.remote_address = ("1.2.3.4", 12345)
        return session

    @asyncio_fixture
    async def rate_limiter(self) -> AsyncGenerator[RateLimiter, None]:
        limiter = RateLimiter(max_requests=2, window_seconds=10)
        async with limiter as activated_limiter:
            yield activated_limiter

    async def test_aexit_no_cleanup_task(self) -> None:
        limiter = RateLimiter()
        limiter._cleanup_task = None

        await limiter.__aexit__(None, None, None)

        assert limiter._is_closing

    async def test_call_existing_ip(self, mock_session: Any, rate_limiter: RateLimiter) -> None:
        assert rate_limiter._lock is not None
        async with rate_limiter._lock:
            rate_limiter._requests["1.2.3.4"] = deque()

        await rate_limiter(session=mock_session)

        async with rate_limiter._lock:
            assert len(rate_limiter._requests["1.2.3.4"]) == 1

    async def test_call_no_remote_address(self, mocker: MockerFixture, rate_limiter: RateLimiter) -> None:
        session = mocker.Mock(spec=WebTransportSession)
        session.remote_address = None

        await rate_limiter(session=session)

    async def test_ip_limit_flush(self, mocker: MockerFixture, caplog: LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        mocker.patch("time.perf_counter", return_value=100.0)
        rate_limiter = RateLimiter(max_tracked_ips=2)

        async with rate_limiter as rl:
            rl._requests["1.1.1.1"] = deque([100.0])
            rl._requests["2.2.2.2"] = deque([100.0])

            session = mocker.Mock(spec=WebTransportSession)
            session.remote_address = ("3.3.3.3", 12345)

            await rl(session=session)

            assert "Rate limiter IP tracking limit (2) reached" in caplog.text
            assert "1.1.1.1" not in rl._requests
            assert "3.3.3.3" in rl._requests

    async def test_lifecycle_and_cleanup(self, mocker: MockerFixture, caplog: LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG)
        original_sleep = asyncio.sleep
        proceed_event = asyncio.Event()

        async def sleep_mock(delay: float) -> None:
            if delay > 0:
                proceed_event.set()
            await original_sleep(0)

        mocker.patch("asyncio.sleep", side_effect=sleep_mock)
        mock_time = mocker.patch("time.perf_counter")
        rate_limiter = RateLimiter(window_seconds=10, cleanup_interval=30)

        async with rate_limiter as rl:
            assert rl._lock is not None
            async with rl._lock:
                rl._requests["active_ip"] = deque([210.0])
                rl._requests["stale_ip"] = deque([100.0])
                rl._requests["empty_ip"] = deque()

            mock_time.return_value = 215.0
            await proceed_event.wait()
            await asyncio.sleep(0)

            assert "Cleaned up 2 stale IP entries" in caplog.text
            assert rl._lock is not None
            async with rl._lock:
                assert "active_ip" in rl._requests
                assert "stale_ip" not in rl._requests
                assert "empty_ip" not in rl._requests

    async def test_periodic_cleanup_empty_timestamps(self, mocker: MockerFixture) -> None:
        mocker.patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError])
        mocker.patch("time.perf_counter", return_value=100.0)

        async with RateLimiter() as rate_limiter:
            assert rate_limiter._lock is not None
            async with rate_limiter._lock:
                rate_limiter._requests["empty_ip"] = deque()

            await rate_limiter._periodic_cleanup()

            assert "empty_ip" not in rate_limiter._requests

    async def test_periodic_cleanup_exit_on_closing(self, mocker: MockerFixture) -> None:
        mocker.patch("asyncio.sleep", return_value=None)
        rate_limiter = RateLimiter()
        rate_limiter._is_closing = True
        rate_limiter._lock = mocker.MagicMock()

        await rate_limiter._periodic_cleanup()

        cast(MagicMock, rate_limiter._lock).__aenter__.assert_not_called()

    async def test_periodic_cleanup_no_stale_ips(self, mocker: MockerFixture) -> None:
        mocker.patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError])
        mock_time = mocker.patch("time.perf_counter")

        async with RateLimiter() as rate_limiter:
            assert rate_limiter._lock is not None
            async with rate_limiter._lock:
                rate_limiter._requests["active_ip"] = deque([100.0])
            mock_time.return_value = 105.0

            await rate_limiter._periodic_cleanup()

            assert "active_ip" in rate_limiter._requests

    async def test_periodic_cleanup_task_error(self, mocker: MockerFixture, caplog: LogCaptureFixture) -> None:
        mocker.patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError])

        async with RateLimiter() as rate_limiter:
            assert rate_limiter._lock is not None

            mock_lock = mocker.MagicMock()
            mock_lock.__aenter__.side_effect = ValueError("Cleanup error")
            rate_limiter._lock = mock_lock

            with pytest.raises(asyncio.CancelledError):
                await rate_limiter._periodic_cleanup()

        assert "Error in RateLimiter cleanup task: Cleanup error" in caplog.text

    async def test_rate_limiter_call_not_activated(self, mock_session: Any) -> None:
        limiter = RateLimiter()

        with pytest.raises(ServerError, match="RateLimiter has not been activated"):
            await limiter(session=mock_session)

    async def test_rate_limiting_logic(
        self, mock_session: Any, mocker: MockerFixture, caplog: LogCaptureFixture, rate_limiter: RateLimiter
    ) -> None:
        mock_time = mocker.patch("time.perf_counter")

        mock_time.return_value = 100.0
        await rate_limiter(session=mock_session)

        mock_time.return_value = 101.0
        await rate_limiter(session=mock_session)

        mock_time.return_value = 102.0
        with pytest.raises(MiddlewareRejected) as exc_info:
            await rate_limiter(session=mock_session)

        assert exc_info.value.status_code == http.HTTPStatus.TOO_MANY_REQUESTS
        headers = cast(dict[str, str], exc_info.value.headers)
        assert headers["retry-after"] == "10"
        assert "Rate limit exceeded for IP 1.2.3.4" in caplog.text

        mock_time.return_value = 110.1
        await rate_limiter(session=mock_session)

    async def test_start_cleanup_task_idempotent(self, mocker: MockerFixture) -> None:
        rate_limiter = RateLimiter()
        rate_limiter._start_cleanup_task()
        assert rate_limiter._cleanup_task is None

        mock_cleanup = mocker.Mock(return_value="dummy_coro")
        mocker.patch.object(rate_limiter, "_periodic_cleanup", new=mock_cleanup)

        mock_tg = mocker.Mock()
        mock_task = mocker.Mock()
        mock_tg.create_task.return_value = mock_task
        rate_limiter._tg = mock_tg

        rate_limiter._start_cleanup_task()

        mock_cleanup.assert_called_once()
        mock_tg.create_task.assert_called_once_with(coro="dummy_coro")

        mock_task.done.return_value = False
        rate_limiter._start_cleanup_task()

        assert mock_tg.create_task.call_count == 1

        mock_task.done.return_value = True
        rate_limiter._start_cleanup_task()

        assert mock_tg.create_task.call_count == 2



================================================
FILE: tests/unit/server/test_router.py
================================================
"""Unit tests for the pywebtransport.server.router module."""

import re
from typing import Any

import pytest
from _pytest.logging import LogCaptureFixture
from pytest_mock import MockerFixture

from pywebtransport import WebTransportSession
from pywebtransport.server import RequestRouter


class TestRequestRouter:

    @pytest.fixture
    def mock_handler(self, mocker: MockerFixture) -> Any:
        return mocker.AsyncMock()

    @pytest.fixture
    def mock_session(self, mocker: MockerFixture) -> Any:
        return mocker.create_autospec(WebTransportSession, instance=True)

    @pytest.fixture
    def router(self) -> RequestRouter:
        return RequestRouter()

    def test_add_and_get_route(self, router: RequestRouter, mock_handler: Any) -> None:
        router.add_route(path="/home", handler=mock_handler)

        assert router.get_route_handler(path="/home") is mock_handler
        assert router.get_route_handler(path="/not-found") is None
        assert router.get_all_routes() == {"/home": mock_handler}
        assert router.get_route_stats()["exact_routes"] == 1

    def test_add_invalid_pattern_route(
        self, router: RequestRouter, mock_handler: Any, caplog: LogCaptureFixture
    ) -> None:
        invalid_pattern = r"/users/(\d+"

        with pytest.raises(re.error):
            router.add_pattern_route(pattern=invalid_pattern, handler=mock_handler)

        assert router.get_route_stats()["pattern_routes"] == 0
        assert f"Invalid regex pattern '{invalid_pattern}'" in caplog.text

    def test_add_pattern_route(self, router: RequestRouter, mock_handler: Any) -> None:
        router.add_pattern_route(pattern=r"/users/(\d+)", handler=mock_handler)

        stats = router.get_route_stats()

        assert stats["pattern_routes"] == 1

    def test_add_route_duplicate_raises_error(self, router: RequestRouter, mock_handler: Any) -> None:
        router.add_route(path="/home", handler=mock_handler)

        with pytest.raises(ValueError, match="Route for path '/home' already exists"):
            router.add_route(path="/home", handler=mock_handler)

    def test_add_route_override(self, router: RequestRouter, mock_handler: Any, mocker: MockerFixture) -> None:
        router.add_route(path="/home", handler=mock_handler)
        new_handler = mocker.AsyncMock()

        router.add_route(path="/home", handler=new_handler, override=True)

        assert router.get_route_handler(path="/home") is new_handler

    def test_init(self, router: RequestRouter) -> None:
        stats = router.get_route_stats()

        assert not router.get_all_routes()
        assert stats["exact_routes"] == 0
        assert stats["pattern_routes"] == 0
        assert stats["has_default_handler"] is False

    def test_remove_pattern_route(self, router: RequestRouter, mock_handler: Any) -> None:
        pattern = r"/users/(\d+)"
        router.add_pattern_route(pattern=pattern, handler=mock_handler)

        router.remove_pattern_route(pattern=pattern)

        assert router.get_route_stats()["pattern_routes"] == 0

        router.remove_pattern_route(pattern=r"/not/found")

    def test_remove_route(self, router: RequestRouter, mock_handler: Any) -> None:
        router.add_route(path="/temp", handler=mock_handler)
        assert router.get_route_handler(path="/temp") is not None

        router.remove_route(path="/temp")

        assert router.get_route_handler(path="/temp") is None

        router.remove_route(path="/non-existent")

    def test_route_request_no_match(self, router: RequestRouter, mock_session: Any, mocker: MockerFixture) -> None:
        router.add_route(path="/home", handler=mocker.AsyncMock())
        mock_session.path = "/about"

        result = router.route_request(session=mock_session)

        assert result is None

    def test_route_request_precedence(self, router: RequestRouter, mock_session: Any, mocker: MockerFixture) -> None:
        exact_handler = mocker.AsyncMock()
        pattern_handler = mocker.AsyncMock()
        router.add_route(path="/users/profile", handler=exact_handler)
        router.add_pattern_route(pattern=r"/users/(\w+)", handler=pattern_handler)
        mock_session.path = "/users/profile"

        result = router.route_request(session=mock_session)

        assert result is not None
        handler, params = result
        assert handler is exact_handler
        assert params == {}

    @pytest.mark.parametrize(
        "path, should_find",
        [
            ("/exact", "exact_handler"),
            ("/users/123", "pattern_handler"),
            ("/items/abc/456", "multi_capture_handler"),
            ("/not-found", "default_handler"),
        ],
    )
    def test_route_request_scenarios(
        self, router: RequestRouter, mock_session: Any, path: str, should_find: str, mocker: MockerFixture
    ) -> None:
        handlers = {
            "exact_handler": mocker.AsyncMock(name="exact"),
            "pattern_handler": mocker.AsyncMock(name="pattern"),
            "multi_capture_handler": mocker.AsyncMock(name="multi_capture"),
            "default_handler": mocker.AsyncMock(name="default"),
        }
        router.add_route(path="/exact", handler=handlers["exact_handler"])
        router.add_pattern_route(pattern=r"/users/(\d+)", handler=handlers["pattern_handler"])
        router.add_pattern_route(pattern=r"/items/([a-z]+)/(\d+)", handler=handlers["multi_capture_handler"])
        router.set_default_handler(handler=handlers["default_handler"])
        mock_session.path = path

        result = router.route_request(session=mock_session)

        assert result is not None
        handler, params = result
        assert handler is handlers[should_find]
        assert params == {}



================================================
FILE: tests/unit/server/test_server.py
================================================
"""Unit tests for the pywebtransport.server.server module."""

import asyncio
from typing import Any

import pytest
from pytest_mock import MockerFixture

from pywebtransport import Event, ServerConfig, ServerError
from pywebtransport.connection import WebTransportConnection
from pywebtransport.manager import ConnectionManager, SessionManager
from pywebtransport.server import ServerDiagnostics, ServerStats, WebTransportServer
from pywebtransport.types import ConnectionState, EventType, SessionState


class TestServerDiagnostics:

    @pytest.mark.parametrize(
        "diag_kwargs, path_exists_side_effect, expected_issue_part",
        [
            ({"is_serving": False}, [True, True], "Server is not currently serving."),
            (
                {"stats": ServerStats(connections_accepted=89, connections_rejected=11)},
                [True, True],
                "High connection rejection rate",
            ),
            ({"connection_states": {ConnectionState.CONNECTED: 95}}, [True, True], "High connection usage"),
            (
                {"certfile_path": "/nonexistent/cert.pem", "cert_file_exists": False},
                [False, True],
                "Certificate file not found",
            ),
            ({"keyfile_path": "/nonexistent/key.pem", "key_file_exists": False}, [True, False], "Key file not found"),
            ({}, [True, True], None),
        ],
    )
    def test_issues_property(
        self,
        mocker: MockerFixture,
        diag_kwargs: dict[str, Any],
        path_exists_side_effect: list[bool],
        expected_issue_part: str | None,
    ) -> None:
        defaults = {
            "stats": ServerStats(),
            "connection_states": {},
            "session_states": {},
            "is_serving": True,
            "certfile_path": "cert.pem",
            "keyfile_path": "key.pem",
            "max_connections": 100,
            "cert_file_exists": True,
            "key_file_exists": True,
        }
        for k, v in defaults.items():
            if k not in diag_kwargs:
                diag_kwargs[k] = v

        mocker.patch("pathlib.Path.exists", side_effect=path_exists_side_effect)
        diagnostics = ServerDiagnostics(**diag_kwargs)

        issues = diagnostics.issues

        if expected_issue_part:
            assert any(expected_issue_part in issue for issue in issues)
        else:
            assert not issues


class TestWebTransportServer:

    @pytest.fixture
    def mock_connection_manager(self, mocker: MockerFixture) -> Any:
        mock_manager_class = mocker.patch("pywebtransport.server.server.ConnectionManager", autospec=True)
        return mock_manager_class.return_value

    @pytest.fixture
    def mock_create_server(self, mocker: MockerFixture) -> Any:
        mock_server = mocker.MagicMock()
        mock_server.close = mocker.MagicMock()
        mock_server._transport.get_extra_info.return_value = ("127.0.0.1", 4433)
        return mocker.patch(
            "pywebtransport.server.server.create_server", new_callable=mocker.AsyncMock, return_value=mock_server
        )

    @pytest.fixture
    def mock_quic_server(self, mock_create_server: Any) -> Any:
        return mock_create_server.return_value

    @pytest.fixture
    def mock_server_config(self, mocker: MockerFixture) -> ServerConfig:
        mocker.patch("pywebtransport.config.ServerConfig.validate")
        config = ServerConfig(
            bind_host="127.0.0.1", bind_port=4433, certfile="cert.pem", keyfile="key.pem", max_connections=10
        )
        config.connection_idle_timeout = 60.0
        return config

    @pytest.fixture
    def mock_session_manager(self, mocker: MockerFixture) -> Any:
        mock_manager_class = mocker.patch("pywebtransport.server.server.SessionManager", autospec=True)
        return mock_manager_class.return_value

    @pytest.fixture
    def mock_webtransport_connection(self, mocker: MockerFixture) -> Any:
        mock_conn = mocker.create_autospec(WebTransportConnection, instance=True)
        type(mock_conn).is_closed = mocker.PropertyMock(return_value=False)
        mock_conn.events = mocker.MagicMock()
        mock_conn.initialize = mocker.AsyncMock()
        mock_conn.connection_id = "test_conn_id"
        mocker.patch("pywebtransport.server.server.WebTransportConnection", return_value=mock_conn)
        return mock_conn

    @pytest.fixture
    def server(
        self, mock_server_config: ServerConfig, mock_connection_manager: Any, mock_session_manager: Any
    ) -> WebTransportServer:
        return WebTransportServer(config=mock_server_config)

    @pytest.fixture(autouse=True)
    def setup_common_mocks(self, mocker: MockerFixture) -> None:
        mocker.patch("pywebtransport.server.server.get_timestamp", side_effect=[1000.0, 1005.0])
        mocker.patch("pathlib.Path.exists", return_value=True)

    @pytest.mark.asyncio
    async def test_async_context_manager(
        self, server: WebTransportServer, mock_connection_manager: Any, mock_session_manager: Any, mocker: MockerFixture
    ) -> None:
        mock_close = mocker.patch.object(server, "close", new_callable=mocker.AsyncMock)

        async with server as s:
            assert s is server
            mock_connection_manager.__aenter__.assert_awaited_once()
            mock_session_manager.__aenter__.assert_awaited_once()

        mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_with_exception(
        self, server: WebTransportServer, mocker: MockerFixture
    ) -> None:
        mock_close = mocker.patch.object(server, "close", new_callable=mocker.AsyncMock)

        with pytest.raises(ValueError, match="Test exception"):
            async with server:
                raise ValueError("Test exception")

        mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close(
        self, server: WebTransportServer, mock_quic_server: Any, mock_connection_manager: Any, mock_session_manager: Any
    ) -> None:
        await server.listen()

        await server.close()

        mock_connection_manager.shutdown.assert_awaited_once()
        mock_session_manager.shutdown.assert_awaited_once()
        mock_quic_server.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_already_in_progress(self, server: WebTransportServer) -> None:
        async def dummy_task() -> None:
            await asyncio.sleep(0.1)

        real_task = asyncio.create_task(dummy_task())
        server._close_task = real_task
        server._serving = True

        try:
            await server.close()
        finally:
            real_task.cancel()
            try:
                await real_task
            except asyncio.CancelledError:
                pass

        assert server._serving is True

    @pytest.mark.asyncio
    async def test_close_idempotency(self, server: WebTransportServer, mock_quic_server: Any) -> None:
        await server.listen()

        await server.close()
        mock_quic_server.close.assert_called_once()

        await server.close()
        mock_quic_server.close.assert_called_once()
        assert not server.is_serving

    @pytest.mark.asyncio
    async def test_close_implementation_defensive_check_no_server(
        self, server: WebTransportServer, mock_connection_manager: Any
    ) -> None:
        server._serving = True
        server._server = None

        await server.close()

        mock_connection_manager.shutdown.assert_awaited_once()
        assert server.is_serving is False

    @pytest.mark.asyncio
    async def test_close_with_done_task(
        self, server: WebTransportServer, mock_quic_server: Any, mocker: MockerFixture
    ) -> None:
        await server.listen()
        done_task = mocker.create_autospec(asyncio.Task, instance=True)
        done_task.done.return_value = True
        not_done_task = mocker.create_autospec(asyncio.Task, instance=True)
        not_done_task.done.return_value = False
        server._background_tasks = {done_task, not_done_task}
        mock_gather = mocker.patch("asyncio.gather", new_callable=mocker.AsyncMock)

        await server.close()

        done_task.cancel.assert_not_called()
        not_done_task.cancel.assert_called_once()

        mock_gather.assert_awaited_once()
        args = mock_gather.await_args[0]
        assert set(args) == {done_task, not_done_task}

    @pytest.mark.asyncio
    async def test_close_with_finished_previous_close_task(
        self, server: WebTransportServer, mock_quic_server: Any, mocker: MockerFixture
    ) -> None:
        server._serving = True
        server._server = mock_quic_server
        done_task = mocker.create_autospec(asyncio.Task, instance=True)
        done_task.done.return_value = True
        server._close_task = done_task

        await server.close()

        assert server._close_task is not done_task
        mock_quic_server.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_manager_shutdown_error(
        self, server: WebTransportServer, mock_connection_manager: Any, mock_quic_server: Any
    ) -> None:
        await server.listen()
        mock_connection_manager.shutdown.side_effect = RuntimeError("Shutdown error")

        await server.close()

        mock_connection_manager.shutdown.assert_awaited_once()
        mock_quic_server.close.assert_called_once()

    def test_connection_manager_property(
        self, server: WebTransportServer, mock_connection_manager: ConnectionManager
    ) -> None:
        assert server.connection_manager is mock_connection_manager

    @pytest.mark.asyncio
    async def test_create_connection_callback_exception(
        self, server: WebTransportServer, mocker: MockerFixture
    ) -> None:
        mock_transport = mocker.Mock(spec=asyncio.DatagramTransport)
        mock_transport.sendto = mocker.Mock()
        mock_transport.is_closing.return_value = False
        mock_protocol = mocker.MagicMock()
        mocker.patch(
            "pywebtransport.server.server.WebTransportConnection.accept", side_effect=ValueError("Factory failed")
        )

        server._create_connection_callback(protocol=mock_protocol, transport=mock_transport)

        mock_transport.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_connection_callback_exception_closing(
        self, server: WebTransportServer, mocker: MockerFixture
    ) -> None:
        mock_transport = mocker.Mock(spec=asyncio.DatagramTransport)
        mock_transport.sendto = mocker.Mock()
        mock_transport.is_closing.return_value = True
        mock_protocol = mocker.MagicMock()
        mocker.patch(
            "pywebtransport.server.server.WebTransportConnection.accept", side_effect=ValueError("Factory failed")
        )

        server._create_connection_callback(protocol=mock_protocol, transport=mock_transport)

        mock_transport.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_connection_callback_invalid_transport(
        self, server: WebTransportServer, mocker: MockerFixture
    ) -> None:
        mock_transport = mocker.MagicMock()
        del mock_transport.sendto
        mock_transport.is_closing.return_value = False
        mock_protocol = mocker.MagicMock()

        server._create_connection_callback(protocol=mock_protocol, transport=mock_transport)

        mock_transport.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_connection_callback_invalid_transport_already_closing(
        self, server: WebTransportServer, mocker: MockerFixture
    ) -> None:
        mock_transport = mocker.Mock()
        del mock_transport.sendto
        mock_transport.close = mocker.Mock()
        mock_transport.is_closing.return_value = True
        mock_protocol = mocker.MagicMock()

        server._create_connection_callback(protocol=mock_protocol, transport=mock_transport)

        mock_transport.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_connection_callback_invalid_transport_no_close(
        self, server: WebTransportServer, mocker: MockerFixture
    ) -> None:
        mock_transport = mocker.Mock()
        del mock_transport.sendto
        del mock_transport.close
        mock_protocol = mocker.MagicMock()

        server._create_connection_callback(protocol=mock_protocol, transport=mock_transport)

    @pytest.mark.asyncio
    async def test_create_connection_callback_success(
        self, server: WebTransportServer, mocker: MockerFixture, mock_webtransport_connection: Any
    ) -> None:
        mock_transport = mocker.Mock(spec=asyncio.DatagramTransport)
        mock_transport.sendto = mocker.Mock()
        mock_protocol = mocker.MagicMock()
        mock_accept = mocker.patch(
            "pywebtransport.server.server.WebTransportConnection.accept", return_value=mock_webtransport_connection
        )
        mock_init_task = mocker.patch.object(server, "_initialize_and_register_connection")
        mock_create_task = mocker.patch("asyncio.create_task")

        server._create_connection_callback(protocol=mock_protocol, transport=mock_transport)

        mock_accept.assert_called_once_with(transport=mock_transport, protocol=mock_protocol, config=server._config)
        mock_init_task.assert_called_once()
        mock_create_task.assert_called_once()

        call_args = mock_create_task.call_args
        if call_args:
            coro = call_args.kwargs.get("coro") or call_args.args[0]
            if asyncio.iscoroutine(coro):
                coro.close()

    @pytest.mark.asyncio
    async def test_create_connection_callback_transport_already_closed(
        self, server: WebTransportServer, mocker: MockerFixture
    ) -> None:
        mock_transport = mocker.Mock()
        del mock_transport.sendto
        mock_transport.close = mocker.Mock()
        mock_transport.is_closing.return_value = True
        mock_protocol = mocker.MagicMock()

        server._create_connection_callback(protocol=mock_protocol, transport=mock_transport)

        mock_transport.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_diagnostics(
        self,
        server: WebTransportServer,
        mock_connection_manager: Any,
        mock_session_manager: Any,
        mock_quic_server: Any,
        mocker: MockerFixture,
    ) -> None:
        await server.listen()
        mock_conn = mocker.MagicMock()
        mock_conn.state = ConnectionState.CONNECTED
        mock_session = mocker.MagicMock()
        mock_session.state = SessionState.CONNECTED
        mock_connection_manager.get_all_resources = mocker.AsyncMock(return_value=[mock_conn])
        mock_session_manager.get_all_resources = mocker.AsyncMock(return_value=[mock_session])

        diagnostics = await server.diagnostics()

        assert isinstance(diagnostics, ServerDiagnostics)
        assert diagnostics.stats.to_dict()["uptime"] == 5.0
        assert diagnostics.connection_states == {ConnectionState.CONNECTED: 1}
        assert diagnostics.session_states == {SessionState.CONNECTED: 1}
        assert diagnostics.is_serving is True
        assert diagnostics.certfile_path == "cert.pem"
        assert diagnostics.keyfile_path == "key.pem"
        assert diagnostics.cert_file_exists is True
        assert diagnostics.key_file_exists is True

    @pytest.mark.asyncio
    async def test_diagnostics_before_listen(self, server: WebTransportServer) -> None:
        diagnostics = await server.diagnostics()

        assert diagnostics.stats.to_dict()["uptime"] == 0.0

    def test_init_with_custom_config(self, server: WebTransportServer, mock_server_config: ServerConfig) -> None:
        assert server.config is mock_server_config

    def test_init_with_default_config(self, mocker: MockerFixture) -> None:
        mock_config_class = mocker.patch("pywebtransport.server.server.ServerConfig", autospec=True)
        mock_config_instance = mock_config_class.return_value
        mock_config_instance.max_connections = 100
        mock_config_instance.connection_idle_timeout = 60.0
        mock_config_instance.max_sessions = 100
        mock_config_instance.max_event_queue_size = 100
        mock_config_instance.max_event_listeners = 100
        mock_config_instance.max_event_history_size = 100

        WebTransportServer(config=None)

        mock_config_class.assert_called_once_with()
        mock_config_instance.validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_and_register_connection_event_forwarding(
        self, server: WebTransportServer, mock_webtransport_connection: Any, mocker: MockerFixture
    ) -> None:
        server_emit = mocker.patch.object(server, "emit", new_callable=mocker.AsyncMock)

        await server._initialize_and_register_connection(connection=mock_webtransport_connection)

        call_args = mock_webtransport_connection.events.on.call_args
        assert call_args is not None
        handler = call_args.kwargs["handler"]

        event_data = {"session_id": "s1"}
        test_event = Event(type=EventType.SESSION_REQUEST, data=event_data)

        await handler(test_event)

        server_emit.assert_awaited_once()
        assert server_emit.await_args is not None
        emit_kwargs = server_emit.await_args.kwargs
        assert emit_kwargs["event_type"] == EventType.SESSION_REQUEST
        assert emit_kwargs["data"]["session_id"] == "s1"
        assert emit_kwargs["data"]["connection"] is mock_webtransport_connection

    @pytest.mark.asyncio
    async def test_initialize_and_register_connection_event_forwarding_nodata(
        self, server: WebTransportServer, mock_webtransport_connection: Any, mocker: MockerFixture
    ) -> None:
        server_emit = mocker.patch.object(server, "emit", new_callable=mocker.AsyncMock)
        await server._initialize_and_register_connection(connection=mock_webtransport_connection)

        call_args = mock_webtransport_connection.events.on.call_args
        assert call_args is not None
        handler = call_args.kwargs["handler"]

        test_event = Event(type=EventType.SESSION_REQUEST, data=None)
        await handler(test_event)

        server_emit.assert_awaited_once()
        assert server_emit.await_args is not None
        emit_kwargs = server_emit.await_args.kwargs
        assert emit_kwargs["data"]["connection"] is mock_webtransport_connection

    @pytest.mark.asyncio
    async def test_initialize_and_register_connection_failure(
        self,
        server: WebTransportServer,
        mock_connection_manager: Any,
        mock_webtransport_connection: Any,
        mocker: MockerFixture,
    ) -> None:
        mock_connection_manager.add_connection.side_effect = ValueError("Add failed")

        await server._initialize_and_register_connection(connection=mock_webtransport_connection)

        assert server._stats.connections_rejected == 1
        assert server._stats.connection_errors == 1
        mock_webtransport_connection.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_and_register_connection_failure_closed(
        self,
        server: WebTransportServer,
        mock_connection_manager: Any,
        mock_webtransport_connection: Any,
        mocker: MockerFixture,
    ) -> None:
        mock_connection_manager.add_connection.side_effect = ValueError("Add failed")
        type(mock_webtransport_connection).is_closed = mocker.PropertyMock(return_value=True)

        await server._initialize_and_register_connection(connection=mock_webtransport_connection)

        assert server._stats.connections_rejected == 1
        mock_webtransport_connection.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_connection_session_registration_failure(
        self,
        server: WebTransportServer,
        mock_webtransport_connection: Any,
        mock_session_manager: Any,
        mocker: MockerFixture,
    ) -> None:
        mock_logger = mocker.patch("pywebtransport.server.server.logger")
        mock_session_manager.add_session.side_effect = ValueError("Session limit reached")

        await server._initialize_and_register_connection(connection=mock_webtransport_connection)

        call_args = mock_webtransport_connection.events.on.call_args
        handler = call_args.kwargs["handler"]

        mock_session = mocker.Mock()
        mock_session.session_id = "test_sess_id"
        event = Event(type=EventType.SESSION_REQUEST, data={"session": mock_session})

        await handler(event)

        mock_logger.error.assert_called_with("Failed to register session %s: %s", "test_sess_id", mocker.ANY)

    @pytest.mark.asyncio
    async def test_initialize_and_register_connection_success(
        self,
        server: WebTransportServer,
        mock_connection_manager: Any,
        mock_webtransport_connection: Any,
        mocker: MockerFixture,
    ) -> None:
        await server._initialize_and_register_connection(connection=mock_webtransport_connection)

        mock_webtransport_connection.events.on.assert_called_once()
        mock_webtransport_connection.initialize.assert_not_awaited()
        mock_connection_manager.add_connection.assert_awaited_once_with(connection=mock_webtransport_connection)
        assert server._stats.connections_accepted == 1

        once_call = mock_webtransport_connection.events.once.call_args
        assert once_call is not None
        assert once_call.kwargs["event_type"] == EventType.CONNECTION_CLOSED
        cleanup_handler = once_call.kwargs["handler"]

        await cleanup_handler(Event(type=EventType.CONNECTION_CLOSED, data=None))
        mock_webtransport_connection.events.off.assert_called_once()

    @pytest.mark.asyncio
    async def test_listen_cert_file_not_found(
        self, server: WebTransportServer, mock_create_server: Any, mocker: MockerFixture
    ) -> None:
        mock_create_server.side_effect = FileNotFoundError("Cert missing")
        with pytest.raises(ServerError, match="Certificate/Key file error"):
            await server.listen()

    @pytest.mark.asyncio
    async def test_listen_generic_exception(
        self, server: WebTransportServer, mock_create_server: Any, mocker: MockerFixture
    ) -> None:
        mock_create_server.side_effect = Exception("Generic error")
        with pytest.raises(ServerError, match="Failed to start server"):
            await server.listen()

    @pytest.mark.asyncio
    async def test_listen_raises_error_if_already_serving(self, server: WebTransportServer) -> None:
        server._serving = True

        with pytest.raises(ServerError, match="Server is already serving"):
            await server.listen()

    @pytest.mark.asyncio
    async def test_listen_raises_error_on_create_server_failure(
        self, server: WebTransportServer, mock_create_server: Any, mocker: MockerFixture
    ) -> None:
        mock_create_server.side_effect = OSError("Address failed")

        with pytest.raises(ServerError, match="Failed to start server"):
            await server.listen()

    @pytest.mark.asyncio
    async def test_listen_success(self, server: WebTransportServer, mock_quic_server: Any) -> None:
        await server.listen()

        assert server.is_serving
        assert server.local_address == ("127.0.0.1", 4433)

    @pytest.mark.asyncio
    async def test_listen_with_explicit_host_port(self, server: WebTransportServer, mock_create_server: Any) -> None:
        await server.listen(host="1.2.3.4", port=9999)
        mock_create_server.assert_called_once()
        call_kwargs = mock_create_server.call_args.kwargs
        assert call_kwargs["host"] == "1.2.3.4"
        assert call_kwargs["port"] == 9999
        assert server.is_serving

    def test_local_address_attribute_error(self, server: WebTransportServer, mock_quic_server: Any) -> None:
        server._server = mock_quic_server
        mock_quic_server._transport.get_extra_info.side_effect = AttributeError("Missing attr")
        assert server.local_address is None

    def test_local_address_oserror(self, server: WebTransportServer, mock_quic_server: Any) -> None:
        server._server = mock_quic_server
        mock_quic_server._transport.get_extra_info.side_effect = OSError("Transport error")
        assert server.local_address is None

    def test_local_address_with_server_but_no_transport(
        self, server: WebTransportServer, mock_quic_server: Any
    ) -> None:
        server._server = mock_quic_server
        mock_quic_server._transport = None
        assert server.local_address is None

    @pytest.mark.asyncio
    async def test_serve_forever_cancelled(
        self, server: WebTransportServer, mocker: MockerFixture, mock_create_server: Any, mock_quic_server: Any
    ) -> None:
        await server.listen()
        assert server._shutdown_event is not None

        task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.01)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.result() is None

    @pytest.mark.asyncio
    async def test_serve_forever_graceful_exit(
        self, server: WebTransportServer, mock_quic_server: Any, mocker: MockerFixture
    ) -> None:
        await server.listen()

        async def trigger_shutdown() -> None:
            await asyncio.sleep(0.01)
            await server.close()

        asyncio.create_task(trigger_shutdown())
        await server.serve_forever()
        assert not server.is_serving

    @pytest.mark.asyncio
    async def test_serve_forever_keyboard_interrupt(
        self, server: WebTransportServer, mock_quic_server: Any, mocker: MockerFixture
    ) -> None:
        await server.listen()
        assert server._shutdown_event is not None

        mocker.patch.object(server._shutdown_event, "wait", side_effect=KeyboardInterrupt)

        with pytest.raises(KeyboardInterrupt):
            await server.serve_forever()

    @pytest.mark.asyncio
    async def test_serve_forever_not_listening(self, server: WebTransportServer) -> None:
        with pytest.raises(ServerError, match="Server is not listening"):
            await server.serve_forever()

    @pytest.mark.asyncio
    async def test_serve_forever_wait_exception(
        self, server: WebTransportServer, mock_quic_server: Any, mocker: MockerFixture
    ) -> None:
        await server.listen()
        assert server._shutdown_event is not None
        mock_logger_error = mocker.patch("pywebtransport.server.server.logger.error")

        mocker.patch.object(server._shutdown_event, "wait", side_effect=ValueError("Wait error"))

        await server.serve_forever()

        mock_logger_error.assert_called_with("Error during serve_forever wait: %s", mocker.ANY)

    def test_session_manager_property(self, server: WebTransportServer, mock_session_manager: SessionManager) -> None:
        assert server.session_manager is mock_session_manager

    def test_str_representation(
        self, server: WebTransportServer, mock_quic_server: Any, mock_connection_manager: Any, mock_session_manager: Any
    ) -> None:
        server._serving = True
        server._server = mock_quic_server
        mock_connection_manager.__len__.return_value = 5
        mock_session_manager.__len__.return_value = 2

        representation = str(server)

        assert "status=serving" in representation
        assert "address=127.0.0.1:4433" in representation
        assert "connections=5" in representation
        assert "sessions=2" in representation

    def test_str_representation_not_serving(self, server: WebTransportServer) -> None:
        representation = str(server)

        assert "status=stopped" in representation
        assert "address=unknown" in representation


