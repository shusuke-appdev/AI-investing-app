from types import SimpleNamespace
from unittest.mock import Mock

from src import gemini_client


def test_grounded_structured_uses_one_interaction_and_keeps_annotation_urls(
    monkeypatch,
):
    interaction = SimpleNamespace(
        model="gemini-test",
        usage=SimpleNamespace(
            total_input_tokens=12,
            total_output_tokens=8,
            total_tokens=20,
        ),
        steps=[
            SimpleNamespace(
                type="google_search_call",
                arguments=SimpleNamespace(queries=["q1", "q2"]),
            ),
            SimpleNamespace(
                type="model_output",
                content=[
                    SimpleNamespace(
                        text='{"items": [{"ticker": "NVDA"}]}',
                        annotations=[
                            SimpleNamespace(
                                url="https://www.sec.gov/example",
                                title="filing",
                                start_index=0,
                                end_index=10,
                            )
                        ],
                    )
                ],
            ),
        ],
    )
    client = Mock()
    client.interactions.create.return_value = interaction
    monkeypatch.setattr(gemini_client, "ai_generation_enabled", lambda: True)
    monkeypatch.setattr(gemini_client, "get_gemini_client", lambda: client)

    schema = {"type": "object", "properties": {"items": {"type": "array"}}}
    result = gemini_client.generate_grounded_structured(
        "prompt",
        schema,
        model="gemini-test",
        max_retries=1,
    )

    assert result["status"] == "available"
    assert result["data"]["items"][0]["ticker"] == "NVDA"
    assert result["citations"][0]["url"] == "https://www.sec.gov/example"
    assert result["search_query_count"] == 2
    assert result["total_tokens"] == 20
    client.interactions.create.assert_called_once_with(
        model="gemini-test",
        input="prompt",
        tools=[{"type": "google_search"}],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        },
        store=False,
        timeout=90,
    )


def test_grounded_structured_does_not_promote_json_only_url(monkeypatch):
    interaction = SimpleNamespace(
        model="gemini-test",
        usage=None,
        steps=[
            SimpleNamespace(
                type="model_output",
                content=[
                    SimpleNamespace(
                        text='{"url": "https://not-cited.example"}', annotations=[]
                    )
                ],
            )
        ],
    )
    client = Mock()
    client.interactions.create.return_value = interaction
    monkeypatch.setattr(gemini_client, "ai_generation_enabled", lambda: True)
    monkeypatch.setattr(gemini_client, "get_gemini_client", lambda: client)

    result = gemini_client.generate_grounded_structured(
        "prompt", {"type": "object"}, max_retries=1
    )

    assert result["data"]["url"] == "https://not-cited.example"
    assert result["citations"] == []
    assert result["warnings"] == ["検索引用を取得できませんでした。"]
