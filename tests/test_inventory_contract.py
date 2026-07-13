from pathlib import Path

import tomllib


def test_inventory_lists_every_test_file_exactly_once():
    inventory_path = Path(__file__).with_name("test_inventory.toml")
    inventory = tomllib.loads(inventory_path.read_text(encoding="utf-8"))
    listed = [filename for suite in inventory["suite"] for filename in suite["files"]]
    actual = sorted(path.name for path in inventory_path.parent.glob("test_*.py"))

    assert len(listed) == len(set(listed)), "test inventory contains duplicates"
    assert sorted(listed) == actual


def test_inventory_uses_supported_classifications():
    inventory_path = Path(__file__).with_name("test_inventory.toml")
    suites = tomllib.loads(inventory_path.read_text(encoding="utf-8"))["suite"]

    assert {suite["nature"] for suite in suites} <= {
        "unit",
        "contract",
        "integration",
    }
    assert {suite["profile"] for suite in suites} <= {"standard", "slow"}
    assert all(suite["role"] and suite["limitations"] for suite in suites)
