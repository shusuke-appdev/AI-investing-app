"""Manual next-leader discovery page."""

import reflex as rx

from frontend.components.ui_primitives import empty_state, page_header, section_heading
from frontend.state.theme_state import (
    GeminiUnverifiedTicker,
    ThemeDeepDiveItem,
    ThemeLeaderCandidate,
    ThemeLeaderExclusion,
    ThemeState,
)
from frontend.template import template


def _metric(label: str, value, suffix: str = "") -> rx.Component:
    return rx.box(
        rx.text(label, size="1", color=rx.color("gray", 10)),
        rx.text(value, suffix, size="3", weight="bold"),
        padding="0.55rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="0.55rem",
        min_width="0",
    )


def _source_link(url) -> rx.Component:
    return rx.link(
        rx.icon("external-link", size=13),
        "根拠",
        href=url,
        is_external=True,
        size="1",
    )


def _candidate_card(item: ThemeLeaderCandidate) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.hstack(
                        rx.link(
                            item.ticker,
                            href="/stock?ticker=" + item.ticker,
                            size="5",
                            weight="bold",
                            underline="hover",
                        ),
                        rx.badge(item.candidate_source, variant="soft"),
                        rx.badge(
                            item.fundamental_category,
                            color_scheme=rx.cond(
                                item.fundamental_category == "研究優先",
                                "green",
                                "amber",
                            ),
                        ),
                        wrap="wrap",
                    ),
                    rx.text(
                        item.company_name,
                        rx.cond(item.company_name != "", " / ", ""),
                        item.primary_theme,
                        size="2",
                        color=rx.color("gray", 11),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("研究優先度", size="1", color="gray"),
                    rx.text(
                        item.research_priority_score, "/100", size="6", weight="bold"
                    ),
                    align_items="end",
                    spacing="0",
                ),
                width="100%",
                justify="between",
                align="start",
                gap="0.75rem",
            ),
            rx.grid(
                _metric("テクニカル・テーマ", item.score, "/100"),
                _metric("ファンダメンタル", item.fundamental_score, "/100"),
                _metric("Stage 2", item.stage_pass_count, "/7"),
                _metric("市場比63日", item.market_relative_63d, "%"),
                _metric("節目距離", item.pivot_distance_pct, "%"),
                _metric("RVOL", item.rvol, "倍"),
                _metric("50日線乖離", item.ma50_extension_atr, " ATR"),
                _metric("20日売買代金中央値", item.median_dollar_volume_20d),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="2",
                width="100%",
            ),
            rx.flex(
                rx.badge(item.status, color_scheme="blue", variant="surface"),
                rx.badge(
                    rx.cond(item.vcp, "VCPあり", "VCPなし"),
                    color_scheme=rx.cond(item.vcp, "green", "gray"),
                ),
                rx.badge(
                    rx.cond(item.atr_contraction, "ATR収縮", "ATR収縮なし"),
                    color_scheme=rx.cond(item.atr_contraction, "green", "gray"),
                ),
                rx.badge("Fデータ取得率 ", item.fundamental_coverage, "%"),
                wrap="wrap",
                gap="0.4rem",
            ),
            rx.callout(item.candidate_reason, icon="search", width="100%"),
            rx.text("次に確認: ", item.next_condition, size="2"),
            rx.text(
                "無効化条件: ",
                item.invalidation_condition,
                size="2",
                color=rx.color("red", 10),
            ),
            rx.text(item.fundamental_summary, size="2", color=rx.color("gray", 11)),
            rx.flex(
                rx.foreach(item.source_urls, _source_link),
                rx.spacer(),
                rx.text("取得: " + item.fetched_at, size="1", color="gray"),
                width="100%",
                wrap="wrap",
                gap="0.5rem",
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
    )


def _pending_card(item: ThemeLeaderCandidate) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.link(
                    item.ticker,
                    href="/stock?ticker=" + item.ticker,
                    weight="bold",
                ),
                rx.badge("ファンダメンタル確認待ち", color_scheme="amber"),
            ),
            rx.text(item.candidate_reason, size="2"),
            rx.text(item.fundamental_summary, size="1", color="gray"),
            align_items="start",
            width="100%",
        ),
        width="100%",
    )


def _unverified_card(item: GeminiUnverifiedTicker) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(item.ticker, weight="bold"),
                rx.badge("Gemini未検証", color_scheme="red"),
            ),
            rx.text(item.company_name, " / ", item.theme, size="2"),
            rx.text(item.reason, size="2", color=rx.color("red", 10)),
            rx.flex(
                rx.foreach(item.source_urls, _source_link), gap="0.5rem", wrap="wrap"
            ),
            width="100%",
            align_items="start",
        ),
        width="100%",
    )


def _exclusion(item: ThemeLeaderExclusion) -> rx.Component:
    return rx.badge(item.reason, " ", item.count, "件", variant="soft")


def _deep_dive_card(item: ThemeDeepDiveItem) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(item.ticker, size="4", weight="bold"),
            rx.text("テーマとの事業関係: ", item.business_relationship, size="2"),
            rx.text("業績加速: ", item.earnings_acceleration, size="2"),
            rx.text("最新材料: ", item.latest_catalyst, size="2"),
            rx.text(
                "反証: ", item.counter_evidence, size="2", color=rx.color("red", 10)
            ),
            rx.text("次回確認: ", item.next_check, size="2"),
            rx.flex(
                rx.foreach(item.source_urls, _source_link), gap="0.5rem", wrap="wrap"
            ),
            width="100%",
            align_items="start",
            spacing="2",
        ),
        width="100%",
    )


@template
def theme_leaders_page() -> rx.Component:
    return rx.vstack(
        page_header(
            "次期リーダー候補",
            "登録代表銘柄と、一次資料で検証できたGemini探索銘柄を同じ市場データ条件で比較します。",
            rx.link(rx.button("テーマ順位へ戻る", variant="surface"), href="/theme"),
        ),
        rx.callout(
            "このページを開いただけではGemini、候補2年足、企業情報を取得しません。下の実行ボタンを押した時だけ分析します。",
            icon="info",
            color_scheme="blue",
            width="100%",
        ),
        rx.flex(
            rx.text("対象テーマ", size="2", weight="bold"),
            rx.foreach(
                ThemeState.leader_selected_themes,
                lambda theme: rx.badge(theme, color_scheme="violet", variant="surface"),
            ),
            wrap="wrap",
            gap="0.5rem",
            width="100%",
        ),
        rx.flex(
            rx.button(
                rx.icon("search", size=16),
                "候補探索を実行",
                on_click=ThemeState.discover_theme_leaders(False),
                loading=ThemeState.is_discovering_leaders,
                disabled=ThemeState.leader_selected_themes.length() == 0,
            ),
            rx.button(
                "強制更新",
                on_click=ThemeState.discover_theme_leaders(True),
                loading=ThemeState.is_discovering_leaders,
                variant="surface",
                disabled=ThemeState.leader_selected_themes.length() == 0,
            ),
            wrap="wrap",
            gap="0.5rem",
        ),
        rx.cond(
            ThemeState.leader_error_msg != "",
            rx.callout(
                ThemeState.leader_error_msg,
                icon="triangle-alert",
                color_scheme="red",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            ThemeState.leader_warning_msg != "",
            rx.callout(
                ThemeState.leader_warning_msg,
                icon="info",
                color_scheme="amber",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            ThemeState.is_discovering_leaders,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("登録外探索、価格分析、ファンダメンタル評価を実行中…"),
                    align_items="center",
                ),
                min_height="260px",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            ThemeState.leader_candidates.length() > 0,
            rx.vstack(
                section_heading(
                    "主候補",
                    "70%をテクニカル・テーマ、30%をファンダメンタルで統合した研究優先度順です。",
                ),
                rx.foreach(ThemeState.leader_candidates, _candidate_card),
                width="100%",
                spacing="3",
            ),
            rx.cond(
                (ThemeState.leader_status != "idle")
                & (ThemeState.leader_status != "loading")
                & (~ThemeState.is_discovering_leaders),
                empty_state(
                    "主候補はありません",
                    "条件未達の銘柄は、確認待ちまたは除外理由に分けて表示します。",
                    "search-x",
                ),
                rx.fragment(),
            ),
        ),
        rx.cond(
            ThemeState.leader_fundamental_pending.length() > 0,
            rx.vstack(
                section_heading(
                    "ファンダメンタル確認待ち",
                    "データ取得率が60%未満のため0点扱いせず、主候補とは比較しません。",
                ),
                rx.foreach(ThemeState.leader_fundamental_pending, _pending_card),
                width="100%",
                spacing="2",
            ),
            rx.fragment(),
        ),
        rx.cond(
            ThemeState.leader_gemini_unverified.length() > 0,
            rx.vstack(
                section_heading(
                    "Gemini未検証",
                    "引用・一次資料・日付・市場条件を満たさず、採点母集団から外しました。",
                ),
                rx.foreach(ThemeState.leader_gemini_unverified, _unverified_card),
                width="100%",
                spacing="2",
            ),
            rx.fragment(),
        ),
        rx.cond(
            ThemeState.leader_exclusions.length() > 0,
            rx.vstack(
                rx.text("除外理由", weight="bold"),
                rx.flex(
                    rx.foreach(ThemeState.leader_exclusions, _exclusion),
                    wrap="wrap",
                    gap="0.4rem",
                ),
                align_items="start",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            ThemeState.leader_loaded_at != "",
            rx.callout(
                rx.text(
                    "取得: ",
                    ThemeState.leader_loaded_at,
                    " / Gemini検索 ",
                    ThemeState.gemini_search_query_count,
                    "件 / トークン ",
                    ThemeState.gemini_total_tokens,
                    " / ",
                    ThemeState.gemini_cache_status,
                ),
                icon="database",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            ThemeState.leader_candidates.length() > 0,
            rx.vstack(
                section_heading(
                    "Gemini深掘り",
                    "上位5銘柄の証拠と反証を別操作で整理します。機械順位は変更しません。",
                    rx.button(
                        "上位候補を深掘り",
                        on_click=ThemeState.deep_dive_theme_leaders(False),
                        loading=ThemeState.is_deep_diving,
                        variant="surface",
                    ),
                ),
                rx.cond(
                    ThemeState.deep_dive_error_msg != "",
                    rx.callout(
                        ThemeState.deep_dive_error_msg,
                        color_scheme="red",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                rx.foreach(ThemeState.deep_dive_items, _deep_dive_card),
                width="100%",
                spacing="2",
            ),
            rx.fragment(),
        ),
        rx.text(
            "候補は追加調査の優先対象です。売買推奨や将来予測ではありません。",
            size="1",
            color=rx.color("gray", 9),
        ),
        width="100%",
        max_width="1100px",
        margin="0 auto",
        spacing="4",
    )
