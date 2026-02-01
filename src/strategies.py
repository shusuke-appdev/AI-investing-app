"""
売買戦略定義モジュール
バックテスト用の戦略クラスを定義します。
"""
from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd


class SMAcrossover(Strategy):
    """
    単純移動平均線クロスオーバー戦略
    短期MAが長期MAを上抜けで買い、下抜けで売り。
    """
    # パラメータ（最適化可能）
    n1 = 10  # 短期MA期間
    n2 = 30  # 長期MA期間
    
    def init(self):
        """インジケータの初期化"""
        close = self.data.Close
        self.sma1 = self.I(lambda x: pd.Series(x).rolling(self.n1).mean(), close)
        self.sma2 = self.I(lambda x: pd.Series(x).rolling(self.n2).mean(), close)
    
    def next(self):
        """各バーでの取引ロジック"""
        if crossover(self.sma1, self.sma2):
            self.buy()
        elif crossover(self.sma2, self.sma1):
            self.sell()


class RSIStrategy(Strategy):
    """
    RSIベースの逆張り戦略
    RSIが売られすぎで買い、買われすぎで売り。
    """
    rsi_period = 14
    oversold = 30
    overbought = 70
    
    def init(self):
        """RSIインジケータの初期化"""
        close = pd.Series(self.data.Close)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        self.rsi = self.I(lambda: 100 - (100 / (1 + rs)))
    
    def next(self):
        """各バーでの取引ロジック"""
        if self.rsi[-1] < self.oversold and not self.position:
            self.buy()
        elif self.rsi[-1] > self.overbought and self.position:
            self.sell()


class MACDStrategy(Strategy):
    """
    MACD戦略
    MACDラインがシグナルラインを上抜けで買い、下抜けで売り。
    """
    fast = 12
    slow = 26
    signal = 9
    
    def init(self):
        """MACDインジケータの初期化"""
        close = pd.Series(self.data.Close)
        exp1 = close.ewm(span=self.fast, adjust=False).mean()
        exp2 = close.ewm(span=self.slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=self.signal, adjust=False).mean()
        self.macd = self.I(lambda: macd)
        self.signal_line = self.I(lambda: signal_line)
    
    def next(self):
        """各バーでの取引ロジック"""
        if crossover(self.macd, self.signal_line):
            self.buy()
        elif crossover(self.signal_line, self.macd):
            self.sell()


# 利用可能な戦略のマッピング
AVAILABLE_STRATEGIES = {
    "SMAクロスオーバー": SMAcrossover,
    "RSI逆張り": RSIStrategy,
    "MACD": MACDStrategy,
}


def get_strategy_params(strategy_name: str) -> dict:
    """
    戦略のデフォルトパラメータを取得します。
    
    Args:
        strategy_name: 戦略名
    
    Returns:
        パラメータ名と値の辞書
    """
    if strategy_name == "SMAクロスオーバー":
        return {"n1": 10, "n2": 30}
    elif strategy_name == "RSI逆張り":
        return {"rsi_period": 14, "oversold": 30, "overbought": 70}
    elif strategy_name == "MACD":
        return {"fast": 12, "slow": 26, "signal": 9}
    return {}
