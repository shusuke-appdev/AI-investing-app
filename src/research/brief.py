"""Source-labelled Markdown for Codex, using saved calculations without acquisition."""

from __future__ import annotations

import math
from collections import Counter
from urllib.parse import urlsplit


def _text(value) -> str:
    return (
        str(value if value is not None else "未確認")
        .replace("\n", " ")
        .replace("|", "\\|")
    )


def _number(value, unit="%") -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "未確認"
    return f"{value:+.1f}{unit}" if math.isfinite(value) else "未確認"


def _table(headers, rows) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(_text(v) for v in row) + " |" for row in rows),
        "",
    ]


def _ranked(rows, key, limit=5):
    values = [
        r
        for r in rows
        if isinstance(r.get(key), (int, float))
        and not isinstance(r[key], bool)
        and math.isfinite(r[key])
    ]
    return sorted(values, key=lambda r: -r[key])[:limit]


def render_brief(bundle: dict, markets: tuple[str, ...] = ("US", "JP")) -> str:
    """Expose the two top-down questions in text; do not infer missing evidence."""
    sections = bundle["sections"]
    lines = [
        "# Codex投資リサーチ / 保存済み観測",
        "",
        f"保存run: {_text(bundle['run_id'])} / 作成: {_text(bundle['created_at'])}",
        "作成日時は価格の観測日・資料確認日とは別です。閲覧では取得しません。",
        "",
    ]
    for market in markets:
        packet = sections.get("markets", {}).get(market, {})
        if not packet and bundle["inputs"].get("market") == market:
            packet = sections.get("market", {})
        analysis = packet.get("analysis", {})
        data = analysis.get("topdown", {})
        lines.extend([f"## {'米国' if market == 'US' else '日本'}", ""])
        if not data:
            lines.extend(
                [
                    "地合い・業種の保存入力がありません。未取得を中立や0に置き換えません。",
                    "",
                ]
            )
            continue
        lines.extend(["### ① 市場の地合い", ""])
        lines.extend(
            _table(
                ["指数", "観測日", "中期基調", "短期位置", "200日線乖離", "20日線乖離"],
                [
                    [
                        r.get("name"),
                        r.get("observed_on"),
                        r.get("label"),
                        r.get("short_term"),
                        _number(r.get("ma_gaps", {}).get("200")),
                        _number(r.get("ma_gaps", {}).get("20")),
                    ]
                    for r in data.get("indices", [])
                ],
            )
        )
        sample = data.get("breadth", {})
        latest = sample.get("latest", {})
        lines.append(
            f"市場参加: {_text(sample.get('scope'))} / 観測 {_text(latest.get('date'))} / "
            f"登録{sample.get('registered_count', '未確認')}銘柄。全市場の統計ではありません。"
        )
        for key, label in [
            ("above_50", "50日線上"),
            ("above_200", "200日線上"),
            ("near_high", "52週高値圏"),
            ("near_low", "52週安値圏"),
        ]:
            count = latest.get("counts", {}).get(key, {})
            lines.append(
                f"- {label}: {_number(latest.get(key))} "
                f"({count.get('numerator', '未確認')}/{count.get('denominator', '未確認')})"
            )
        lines.extend(["", "### ② 強い業種・テーマと勢いの変化", ""])
        relative = data.get("benchmark_status") != "unavailable"
        if not relative:
            lines.extend(
                [
                    "市場相対順位は基準系列の不足・価格不整合により判定不能。以下の絶対騰落は相対順位の代替ではありません。",
                    "",
                ]
            )
        sector_rows = []
        for row in data.get("sectors", []):
            periods = row.get("periods", {})
            sector_rows.append(
                {
                    **row,
                    "metric": periods.get("6m", {}).get(
                        "relative_return" if relative else "return"
                    ),
                }
            )
        lines.extend(
            _table(
                [
                    "業種ETF・代理",
                    "6か月相対pp" if relative else "6か月絶対騰落",
                    "1か月騰落",
                    "観測日",
                    "状態",
                ],
                [
                    [
                        r.get("name"),
                        _number(r["metric"], "pp" if relative else "%"),
                        _number(r.get("periods", {}).get("1m", {}).get("return")),
                        r.get("trend", {}).get("observed_on"),
                        r.get("status"),
                    ]
                    for r in _ranked(sector_rows, "metric")
                ],
            )
        )
        theme = sections.get("themes", {}).get(market, {})
        if not theme and bundle["inputs"].get("market") == market:
            theme = sections.get("theme", {})
        ranking = theme.get("ranking", {})
        items = ranking.get("items", [])
        key = "relative_6m" if relative else "performance_6m"
        lines.extend(
            _table(
                [
                    "登録テーマ",
                    "6か月相対pp" if relative else "6か月絶対騰落",
                    "1か月騰落",
                    "1週騰落",
                    "代表銘柄（推奨ではない）",
                ],
                [
                    [
                        r.get("theme"),
                        _number(r.get(key), "pp" if relative else "%"),
                        _number(r.get("performance_1m")),
                        _number(r.get("performance_1w")),
                        ", ".join(r.get("representative_tickers", [])[:3]),
                    ]
                    for r in _ranked(items, key)
                ],
            )
        )
        improving = [
            {**r, "acceleration": r.get("rotation", {}).get("acceleration")}
            for r in items
        ]
        improving = [
            r for r in _ranked(improving, "acceleration") if r["acceleration"] > 0
        ]
        if relative and improving:
            lines.extend(["勢いが改善中のテーマ（中期の強さとは別）:", ""])
            lines.extend(
                _table(
                    ["テーマ", "6か月相対pp", "1か月相対の21営業日前比", "状態"],
                    [
                        [
                            r.get("theme"),
                            _number(r.get("relative_6m"), "pp"),
                            _number(r["acceleration"], "pp"),
                            r.get("rotation", {}).get("quadrant"),
                        ]
                        for r in improving
                    ],
                )
            )
        lines.extend(["### 反証・不足・次の確認", ""])
        for text in data.get("summary", []):
            lines.append(f"- {_text(text)}")
        for row in data.get("sectors", []):
            if row.get("status") in {"unavailable", "stale"}:
                lines.append(
                    f"- 業種 {_text(row.get('name'))}: {_text(row.get('status'))} / {_text(row.get('reason'))}"
                )
        for row in analysis.get("connected", {}).get("observations", []):
            if row.get("id") in {
                "DGS10:level",
                "JP10:level",
                "credit:level",
                "vix:level",
            }:
                lines.append(
                    f"- {_text(row.get('label'))}: {_number(row.get('value'), ' ' + str(row.get('unit', '')))} / 観測 {_text(row.get('observed_on'))} / {_text(row.get('quality'))}"
                )
        financial = analysis.get("quarterly_fundamentals", {})
        if financial:
            counts = dict(
                Counter(r.get("status", "unavailable") for r in financial.values())
            )
            lines.append(
                f"- 自動業績データの状態: {_text(counts)}。取得と原資料確認は別工程。確認済み判定はその元の期間に限定。"
            )
        lines.extend(
            [
                "- 中期基調と短期位置、テーマの相対優位と改善を分けて確認。欠損を合格条件にしません。",
                "- 1日/1週/1か月/3か月/6か月/1年は1/5/21/63/126/252営業日。中央値・登録標本・ETF代理による研究値です。",
                f"- 算定入力: /sections/markets/{market}/analysis/topdown （単一市場旧形式は /sections/market/analysis）。",
                "",
                "出典（観測日・取得日を保持）:",
            ]
        )
        sources = [*data.get("indices", []), data.get("benchmark_evidence", {})]
        for row in sources:
            url = row.get("source", "")
            parsed = urlsplit(url)
            if (
                parsed.scheme in {"https", "http"}
                and parsed.hostname
                and not parsed.username
            ):
                lines.append(
                    f"- <{url}> / 観測 {_text(row.get('observed_on'))} / 取得 {_text(row.get('fetched_at'))} / {_text(row.get('price_basis'))}"
                )
        lines.append("")
    lines.append(
        "調査用の観測であり、売買指示ではありません。保存済み会計・評価の資料確認日は更新していません。"
    )
    return "\n".join(lines) + "\n"
