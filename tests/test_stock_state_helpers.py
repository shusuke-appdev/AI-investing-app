from frontend.state.stock_state import (
    SmartCriteria,
    plain_state_value,
    smart_criteria_from_mapping,
)


class FakeProxy:
    def __init__(self, wrapped):
        self.__wrapped__ = wrapped


def test_plain_state_value_unwraps_proxy_containers():
    proxied = FakeProxy({"ticker": "AAPL", "nested": [{"value": 1}], "pair": (1, 2)})

    assert plain_state_value(proxied) == {
        "ticker": "AAPL",
        "nested": [{"value": 1}],
        "pair": [1, 2],
    }


def test_smart_criteria_from_mapping_keeps_state_model_type():
    criteria = smart_criteria_from_mapping(
        {
            "all_met": True,
            "S": {"met": True, "desc": "Sales", "value": "30%"},
            "M": {"met": True, "desc": "Margin", "value": "35%"},
        }
    )

    assert isinstance(criteria, SmartCriteria)
    assert criteria.all_met is True
    assert criteria.S.met is True
    assert criteria.M.value == "35%"
    assert smart_criteria_from_mapping(None) == SmartCriteria()
