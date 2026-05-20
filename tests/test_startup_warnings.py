import logging


def test_edinet_tools_import_is_lazy_without_api_key(monkeypatch):
    from src import edinet_client

    monkeypatch.setattr(edinet_client, "edinet_tools", None)
    monkeypatch.setattr(edinet_client, "_import_attempted", False)
    monkeypatch.setattr(edinet_client, "get_edinet_api_key", lambda: "")

    assert edinet_client.is_configured() is False
    assert edinet_client._import_attempted is False


def test_app_logger_does_not_duplicate_via_root_propagation():
    from src.log_config import get_logger

    name = "tests.startup_warning_logger"
    logging.getLogger(name).handlers.clear()

    logger = get_logger(name)
    handler_count = len(logger.handlers)
    same_logger = get_logger(name)

    assert logger.propagate is False
    assert same_logger is logger
    assert len(logger.handlers) == handler_count == 1
