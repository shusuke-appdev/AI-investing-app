import logging

import numpy as np
import pandas as pd
try:
    from arch import arch_model
    from statsmodels.tsa.stattools import acf
    HAS_ADVANCED_STATS = True
except ImportError:
    HAS_ADVANCED_STATS = False

logger = logging.getLogger(__name__)

def detect_clustering(df: pd.DataFrame) -> dict:
    Step 3: クラスタリング検知アルゴリズム
    ACF, vol_of_vol, GARCH(1,1) の3手法で評価し、状態を判定する。
    """
    if not HAS_ADVANCED_STATS:
        return {'state': False, 'duration': 0, 'confidence': 0.0, 'reason': '分析ライブラリ(arch/statsmodels)未インストールのため判定スキップ'}

    if df is None or df.empty or 'log_return' not in df.columns or len(df) < 252:
        return {'state': False, 'duration': 0, 'confidence': 0.0, 'reason': 'データ不足'}

    recent_df = df.tail(252).copy()
    recent_df['log_return'] = recent_df['log_return'].fillna(0)

    # 1. ACFベース
    sq_returns = recent_df['log_return'] ** 2
    acf_vals = acf(sq_returns, nlags=120)

    # lag-1〜5の自己相関が0.3以上か
    acf_significant = any(val > 0.3 for val in acf_vals[1:6])

    # 半減期の推定（ACFが0.5を下回る最初の日数）
    half_life = 0
    for i, val in enumerate(acf_vals):
        if i > 0 and val < 0.5:
            half_life = i
            break
    if half_life == 0:
        half_life = 120 # 上限

    # 2. ボラ不安定度 (vol_of_vol) ベース
    if 'vol_of_vol' in recent_df.columns:
        vov = recent_df['vol_of_vol'].dropna()
        if len(vov) > 50:
            hist_mean = vov.mean()
            hist_std = vov.std()
            vov_threshold = hist_mean + 1.5 * hist_std
            # 直近5日間すべて閾値超えか
            recent_5_vov = vov.tail(5)
            vov_high = all(v >= vov_threshold for v in recent_5_vov) and len(recent_5_vov) == 5
        else:
            vov_high = False
    else:
        vov_high = False

    # 3. GARCH(1,1) フィットベース
    garch_high = False
    persistence = 0.0
    try:
        # スケール調整（archライブラリの収束安定化のため）
        y = recent_df['log_return'] * 100
        am = arch_model(y, vol='Garch', p=1, q=1, rescale=False)
        res = am.fit(disp='off')

        # persistence = alpha + beta
        alpha = res.params.get('alpha[1]', 0)
        beta = res.params.get('beta[1]', 0)
        persistence = alpha + beta


        # ショック検知（直近20日で3σ超えのリターンがあったか）
        std_ret = recent_df['log_return'].std() * 100
        recent_shocks = y.tail(20).apply(lambda x: abs(x) > 3 * std_ret)
        has_shock = recent_shocks.any()

        if persistence > 0.85 and has_shock:
            garch_high = True

        # 終了条件の確認：persistence < 0.7 かつ vov 低下ならクラスタリング終了（GARCHフラグOFF）
        if persistence < 0.7 and not vov_high:
            garch_high = False

    except Exception as e:
        logger.warning(f"GARCHフィットに失敗しました: {e}")
        # ACFをフォールバックとして強める
        if acf_significant and vov_high:
            garch_high = True # 疑似的にTrueとする

    # 状態判定（合議制）
    score = 0
    if acf_significant:
        score += 1
    if vov_high:
        score += 1
    if garch_high:
        score += 2  # GARCHを重視

    confidence = min(score / 4.0, 1.0)

    state = confidence >= 0.5  # 2点以上でTrue (GARCH単独、またはACF+VoV)

    # 推定持続期間: GARCHの理論的半減期 または ACFベース
    if persistence > 0 and persistence < 1:
        # half-life = -ln(2) / ln(persistence)  (※日次)
        theoretical_hl = -np.log(2) / np.log(persistence)
        duration = min(int(theoretical_hl), 120)
    else:
        duration = half_life

    reason_parts = []
    if garch_high:
        reason_parts.append(f"GARCH持続性高({persistence:.2f})")
    if vov_high:
        reason_parts.append("ボラティリティ不安定度高")
    if acf_significant:
        reason_parts.append("リターン平方の自己相関有意")

    reason = "、".join(reason_parts) if state else "クラスタリング未検知（安定期）"

    return {
        'state': state,
        'duration': duration,
        'confidence': confidence,
        'reason': reason
    }

def generate_signals(vol_df: pd.DataFrame, current_position: bool = False) -> dict:
    """
    Step 4: エントリー/エグジット判断ロジック
    """
    cluster_info = detect_clustering(vol_df)
    state = cluster_info['state']
    confidence = cluster_info['confidence']
    dur = cluster_info['duration']
    reason = cluster_info['reason']

    signal = "HOLD"
    explanation = ""

    # 直近5日のボラティリティ状態
    if vol_df is not None and len(vol_df) >= 20 and 'vol' in vol_df.columns:
        hist_vol_mean = vol_df['vol'].mean()
        hist_vol_std = vol_df['vol'].std()
        current_vol = vol_df['vol'].iloc[-1]

        # エグジット条件（position保有中）
        if current_position:
            if state and confidence > 0.7:
                signal = "EXIT"
                explanation = f"余震クラスタリング発生中（理由: {reason}）。安定するまで約{dur}営業日のリスクがあるためエグジットを推奨します。"
            elif state and dur > 30:
                signal = "EXIT"
                explanation = f"クラスタリングの長期化（推定{dur}日）が観測されたため、強制エグジットを推奨します。"
            else:
                signal = "HOLD"
                explanation = "ポジションを維持適格（安定推移の範囲内）。"
        # エントリー条件（no position）
        else:
            # 直近5日のクラスタリング状態を取得したいが、ここでは簡易に現在StateとVolで判断
            # 仕様: clustering_state == False かつ vol < 過去平均 - 0.5σ
            if not state and current_vol < (hist_vol_mean - 0.5 * hist_vol_std):
                signal = "ENTRY"
                explanation = f"ボラティリティが十分に収縮し（{current_vol:.2f} < 閾値）、安定期に移行したため低リスクエントリー好機です。"
            else:
                signal = "HOLD"
                explanation = "現在はリスク・リワードが見合わない、または不安定な相場環境（クラスタリング中あるいは収縮不十分）のため待機を推奨します。"
    else:
        explanation = "データ不足のためシグナル判定を保留します。"

    return {
        'signal': signal,
        'confidence': confidence,
        'duration_estimate': dur,
        'explanation': explanation,
        'clustering_state': state
    }
