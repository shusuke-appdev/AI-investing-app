"""Fixed playbooks for qualitative market-state decisions."""

from __future__ import annotations

from typing import Any

from src.advisor.ibd_market_regime import (
    REGIME_CONFIRMED_UPTREND,
    REGIME_MARKET_IN_CORRECTION,
    REGIME_RALLY_ATTEMPT,
    REGIME_UPTREND_UNDER_PRESSURE,
)

PLAYBOOKS: dict[str, dict[str, Any]] = {
    REGIME_CONFIRMED_UPTREND: {
        "stance": "リスクオン。ただし広く買うのではなく、出来高を伴って高値を更新する主導株に集中する。",
        "risk_budget": "60-100%",
        "think_about": [
            "主導セクターの継続性と次の押し目水準",
            "ブレイク後に出来高が続く銘柄と失敗する銘柄の分離",
            "過熱テーマの利確ラインとローテーション候補",
        ],
        "do_now": [
            "最も相対強度が高いテーマの上位銘柄だけを候補化する",
            "ピボット、20日線、50日線を基準に損切り条件を先に決める",
            "指数上昇に対して参加率が細っていないかを確認する",
        ],
        "avoid": [
            "出遅れ銘柄への安易な回帰期待",
            "決算やイベントを跨ぐ過大ポジション",
        ],
    },
    REGIME_UPTREND_UNDER_PRESSURE: {
        "stance": "警戒付きリスクオン。上昇相場の形は残るが、資金防衛を優先する局面。",
        "risk_budget": "30-60%",
        "think_about": [
            "売り抜け日の増加が一時的か構造的か",
            "主導株のブレイク失敗率と50日線維持率",
            "金利・ドル・ボラティリティが成長株に与える圧力",
        ],
        "do_now": [
            "弱いポジションを減らし、強い銘柄だけを残す",
            "新規買いは小さく、即座に検証可能な水準に限定する",
            "市場がCorrectionへ落ちる条件を価格で明文化する",
        ],
        "avoid": [
            "平均取得単価を下げるためだけのナンピン",
            "指数が戻っただけで全リスクを戻すこと",
        ],
    },
    REGIME_RALLY_ATTEMPT: {
        "stance": "観察優先。底打ちの可能性はあるが、確認前に大きく張らない。",
        "risk_budget": "10-30%",
        "think_about": [
            "FTDが発生する条件と候補日",
            "下落時に売られにくかったテーマと最初に高値回復するテーマ",
            "イベント通過後に売り圧が枯れるか",
        ],
        "do_now": [
            "次の主導セクター候補をウォッチリスト化する",
            "出来高を伴う指数上昇と主導株のブレイクを待つ",
            "反発の質がショートカバーだけか実需買いかを区別する",
        ],
        "avoid": [
            "初反発を新上昇相場と誤認すること",
            "含み損銘柄の救済を主目的にした買い増し",
        ],
    },
    REGIME_MARKET_IN_CORRECTION: {
        "stance": "防御優先。買う局面ではなく、次の上昇相場の準備局面。",
        "risk_budget": "0-20%",
        "think_about": [
            "将来の市場回復時のリーダーセクター/テーマの調査と仮説化",
            "下落原因の把握、回復までのイベント的・時間的な見通し",
            "S&P 500/Nasdaq 100の50日線、200日線、直近安値などテクニカル節目",
            "売られ過ぎではなく構造悪化しているテーマの切り分け",
        ],
        "do_now": [
            "保有銘柄の損切り条件と再エントリー条件を分離して書く",
            "強気歪み候補を監視し、売りが止まる条件を待つ",
            "決算・CPI・FOMCなど反転のきっかけになり得るイベントを整理する",
        ],
        "avoid": [
            "安いという理由だけの早すぎる逆張り",
            "市場全体の売りが続く中で個別材料だけを過信すること",
        ],
    },
}


def get_market_playbook(status_key: str) -> dict[str, Any]:
    """Return a fixed playbook for the current market state."""

    return dict(PLAYBOOKS.get(status_key) or PLAYBOOKS[REGIME_MARKET_IN_CORRECTION])
