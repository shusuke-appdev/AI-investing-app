"""
バックテストエンジンモジュール
戦略を過去データで検証し、結果を返します。
"""
import pandas as pd
from backtesting import Backtest
from typing import Optional
import plotly.graph_objects as go
from .strategies import AVAILABLE_STRATEGIES
from .market_data import get_stock_data


def run_backtest(
    ticker: str,
    strategy_name: str,
    period: str = "1y",
    initial_cash: float = 10000,
    commission: float = 0.002,
    **strategy_params
) -> Optional[dict]:
    """
    バックテストを実行します。
    
    Args:
        ticker: 銘柄コード
        strategy_name: 戦略名
        period: テスト期間
        initial_cash: 初期資金
        commission: 手数料率
        **strategy_params: 戦略固有のパラメータ
    
    Returns:
        バックテスト結果の辞書
    """
    if strategy_name not in AVAILABLE_STRATEGIES:
        return {"error": f"Unknown strategy: {strategy_name}"}
    
    # データ取得
    df = get_stock_data(ticker, period)
    if df.empty:
        return {"error": f"Failed to fetch data for {ticker}"}
    
    # カラム名の調整（backtestingライブラリ用）
    df = df.rename(columns={
        "Open": "Open",
        "High": "High",
        "Low": "Low",
        "Close": "Close",
        "Volume": "Volume"
    })
    
    # 必要なカラムのみ抽出
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    
    # 戦略クラスの取得とパラメータ設定
    StrategyClass = AVAILABLE_STRATEGIES[strategy_name]
    
    # バックテストの実行
    try:
        bt = Backtest(
            df,
            StrategyClass,
            cash=initial_cash,
            commission=commission,
            exclusive_orders=True
        )
        
        # パラメータがある場合は適用
        if strategy_params:
            stats = bt.run(**strategy_params)
        else:
            stats = bt.run()
        
        # 結果の整形
        result = {
            "ticker": ticker,
            "strategy": strategy_name,
            "period": period,
            "start_date": str(df.index[0].date()),
            "end_date": str(df.index[-1].date()),
            "initial_cash": initial_cash,
            "final_equity": float(stats["Equity Final [$]"]),
            "return_pct": float(stats["Return [%]"]),
            "buy_hold_return": float(stats["Buy & Hold Return [%]"]),
            "max_drawdown": float(stats["Max. Drawdown [%]"]),
            "sharpe_ratio": float(stats["Sharpe Ratio"]) if pd.notna(stats["Sharpe Ratio"]) else None,
            "win_rate": float(stats["Win Rate [%]"]) if pd.notna(stats["Win Rate [%]"]) else None,
            "num_trades": int(stats["# Trades"]),
            "equity_curve": stats["_equity_curve"]["Equity"].tolist(),
            "trades": stats["_trades"].to_dict("records") if len(stats["_trades"]) > 0 else [],
        }
        
        return result
    
    except Exception as e:
        return {"error": str(e)}


def create_equity_chart(backtest_result: dict) -> go.Figure:
    """
    資産曲線のチャートを作成します。
    
    Args:
        backtest_result: バックテスト結果
    
    Returns:
        Plotly Figureオブジェクト
    """
    if "error" in backtest_result:
        fig = go.Figure()
        fig.add_annotation(
            text=backtest_result["error"],
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    equity = backtest_result.get("equity_curve", [])
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=equity,
        mode="lines",
        name="資産残高",
        line=dict(color="#2E86AB", width=2)
    ))
    
    fig.update_layout(
        title=f"{backtest_result['ticker']} - {backtest_result['strategy']}",
        xaxis_title="取引日",
        yaxis_title="資産残高 ($)",
        template="plotly_white",
        hovermode="x unified"
    )
    
    return fig


def format_backtest_summary(result: dict) -> str:
    """
    バックテスト結果のサマリーテキストを生成します。
    
    Args:
        result: バックテスト結果
    
    Returns:
        フォーマット済みサマリー
    """
    if "error" in result:
        return f"エラー: {result['error']}"
    
    lines = [
        f"**{result['ticker']}** - {result['strategy']}",
        f"期間: {result['start_date']} ～ {result['end_date']}",
        "",
        f"| 指標 | 値 |",
        f"|---|---|",
        f"| 最終資産 | ${result['final_equity']:,.2f} |",
        f"| リターン | {result['return_pct']:.2f}% |",
        f"| Buy & Hold | {result['buy_hold_return']:.2f}% |",
        f"| 最大DD | {result['max_drawdown']:.2f}% |",
        f"| シャープ比 | {result['sharpe_ratio']:.2f if result['sharpe_ratio'] else 'N/A'} |",
        f"| 勝率 | {result['win_rate']:.1f}% |" if result['win_rate'] else "| 勝率 | N/A |",
        f"| 取引回数 | {result['num_trades']} |",
    ]
    
    return "\n".join(lines)
