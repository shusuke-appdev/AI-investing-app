"""Compatibility shims for pandas-datareader on the pinned Python stack."""

from __future__ import annotations

import inspect
from typing import Any


def import_pandas_datareader_data() -> Any:
    """Import pandas_datareader.data after patching pandas 3 decorator drift."""

    from pandas.util import _decorators

    original = _decorators.deprecate_kwarg
    parameters = list(inspect.signature(original).parameters)
    if parameters[:1] == ["klass"]:

        def compat_deprecate_kwarg(
            old_arg_name: str,
            new_arg_name: str | None = None,
            mapping: Any = None,
            stacklevel: int = 2,
        ):
            return original(
                FutureWarning,
                old_arg_name,
                new_arg_name,
                mapping=mapping,
                stacklevel=stacklevel,
            )

        _decorators.deprecate_kwarg = compat_deprecate_kwarg

    from pandas_datareader import data as pdr_data

    return pdr_data
