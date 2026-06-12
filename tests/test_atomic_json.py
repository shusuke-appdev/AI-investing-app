from concurrent.futures import ThreadPoolExecutor

from src.storage.atomic_json import read_json, update_json


def test_atomic_json_keeps_concurrent_updates(tmp_path):
    path = tmp_path / "items.json"

    def append_item(item: int) -> None:
        update_json(path, [], lambda items: [*items, item])

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append_item, range(40)))

    assert sorted(read_json(path, [])) == list(range(40))
