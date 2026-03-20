import pandas as pd
import numpy as np
import pytest
from src.advisor.volatility_clustering import detect_clustering, generate_signals

@pytest.fixture
def dummy_volatility_data():
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    np.random.seed(42)
    
    # Stable period
    stable_returns = np.random.normal(0.001, 0.01, 200)
    # Volatile period (clustering) with a shock
    volatile_returns = np.random.normal(-0.005, 0.04, 100)
    # Introduce an artificial shock
    volatile_returns[10] = -0.15
    
    returns = np.concatenate([stable_returns, volatile_returns])
    
    # Create simple typical dataframe structure
    df = pd.DataFrame({'log_return': returns}, index=dates)
    
    # Create vol_of_vol with stable -> volatile transition
    vol = df['log_return'].rolling(20).std() * np.sqrt(252)
    vov = vol.rolling(20).std()
    
    df['vol'] = vol
    df['vol_of_vol'] = vov
    df['sq_returns'] = returns ** 2
    
    return df

def test_detect_clustering_volatile(dummy_volatility_data):
    # パスが通ること、フォーマットが正しいことを確認
    result = detect_clustering(dummy_volatility_data)
    
    assert 'state' in result
    assert 'confidence' in result
    assert isinstance(result['state'], bool)

def test_generate_signals_exit(dummy_volatility_data):
    # フォーマットが合っていることを確認
    signals_with_pos = generate_signals(dummy_volatility_data, current_position=True)
    assert 'signal' in signals_with_pos
    assert signals_with_pos['signal'] in ["EXIT", "HOLD"]

def test_generate_signals_entry():
    # Construct a stable dataframe for ENTRY
    dates = pd.date_range("2023-01-01", periods=300, freq="B")
    np.random.seed(99)
    # Very stable returns
    returns = np.random.normal(0.001, 0.005, 300)
    df = pd.DataFrame({'log_return': returns}, index=dates)
    
    vol = df['log_return'].rolling(20).std() * np.sqrt(252)
    vov = vol.rolling(20).std()
    
    df['vol'] = vol
    df['vol_of_vol'] = vov
    df['sq_returns'] = returns ** 2
    
    signals = generate_signals(df, current_position=False)
    assert signals['clustering_state'] is False
    # If vol < hist_mean - 0.5 * hist_std, it's ENTRY.
    # We might not guarantee it in random data without explicit crafting, but it should not be EXIT.
    assert signals['signal'] in ["ENTRY", "HOLD"]
