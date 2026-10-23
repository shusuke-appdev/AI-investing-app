"""Evidence connections: deterministic conditional readings, never a vote/score."""

from __future__ import annotations

import math

KINDS = {"supports", "weakens", "different_horizon", "reference", "incomparable"}


def validate_connected(value: dict) -> None:
    from datetime import date

    if not isinstance(value, dict) or value.get("version") != "connected-market-v1":
        raise ValueError("Invalid connected analysis version")
    rows = value.get("observations")
    if not isinstance(rows, list) or not isinstance(value.get("relations"), list):
        raise ValueError("Invalid connected analysis shape")
    identifiers = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"]
            or row["id"] in identifiers
        ):
            raise ValueError("Invalid observation identity")
        identifiers.add(row["id"])
        number = row.get("value")
        if number is not None and (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(number)
        ):
            raise ValueError("Invalid observation value")
        if row.get("market") not in {"US", "JP"} or row.get("quality") not in {
            "available",
            "stale",
            "unavailable",
        }:
            raise ValueError("Invalid observation scope/quality")
        if (
            not isinstance(row.get("parents"), list)
            or not row["parents"]
            or any(not isinstance(p, str) for p in row["parents"])
        ):
            raise ValueError("Invalid observation parent inputs")
        if not all(
            isinstance(row.get(k), str) and row[k]
            for k in ("unit", "window", "series_id")
        ):
            raise ValueError("Missing observation definition")
        if row.get("observed_on") is not None:
            date.fromisoformat(row["observed_on"])
        if row["quality"] == "available" and (
            row.get("value") is None
            or not isinstance(row.get("source"), str)
            or not row["source"].startswith("https://")
            or not row.get("observed_on")
            or not row.get("price_basis")
            or row.get("period_end") != row["observed_on"]
        ):
            raise ValueError("Unconfirmed observation provenance")
    for edge in value["relations"]:
        if not isinstance(edge, dict) or edge.get("kind") not in KINDS:
            raise ValueError("Invalid evidence relation")
        if edge["kind"] in {"supports", "weakens", "different_horizon"} and (
            edge.get("from") not in identifiers or edge.get("to") not in identifiers
        ):
            raise ValueError("Missing related observation")


def relationship(
    left: dict, right: dict, *, same_window: bool = True, reference: bool = False
) -> str:
    """No match from presence alone; metadata/quality are part of the evidence."""

    def valid(row):
        value = row.get("value")
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and row.get("quality") == "available"
            and row.get("observed_on")
            and row.get("source")
            and row.get("parents")
        )

    if not valid(left) or not valid(right):
        return "incomparable"
    if reference or left.get("market") != right.get("market"):
        return "reference"
    if left.get("observed_on") != right.get("observed_on"):
        return "incomparable"
    if left.get("window") != right.get("window"):
        return "different_horizon" if not same_window else "incomparable"
    if not left.get("period_start") or left.get("period_start") != right.get(
        "period_start"
    ):
        return "incomparable"
    if set(left["parents"]) & set(right["parents"]):
        return "reference"  # Not independent confirmations of the same price/VIX.
    product = left["value"] * right["value"]
    return "supports" if product > 0 else "weakens" if product < 0 else "reference"


def connect(observations: list[dict], themes: list[dict]) -> dict:
    rows = {row["id"]: row for row in observations}
    market = rows.get("index:return_6m", {}).get("market", "US")
    specifications = [
        (
            "index:return_6m",
            "participation:rsp"
            if "participation:rsp" in rows
            else "participation:sample",
            "広い参加",
            "等加重対時価加重は参加の代理。構成・規模の違いも別の説明です。",
            "限定母集団とIWM/SPY、テーマ内部も確認",
            True,
        ),
        (
            "index:ma200_gap",
            "index:ma20_gap",
            "中期と短期",
            "中期基調と短期の価格位置は時間軸が異なります。",
            "20日線・直近高安と出来高、公式イベントを再確認",
            False,
        ),
        (
            "index:credit_aligned_1m"
            if "index:credit_aligned_1m" in rows
            else "index:return_1m",
            "credit:index_aligned_1m"
            if "credit:index_aligned_1m" in rows
            else "credit:change_1m",
            "価格と信用",
            "信用拡大は株式に逆風となる仮説。成長期待・発行体構成も別の説明です。",
            "信用スプレッドの反転と同じ日付の指数を確認",
            True,
        ),
        (
            "vix:credit_aligned_1m"
            if "vix:credit_aligned_1m" in rows
            else "vix:change_1m",
            "credit:vix_aligned_1m"
            if "credit:vix_aligned_1m" in rows
            else "credit:change_1m",
            "ボラと信用の不一致",
            "VIXは価格方向ではありません。オプションと社債は対象が異なります。",
            "VIX期間構造と信用の観測日を別々に確認",
            True,
        ),
        (
            "DGS10:change_1m",
            "DFII10:change_1m",
            "名目と実質金利",
            "金利変化を株安の原因と断定しません。実質と名目の差も検討対象です。",
            "実質金利・会社の資金調達と成長仮定を確認",
            True,
        ),
        (
            "JPY=X:return_1m",
            "CL=F:return_1m",
            "為替と原油",
            "輸出採算・輸入コストの感応度は会社ごとに異なります。",
            "テーマの相対騰落と会社のヘッジ・調達を原資料で確認",
            True,
        ),
    ]
    relationships = []
    interpretations = {
        "広い参加": {
            "supports": "指数と等加重の相対方向が一致。ただし等加重の優位だけで全銘柄の参加は確認できません。",
            "weakens": "指数と等加重の相対方向が不一致。指数上昇時の等加重劣後なら、少数大型株への集中を疑い、広い基調の裏付けを弱めます。",
        },
        "中期と短期": {
            "different_horizon": "200日線と20日線は別の時間軸。中期が上・短期が下なら、中期基調の崩壊ではなく調整の可能性を別に検討。逆の場合は短期反発と中期回復を区別。"
        },
        "価格と信用": {
            "supports": "株価方向と信用の縮小・拡大が仮説上は対応。ただし景気・発行体構成が異なり、価格を予測する証拠ではありません。",
            "weakens": "株価と信用の方向が不一致。株価上昇中の信用拡大なら、株式の楽観と資金調達リスクを同時に確認します。",
            "reference": "米国信用は日本株の外部環境参考。国内の実需給・企業の調達条件を代替しません。",
        },
        "ボラと信用の不一致": {
            "reference": "VIX低下中でも信用が拡大していれば安心材料にまとめません。VIX上昇・信用縮小なら短期ヘッジ需要と中期信用を別々に追います。"
        },
        "名目と実質金利": {
            "supports": "名目と実質が同方向。両方上昇なら割引率の負担を仮説として検討し、企業の利益成長による相殺も確認。両方低下でも景気懸念を除外できません。",
            "weakens": "名目と実質が異方向。期待物価や需給の変化も別の説明となり、単純な金利高・株安へ結びません。",
        },
        "為替と原油": {
            "supports": "USD/JPYと原油が同方向。円安・原油高なら円建て輸入コストの負担を仮説として検討し、輸出企業の採算効果とは分けます。",
            "weakens": "為替と原油が逆方向。円換算調達コストが相殺される可能性を調べますが、変化率だけで実際のコストは算定しません。",
        },
    }
    for a, b, title, alternative, next_check, same_window in specifications:
        left, right = rows.get(a, {}), rows.get(b, {})
        # Credit increase is not support for rising equity; preserve raw positive bp.
        oriented = (
            {**right, "value": -right["value"]}
            if a.startswith("index:")
            and b.startswith("credit:")
            and isinstance(right.get("value"), (int, float))
            else right
        )
        kind = relationship(left, oriented, same_window=same_window)
        if b == "participation:sample":
            kind = relationship(left, right, reference=True)
        if a.startswith("vix:") and kind != "incomparable":
            kind = "reference"  # Different asset scope; no independent bullish vote.
        relationships.append(
            {
                "id": title,
                "scope": "米国参考"
                if market == "JP" and left.get("market") == right.get("market") == "US"
                else "外部環境参考"
                if left.get("market") != right.get("market")
                else market,
                "from": a,
                "to": b,
                "kind": kind,
                "observation": " / ".join(
                    f"{r.get('label', identifier)}: {format(r['value'], '.2f') if isinstance(r.get('value'), (int, float)) else '未確認'} {r.get('unit', '')}（{r.get('observed_on') or '日付未確認'}）"
                    for identifier, r in [(a, left), (b, right)]
                ),
                "conditional": "限定母集団の200日線上比率は水準。指数の6か月リターンとは時間軸・尺度が異なる参考で、独立の方向確認として加算しません。"
                if b == "participation:sample" and kind != "incomparable"
                else interpretations.get(title, {}).get(
                    kind, "参考または変化なし。独立の裏付けとして加算しません。"
                )
                if kind != "incomparable"
                else "対象・構成期間・観測日・品質を照合できないため、方向の一致や不一致を判断しません。",
                "alternative": "登録母集団の偏り・取得不足があり得ます。全市場の参加状況ではありません。"
                if b == "participation:sample"
                else alternative,
                "invalidation": "入力の更新、価格基準の不整合、対象・期間の不一致で解釈を無効化。",
                "next_check": "限定母集団の取得率・テーマ内部・同期間の参加状況を確認"
                if b == "participation:sample"
                else next_check,
            }
        )
    relationships.append(
        {
            "id": "テーマ内部",
            "from": "themes",
            "to": "members",
            "kind": "reference" if themes else "incomparable",
            "observation": "テーマ中央値と代表銘柄の同期間リターンを比較。",
            "conditional": "上位テーマでも個別株の主条件・財務・評価の成立を意味しません。",
            "alternative": "少数銘柄への集中・登録母集団の偏り・取得不足の可能性。",
            "invalidation": "取得率60%未満、必要銘柄数未達、期間が不一致なら順位対象外。",
            "next_check": "代表銘柄の散らばり→保存済み主条件→企業資料を確認",
        }
    )
    return {
        "version": "connected-market-v1",
        "observations": observations,
        "relations": relationships,
        "scenarios": relationships,
        "independence": "親入力を共有する派生分析は独立の裏付けとして数えません。総合点・予測確率は算定しません。",
    }
