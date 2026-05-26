from src import network


def test_get_session_keeps_cache_names_separate(monkeypatch, tmp_path):
    network.clear_sessions()
    monkeypatch.setattr(network, "default_http_cache_dir", lambda: tmp_path)

    quotes = network.get_session("quotes", expire_after=60)
    fundamentals = network.get_session("fundamentals", expire_after=3_600)
    quotes_again = network.get_session("quotes", expire_after=60)

    info = network.session_cache_info()

    assert quotes is quotes_again
    assert quotes is not fundamentals
    assert info["session_count"] == 2
    assert info["cache_dir"] == str(tmp_path)

    network.clear_sessions()
