import pytest
from unittest.mock import MagicMock, patch
from babelfish_stt.server import BabelfishH3Protocol
from aioquic.h3.events import HeadersReceived, WebTransportStreamDataReceived

class MockQuicConfiguration:
    def __init__(self):
        self.is_client = False

class MockQuicConnection:
    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 8123
        self.configuration = MockQuicConfiguration()

@pytest.fixture
def mock_server():
    return MagicMock()

@pytest.fixture
def protocol(mock_server):
    # We need to mock QuicConnectionProtocol.__init__ as it expects a connection
    with patch("aioquic.asyncio.QuicConnectionProtocol.__init__", return_value=None):
        proto = BabelfishH3Protocol()
        proto._quic = MockQuicConnection()
        proto.babelfish_server = mock_server
        # Mock H3Connection
        proto._h3 = MagicMock()
        return proto

def test_protocol_init(mock_server):
    with patch("aioquic.asyncio.QuicConnectionProtocol.__init__", return_value=None):
        proto = BabelfishH3Protocol()
        proto._quic = MagicMock()
        # Trigger initialization
        with patch("babelfish_stt.server.H3Connection") as mock_h3_class:
            proto.quic_event_received(MagicMock())
            assert proto._h3 is not None
            mock_h3_class.assert_called_once_with(proto._quic, enable_webtransport=True)

def test_handle_h3_event_headers_webtransport(protocol):
    event = HeadersReceived(
        headers=[
            (b":method", b"CONNECT"),
            (b":protocol", b"webtransport"),
            (b":path", b"/config"),
        ],
        stream_id=0,
        stream_ended=False
    )
    
    protocol._handle_h3_event(event)
    
    # Verify send_headers was called with 200 OK
    protocol._h3.send_headers.assert_called_once()
    args, kwargs = protocol._h3.send_headers.call_args
    headers = kwargs.get("headers") or args[1]
    header_dict = dict(headers)
    assert header_dict[b":status"] == b"200"
    assert b"sec-webtransport-http3-draft" in header_dict
    assert protocol._session_id == 0

def test_handle_h3_event_data(protocol, mock_server):
    protocol._session_id = 0
    event = WebTransportStreamDataReceived(
        data=b"test data",
        session_id=0,
        stream_id=4,
        stream_ended=False
    )
    
    protocol._handle_h3_event(event)
    
    # Verify server.on_data_received was called (we'll define this interface)
    mock_server.on_data_received.assert_called_once_with(4, b"test data")
