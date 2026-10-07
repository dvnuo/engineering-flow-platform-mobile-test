"""BrowserStack's video link answers with an error until the file has landed
on its storage: the download waits for a real video and never keeps an
answer that is not one."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from mobiletest import session

MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x00" * 2048
DENIED = b'<?xml version="1.0"?><Error><Code>AccessDenied</Code><Message>not authorized to perform s3:ListBucket</Message></Error>'


class Storage(BaseHTTPRequestHandler):
    answers = []  # per request: denied-200, denied-403, or video

    def do_GET(self):
        kind = self.answers.pop(0) if self.answers else "video"
        if kind == "video":
            body, status, ctype = MP4, 200, "video/mp4"
        elif kind == "denied-403":
            body, status, ctype = DENIED, 403, "application/xml"
        else:
            body, status, ctype = DENIED, 200, "application/xml"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    server = HTTPServer(("127.0.0.1", 0), Storage)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/video.mp4"
    server.shutdown()


def test_the_download_waits_for_the_video_and_keeps_only_a_video(tmp_path, storage):
    Storage.answers = ["denied-200", "denied-403", "video"]
    path = tmp_path / "video.mp4"
    assert session.download(storage, str(path), wait=5, poll=0.05) == str(path)
    assert path.read_bytes() == MP4


def test_an_answer_that_never_becomes_a_video_is_reported_not_kept(tmp_path, storage):
    Storage.answers = ["denied-200"] * 50
    path = tmp_path / "video.mp4"
    with pytest.raises(session.VideoUnavailable) as caught:
        session.download(storage, str(path), wait=0.3, poll=0.05)
    assert "AccessDenied" in str(caught.value) and not path.exists()
    with pytest.raises(session.VideoUnavailable):
        session.download("", str(path), wait=0)
