"""
Market News Tab Module (formerly Market Intelligence)
Displays flash summary, option analysis, and AI market recap.
"""
import streamlit as st
from src.market_data import get_market_indices, get_stock_info
from src.news_analyst import generate_market_recap
from src.option_analyst import get_major_indices_options


def render_market_tab():
    """Renders the Market News tab."""
    # ヘッダーとAIレポートボタンを横並びに配置
    header_col, btn_col = st.columns([4, 1])
    with header_col:
        st.markdown("## 📰 ニュース")
    with btn_col:
        if st.button("✨ AI分析", type="secondary", use_container_width=True):
            _generate_ai_recap()
    
    with st.spinner("市場データを取得中..."):
        if st.session_state.market_data is None:
            st.session_state.market_data = get_market_indices()
        market_data = st.session_state.market_data
    
    _render_flash_summary(market_data)
    
    # AIレポートがある場合のみ表示
    if st.session_state.get("ai_recap"):
        st.divider()
        with st.container(border=True):
            st.markdown("### 🤖 AI分析レポート")
            # Generate markdown, escaping dollar signs to prevent LaTeX rendering issues
            import re
            # エスケープされていない$のみをエスケープ（既に\$になっているものは除外）
            safe_recap = re.sub(r'(?<!\\)\$', r'\\$', st.session_state.ai_recap)
            st.markdown(safe_recap)
            if st.button("🔄 再生成", key="regenerate_recap"):
                st.session_state.ai_recap = None
                st.rerun()
    
    st.divider()
    _render_option_analysis()


def _generate_ai_recap():
    """AIレポート生成"""
    if not st.session_state.get("gemini_configured"):
        st.toast("⚠️ Gemini APIキーを設定してください", icon="⚠️")
        return
    
    with st.spinner("AI分析レポートを生成中... (ニュース取得・分析)"):
        from src.market_data import get_stock_news, get_stock_data
        from src.theme_analyst import get_ranked_themes
        from src.news_aggregator import get_aggregated_news, merge_with_yfinance_news
        
        # 1. yfinanceからティッカー関連ニュース取得
        tickers_to_fetch = [
            # Macro / Indices
            "^GSPC", "^IXIC", "^RUT", "TLT", "VIX", "DX-Y.NYB",
            # Mega Tech
            "NVDA", "MSFT", "GOOGL", "META", "AMZN", "AAPL", "TSLA",
            # Semiconductor (Design/Fab/Equip)
            "TSM", "AVGO", "AMD", "ARM", "QCOM", "INTC", "MU", 
            "ASML", "LRCX", "AMAT", "KLAC",
            # AI Ecosystem (Server/Data/Software)
            "SMCI", "PLTR", "ORCL", "CRM", "NOW", "DELL", "VRT",
            # Broad Sector ETFs
            "XLE", "XLF", "XLV", "XLI", "XLY", "XLP", "XLU", "XLRE"
        ]
        yf_news = []
        seen_links = set()
        
        for t in tickers_to_fetch:
            news_items = get_stock_news(t, max_items=3)
            for item in news_items:
                if item['link'] not in seen_links:
                    item['related_ticker'] = t
                    item['source'] = 'YFinance'
                    yf_news.append(item)
                    seen_links.add(item['link'])
        
        # 2. GNewsから広範なニュースを取得（コモディティ、暗号資産、マクロ含む）
        gnews_articles = get_aggregated_news(
            categories=["BUSINESS", "TECHNOLOGY", "WORLD"],
            keywords=[
                # マクロ・政策
                "Federal Reserve", "FOMC", "inflation", "Treasury yields", "interest rates",
                # コモディティ
                "crude oil", "gold prices", "commodities", "copper",
                # 暗号資産
                "Bitcoin", "cryptocurrency", "Ethereum",
                # 市場全般
                "stock market", "S&P 500", "Nasdaq", "Wall Street",
                # 地政学
                "tariffs", "trade war", "geopolitics",
            ],
            max_per_source=8,
            max_total=50
        )
        
        # 3. yfinanceとGNewsを統合（重複排除）
        news_data = merge_with_yfinance_news(gnews_articles, yf_news, max_total=80)
        
        # 4. 週次パフォーマンス（1週間リターン）の取得 - アセットクラス横断
        weekly_performance = {}
        cross_asset_tickers = {
            # 株式指数
            "S&P 500": "^GSPC",
            "Nasdaq 100": "^NDX",
            "Russell 2000": "^RUT",
            "Dow Jones": "^DJI",
            # 債券
            "TLT (20Y Bond)": "TLT",
            "US 10Y Yield": "^TNX",
            # コモディティ
            "Gold": "GC=F",
            "WTI Crude": "CL=F",
            "Copper": "HG=F",
            # 暗号資産
            "Bitcoin": "BTC-USD",
            "Ethereum": "ETH-USD",
            # 為替
            "DXY (Dollar)": "DX-Y.NYB",
            "USD/JPY": "JPY=X",
        }
        try:
            for name, ticker in cross_asset_tickers.items():
                df = get_stock_data(ticker, period="5d")
                if not df.empty and len(df) >= 2:
                    start_price = df["Close"].iloc[0]
                    end_price = df["Close"].iloc[-1]
                    change_1w = (end_price - start_price) / start_price * 100
                    weekly_performance[name] = f"{change_1w:+.2f}%"
        except Exception as e:
            print(f"Weekly performance fetch error: {e}")
        
        # 5. 市場コンテキスト (1ヶ月トレンド) の取得
        trend_context = {}
        try:
            indices = {"S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "Russell 2000": "^RUT"}
            for name, ticker in indices.items():
                df = get_stock_data(ticker, period="1mo")
                if not df.empty and len(df) > 1:
                    start_price = df["Close"].iloc[0]
                    end_price = df["Close"].iloc[-1]
                    change_1mo = (end_price - start_price) / start_price * 100
                    
                    trend = "上昇" if change_1mo > 2 else "下落" if change_1mo < -2 else "横ばい"
                    trend_context[name] = {
                        "change_1mo": f"{change_1mo:+.2f}%",
                        "trend": trend,
                        "start_date": df.index[0].strftime("%Y-%m-%d"),
                        "end_date": df.index[-1].strftime("%Y-%m-%d")
                    }
        except Exception as e:
            print(f"Trend fetch error: {e}")

        # 3. テーマ別トレンド取得 (Short & Medium)
        theme_str_parts = ["【テーマ別トレンド分析 (資金循環)】"]
        try:
            # Short (5日)
            short_themes = get_ranked_themes("5日")
            if short_themes:
                top5_s = [f"{t['theme']}({t['performance']:+.1f}%)" for t in short_themes[:5]]
                bot5_s = [f"{t['theme']}({t['performance']:+.1f}%)" for t in short_themes[-5:]]
                theme_str_parts.append(f"- 短期(5日) Top5: {', '.join(top5_s)}")
                theme_str_parts.append(f"- 短期(5日) Bottom5: {', '.join(bot5_s)}")
            
            # Medium (1ヶ月)
            med_themes = get_ranked_themes("1ヶ月")
            if med_themes:
                top5_m = [f"{t['theme']}({t['performance']:+.1f}%)" for t in med_themes[:5]]
                bot5_m = [f"{t['theme']}({t['performance']:+.1f}%)" for t in med_themes[-5:]]
                if top5_m: theme_str_parts.append(f"- 中期(1ヶ月) Top5: {', '.join(top5_m)}")
                if bot5_m: theme_str_parts.append(f"- 中期(1ヶ月) Bottom5: {', '.join(bot5_m)}")
                
        except Exception as e:
            print(f"Theme data fetch error: {e}")
            theme_str_parts.append("- テーマデータの取得に失敗しました")
            
        theme_analysis_str = "\n".join(theme_str_parts)

        market_data = st.session_state.market_data or {}
        market_data["trend_1mo"] = trend_context
        market_data["weekly_performance"] = weekly_performance  # 週次パフォーマンス追加
        
        option_analysis = st.session_state.option_analysis or []
        
        recap = generate_market_recap(
            market_data,
            news_data,
            option_analysis,
            theme_analysis=theme_analysis_str
        )
        st.session_state.ai_recap = recap
        st.rerun()


def _render_flash_summary(market_data):
    """Flash Summaryを資産クラス別にボックス化して表示"""
    st.markdown("### 📌 Flash Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container(border=True):
            st.markdown("**📊 株式指数**")
            # TOPIXはETF(1306.T)で代用しているため、円表示になるが変化率は近似できる
            indices = [
                ("S&P 500", "S&P500"), ("Nasdaq", "Nasdaq"), ("Dow 30", "Dow30"),
                ("Nikkei 225", "日経225"), ("TOPIX", "TOPIX"), # 1306.T
                ("EURO STOXX 50", "Euro50"), ("Shanghai Composite", "上海総合")
            ]
            for name, label in indices:
                if name in market_data:
                    d = market_data[name]
                    price_fmt = f"{d.get('price', 0):,.0f}"
                    if name == "TOPIX": price_fmt = f"¥{d.get('price', 0):,.0f}"
                    _render_market_item(label, price_fmt, d.get("change", 0))
    
    with col2:
        with st.container(border=True):
            st.markdown("**💵 債券・金利**")
            # 日本10年はYF取得不可のため削除、US 2Y復活
            rates = [("US 2Y", "米2年"), ("US 10Y", "米10年"), ("US 30Y", "米30年")]
            for name, label in rates:
                if name in market_data:
                    d = market_data[name]
                    _render_market_item(label, f"{d.get('price', 0):.2f}%", d.get("change", 0))
    
    with col3:
        with st.container(border=True):
            st.markdown("**🌍 商品・FX・暗号資産**")
            assets = [
                ("USD/JPY", "USD/JPY", lambda p: f"¥{p:.2f}"),
                ("EUR/JPY", "EUR/JPY", lambda p: f"¥{p:.2f}"),
                ("Gold", "Gold", lambda p: f"${p:,.0f}"),
                ("WTI Oil", "WTI原油", lambda p: f"${p:.2f}"),
                # Brent削除
                ("Bitcoin", "BTC", lambda p: f"${p/1000:.1f}K"),
                ("Ethereum", "ETH", lambda p: f"${p/1000:.1f}K"),
            ]
            for name, label, fmt in assets:
                if name in market_data:
                    d = market_data[name]
                    _render_market_item(label, fmt(d.get("price", 0)), d.get("change", 0))


def _render_market_item(label: str, value: str, change: float):
    """市場データの1行表示（色分け統一）"""
    color = "#10b981" if change >= 0 else "#ef4444"
    arrow = "↑" if change >= 0 else "↓"
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; 
                border-bottom: 1px solid #e5e7eb; font-size: 1rem;">
        <span style="color: #374151; font-weight: 500;">{label}</span>
        <span style="font-weight: 700;">{value}</span>
        <span style="color: {color}; font-weight: 600;">{arrow}{abs(change):.2f}%</span>
    </div>
    """, unsafe_allow_html=True)


def _render_option_analysis():
    """オプション分析（コンパクト版）"""
    st.markdown("### 📊 オプション分析 (詳細)")
    
    with st.spinner("オプションデータを取得中..."):
        if st.session_state.option_analysis is None:
            from src.option_analyst import get_major_indices_options
            st.session_state.option_analysis = get_major_indices_options()
        option_analysis = st.session_state.option_analysis
    
    if not option_analysis:
        st.info("オプションデータを取得できませんでした")
        return
    
    # 全体センチメント（コンパクト）
    bullish = sum(1 for o in option_analysis if o.get("sentiment") == "強気")
    bearish = sum(1 for o in option_analysis if o.get("sentiment") == "弱気")
    
    if bearish > bullish:
        st.error("🔴 **全体: 弱気** — ヘッジ需要強まる")
    elif bullish > bearish:
        st.success("🟢 **全体: 強気** — アップサイド期待")
    else:
        st.info("⚪ **全体: 中立** — 方向感模索中")
    
    # 各銘柄表示
    cols = st.columns(len(option_analysis))
    for i, opt in enumerate(option_analysis):
        with cols[i]:
            _render_ticker_compact(opt)


def _render_ticker_compact(opt: dict):
    """個別銘柄のコンパクト表示（ナラティブ形式）"""
    ticker = opt.get("ticker", "N/A")
    sentiment = opt.get("sentiment", "中立")
    pcr = opt.get("pcr", {})
    gex = opt.get("gex", {})
    iv = opt.get("iv")
    max_pain = opt.get("max_pain")
    analysis_points = opt.get("analysis", [])
    
    icon = "🟢" if sentiment == "強気" else "🔴" if sentiment == "弱気" else "⚪"
    stock_info = get_stock_info(ticker)
    current_price = stock_info.get("current_price", 0)
    
    with st.container(border=True):
        # ヘッダー
        st.markdown(f"**{icon} {ticker}** ${current_price:,.2f}" if current_price else f"**{icon} {ticker}**")
        
        # 主要指標グリッド
        pcr_val = pcr.get("oi_pcr", 0) if pcr else 0
        net_gex = gex.get("nearby_net_gex", 0) if gex else 0
        
        # 1行目: PCR / GEX
        c1, c2 = st.columns(2)
        with c1:
            pcr_col = "#ef4444" if pcr_val > 1.2 else "#10b981" if pcr_val < 0.7 else "#6b7280"
            st.markdown(f"<small>PCR</small><br><strong style='color:{pcr_col}'>{pcr_val:.2f}</strong>", unsafe_allow_html=True)
        with c2:
            gex_col = "#10b981" if net_gex > 0 else "#ef4444"
            st.markdown(f"<small>Net GEX</small><br><strong style='color:{gex_col}'>{net_gex/1e6:+.0f}M</strong>", unsafe_allow_html=True)
            
        # 2行目: IV / MaxPain
        c3, c4 = st.columns(2)
        with c3:
            st.markdown(f"<small>IV(ATM)</small><br><strong>{iv:.1%}</strong>" if iv else "-", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<small>Max Pain</small><br><strong>${max_pain:.0f}</strong>" if max_pain else "-", unsafe_allow_html=True)
        
        st.divider()
        
        # ナラティブ分析生成
        narrative = f"現在の**PCRは{pcr_val:.2f}**で、これは{sentiment}を示唆しています。"
        if net_gex > 0:
            narrative += " **正のNet GEX**により急激な値動きは抑制される傾向にあります。"
        else:
            narrative += " **負のNet GEX**によりボラティリティが拡大しやすい状態です。"
            
        if iv and iv > 0.2: # IV > 20%
            narrative += f" IVは{iv:.1%}とやや高まっており警戒が必要です。"
            
        if max_pain:
            narrative += f" **Max Painは${max_pain:.0f}**に位置しており、SQに向けて意識される可能性があります。"
            
        st.caption(narrative)
        
        # Wall情報などは補足として
        if gex:
            p_wall = (gex.get("positive_wall") or {}).get("strike")
            n_wall = (gex.get("negative_wall") or {}).get("strike")
            walls = []
            if p_wall: walls.append(f"+Wall ${p_wall:,.0f}")
            if n_wall: walls.append(f"-Wall ${n_wall:,.0f}")
            if walls:
                st.caption(f"抵抗帯: {', '.join(walls)}")


def _render_detailed_analysis_enhanced(opt: dict, pcr_val: float, vol_pcr: float, net_gex: float, price: float):
    # Old function - logic moved to _render_ticker_compact
    pass
