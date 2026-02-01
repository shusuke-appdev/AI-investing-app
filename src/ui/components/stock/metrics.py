import streamlit as st

def render_integrated_metrics(info: dict):
    """基本指標（統合版）を描画します"""
    st.markdown("### 📊 基本指標")
    
    # helper to format values
    def fmt(val, fmt_str="{:.2f}", default="N/A", scale=1):
        if val is None: return default
        try:
            return fmt_str.format(val * scale)
        except:
            return default

    # Rule of 40 Calculation
    rev_g_val = info.get("revenueGrowth")
    prof_m_val = info.get("operatingMargins")
    rule_40 = None
    if rev_g_val is not None and prof_m_val is not None:
        rule_40 = (rev_g_val + prof_m_val) * 100

    col1, col2, col3, col4 = st.columns(4)
    
    # 1. 成長性 & 効率性
    with col1:
        # Determine color class for Rule of 40
        rule_40_cls = "text-positive" if rule_40 and rule_40 >= 40 else "text-primary"
        
        st.markdown(f"""
        <div class="metric-group">
            <div class="metric-title">🚀 成長 & 効率性</div>
            <div class="metric-row"><span class="metric-label">売上成長(YoY)</span><span class="metric-value">{fmt(info.get('revenueGrowth'), "{:+.1f}%", scale=100)}</span></div>
            <div class="metric-row"><span class="metric-label">EPS成長(YoY)</span><span class="metric-value">{fmt(info.get('earningsGrowth'), "{:+.1f}%", scale=100)}</span></div>
            <div class="metric-row"><span class="metric-label">FCFマージン成長</span><span class="metric-value">{fmt(info.get('fcfMarginGrowth'), "{:+.1f}%", scale=100)}</span></div>
            <div class="metric-row"><span class="metric-label">売上総利益率</span><span class="metric-value">{fmt(info.get('grossMargins'), "{:.1f}%", scale=100)}</span></div>
            <div class="metric-row"><span class="metric-label">営業利益率</span><span class="metric-value">{fmt(info.get('operatingMargins'), "{:.1f}%", scale=100)}</span></div>
            <div class="metric-row" style="margin-top:0.5rem; border-top:1px dashed var(--color-border); padding-top:0.25rem;">
                <span class="metric-label" style="font-weight:700;">Rule of 40</span>
                <span class="metric-value {rule_40_cls}">{fmt(rule_40/100 if rule_40 else None, "{:.1f}", scale=1)}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # 2. バリュエーション
    with col2:
        st.markdown(f"""
        <div class="metric-group">
            <div class="metric-title">💎 バリュエーション</div>
            <div class="metric-row"><span class="metric-label">PSR(実績)</span><span class="metric-value">{fmt(info.get('priceToSalesTrailing12Months'), "{:.2f}x")}</span></div>
            <div class="metric-row"><span class="metric-label">PEGレシオ</span><span class="metric-value">{fmt(info.get('pegRatio'), "{:.2f}")}</span></div>
            <div class="metric-row"><span class="metric-label">PER(予想)</span><span class="metric-value">{fmt(info.get('forward_pe'), "{:.1f}x")}</span></div>
            <div class="metric-row"><span class="metric-label">PBR</span><span class="metric-value">{fmt(info.get('priceToBook'), "{:.2f}x")}</span></div>
            <div class="metric-row"><span class="metric-label">時価総額</span><span class="metric-value">{fmt(info.get('market_cap'), "${:,.1f}B", scale=1e-9)}</span></div>
        </div>
        """, unsafe_allow_html=True)

    # 3. モメンタム
    with col3:
        current = info.get("current_price") or 0
        high_52 = info.get("fifty_two_week_high")
        
        diff_high = ((current - high_52) / high_52 * 100) if (current and high_52) else None
        
        target = info.get("target_price")
        upside_val = ((target - current) / current * 100) if (target and current) else None
        
        # Color logic
        diff_cls = "text-negative" if diff_high and diff_high < -20 else "text-primary"
        upside_cls = "text-positive" if upside_val and upside_val > 0 else "text-negative"

        st.markdown(f"""
        <div class="metric-group">
            <div class="metric-title">📈 モメンタム</div>
            <div class="metric-row"><span class="metric-label">現在株価</span><span class="metric-value">${fmt(current, "{:,.2f}")}</span></div>
            <div class="metric-row"><span class="metric-label">52週高値</span><span class="metric-value">{fmt(high_52, "${:,.2f}")}</span></div>
            <div class="metric-row"><span class="metric-label">高値乖離率</span><span class="metric-value {diff_cls}">{fmt(diff_high/100 if diff_high else None, "{:+.1f}%", scale=100)}</span></div>
            <div class="metric-row"><span class="metric-label">目標株価</span><span class="metric-value">{fmt(target, "${:,.2f}")}</span></div>
            <div class="metric-row"><span class="metric-label">目標乖離</span><span class="metric-value {upside_cls}">{fmt(upside_val/100 if upside_val else None, "{:+.1f}%", scale=100)}</span></div>
        </div>
        """, unsafe_allow_html=True)
        
    # 4. 財務健全性
    with col4:
        st.markdown(f"""
        <div class="metric-group">
            <div class="metric-title">🛡️ 財務健全性</div>
            <div class="metric-row"><span class="metric-label">流動比率</span><span class="metric-value">{fmt(info.get('currentRatio'), "{:.2f}")}</span></div>
            <div class="metric-row"><span class="metric-label">負債資本倍率</span><span class="metric-value">{fmt(info.get('debtToEquity'), "{:.2f}")}</span></div>
            <div class="metric-row"><span class="metric-label">Beta</span><span class="metric-value">{fmt(info.get('beta'), "{:.2f}")}</span></div>
            <div class="metric-row"><span class="metric-label">ROA</span><span class="metric-value">{fmt(info.get('returnOnAssets'), "{:.1f}%", scale=100)}</span></div>
            <div class="metric-row"><span class="metric-label">従業員数</span><span class="metric-value">{fmt(info.get('fullTimeEmployees'), "{:,}")}</span></div>
        </div>
        """, unsafe_allow_html=True)
