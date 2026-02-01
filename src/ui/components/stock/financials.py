import streamlit as st
import plotly.graph_objects as go
import pandas as pd

def render_quarterly_financials_graph(ticker: str):
    """四半期財務グラフを描画（詳細データテーブルは削除済み）"""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        q_fin = stock.quarterly_financials
        
        if q_fin is not None and not q_fin.empty:
            q_fin = q_fin.sort_index(axis=1)
            recent_q_fin = q_fin.iloc[:, -6:]
            dates = []
            
            for d in recent_q_fin.columns:
                try:
                    ts = pd.Timestamp(d)
                    quarter = (ts.month - 1) // 3 + 1
                    year = str(ts.year)[2:]
                    dates.append(f"Q{quarter} '{year}")
                except:
                    dates.append(str(d)[:10])
            
            def get_row_data(df, keys):
                for k in keys:
                    if k in df.index:
                        return df.loc[k].values
                return [0] * len(df.columns)

            revenue_row = get_row_data(recent_q_fin, ["Total Revenue", "Revenue"])
            net_income_row = get_row_data(recent_q_fin, ["Net Income", "Net Income Common Stockholders"])
            
            revenue_m = revenue_row / 1e6
            net_income_m = net_income_row / 1e6
            
            net_margin = []
            for r, n in zip(revenue_row, net_income_row):
                if r != 0:
                    net_margin.append((n / r) * 100)
                else:
                    net_margin.append(0)
            
            fig = go.Figure()
            
            # 1. 売上高 (棒グラフ・青)
            fig.add_trace(go.Bar(
                x=dates, y=revenue_m, name="売上高",
                marker_color="#4285F4", offsetgroup=1, yaxis="y1"
            ))
            
            # 2. 純利益 (棒グラフ・水色)
            fig.add_trace(go.Bar(
                x=dates, y=net_income_m, name="純利益",
                marker_color="#64B5F6", offsetgroup=2, yaxis="y1"
            ))
            
            # 3. 純利益率 (折れ線グラフ・オレンジ)
            fig.add_trace(go.Scatter(
                x=dates, y=net_margin, name="当期純利益率 %",
                mode="lines+markers",
                line=dict(color="#FB8C00", width=3),
                marker=dict(size=8, color="#FFFFFF", line=dict(width=2, color="#FB8C00")),
                yaxis="y2"
            ))
            
            fig.update_layout(
                title=dict(text="損益計算書 (四半期)", font=dict(size=16)),
                yaxis=dict(title="金額 (百万ドル)", side="left", showgrid=True, gridcolor="#F1F3F4"),
                yaxis2=dict(
                    title="利益率 (%)", side="right", overlaying="y", showgrid=False,
                    range=[min(net_margin)*1.2 if min(net_margin)<0 else 0, max(net_margin)*1.2]
                ),
                legend=dict(orientation="h", x=0.5, y=1.1, xanchor="center"),
                barmode='group', height=400, margin=dict(l=50, r=50, t=50, b=50),
                template="plotly_white",xaxis=dict(tickmode='array', tickvals=dates)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("四半期財務データを取得できませんでした。")
            
    except Exception as e:
        st.info("詳細データの計算中に一部データが不足していました")


def render_recent_earnings(ticker: str):
    """直近決算サプライズを描画"""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        earnings_hist = stock.earnings_history
        
        if earnings_hist is not None and not earnings_hist.empty:
            df = earnings_hist.copy()
            try:
                df['sort_date'] = pd.to_datetime(df['quarter'])
                df = df.sort_values('sort_date', ascending=False)
            except: pass
            
            df = df.head(5)
            display_data = []
            
            for index, row in df.iterrows():
                date_val = row.get("quarter", index)
                date_str = str(date_val)[:10] 
                est = row.get("epsEstimate")
                act = row.get("epsActual")
                
                surprise = "N/A"
                if est is not None and act is not None and est != 0:
                    surp_val = (act - est) / abs(est) * 100
                    surprise = f"{surp_val:+.1f}%"
                
                beat_miss = "➖"
                if act is not None and est is not None:
                    if act > est: beat_miss = "✅ Beat"
                    elif act < est: beat_miss = "❌ Miss"
                
                display_data.append({
                    "決算日": date_str,
                    "EPS予想": f"${est:.2f}" if est is not None else "-",
                    "EPS実績": f"${act:.2f}" if act is not None else "-",
                    "サプライズ": surprise,
                    "結果": beat_miss
                })
            
            st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
        else:
            st.info("決算サプライズデータがありません")
            
    except Exception:
        st.info("決算データの取得に失敗しました")
