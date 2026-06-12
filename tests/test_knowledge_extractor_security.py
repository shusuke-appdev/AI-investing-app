import socket
from types import SimpleNamespace

from src import knowledge_extractor


def test_extract_from_url_rejects_private_network(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))
        ],
    )

    result = knowledge_extractor.extract_from_url("http://internal.example/report")

    assert "非公開ネットワーク" in result


def test_extract_from_url_rejects_private_redirect(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )
    redirect = SimpleNamespace(url="http://127.0.0.1/admin")
    response = SimpleNamespace(
        url="https://example.com/final",
        history=[redirect],
        headers={"Content-Type": "text/html"},
        raise_for_status=lambda: None,
        iter_content=lambda chunk_size: iter([b"<html><body>ok</body></html>"]),
    )
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: response)

    result = knowledge_extractor.extract_from_url("https://example.com/report")

    assert "非公開ネットワーク" in result


def test_extract_from_file_rejects_large_or_unsupported_upload():
    oversized = b"x" * (knowledge_extractor.MAX_UPLOAD_BYTES + 1)

    assert "上限" in knowledge_extractor.extract_from_file(oversized, "report.txt")
    assert "未対応" in knowledge_extractor.extract_from_file(b"data", "report.exe")
