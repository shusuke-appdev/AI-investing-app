"""Latest-request guards for asynchronous Reflex state events."""


def is_current_request(
    *,
    current_id: int,
    current_key: str,
    request_id: int,
    request_key: str,
) -> bool:
    """Return whether an async result still belongs to the active UI request."""

    return current_id == request_id and current_key == request_key
