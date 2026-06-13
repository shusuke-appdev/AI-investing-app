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
    response = SimpleNamespace(
        is_redirect=True,
        is_permanent_redirect=False,
        headers={"Location": "http://127.0.0.1/admin"},
        raise_for_status=lambda: None,
        iter_content=lambda chunk_size: iter([b"<html><body>ok</body></html>"]),
        close=lambda: None,
    )
    calls = []
    monkeypatch.setattr(
        "requests.get", lambda url, **kwargs: calls.append(url) or response
    )

    result = knowledge_extractor.extract_from_url("https://example.com/report")

    assert "非公開ネットワーク" in result
    assert calls == ["https://example.com/report"]


def test_public_mode_rejects_url_before_network_request(monkeypatch):
    monkeypatch.setenv("APP_MODE", "public_readonly")
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("network request was made")
        ),
    )

    result = knowledge_extractor.extract_from_url("https://example.com/report")

    assert "公開読み取り専用モード" in result


def test_extract_from_file_rejects_large_or_unsupported_upload():
    oversized = b"x" * (knowledge_extractor.MAX_UPLOAD_BYTES + 1)

    assert "上限" in knowledge_extractor.extract_from_file(oversized, "report.txt")
    assert "未対応" in knowledge_extractor.extract_from_file(b"data", "report.exe")
