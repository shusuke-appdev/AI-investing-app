import streamlit as st
import plotly.graph_objects as go
import pandas as pd

def render_quarterly_financials_graph(ticker: str):
    """四半期財務グラフを描画（Finnhub版）"""
    try:
        from src.finnhub_client import get_financials_reported, is_configured
        
        if not is_configured():
            st.warning("Finnhub APIキーが設定されていません")
            return

        # Finnhubから四半期報告書を取得
        # data = [{"report": {"ic": [...], "bs": [...]}, "year": 2024, "quarter": 1, ...}]
        reports = get_financials_reported(ticker, freq="quarterly")
        
        if not reports:
            st.info("四半期財務データが見つかりませんでした (Finnhub)")
            return

        # データを抽出・整理
        financials_data = []
        
        for item in reports:
            try:
                year = item.get("year")
                quarter = item.get("quarter")
                report = item.get("report", {})
                
                # Income Statement (ic) から Revenue, NetIncome を探す
                ic = report.get("ic", [])
                
                revenue = 0
                operating_income = 0
                net_income = 0
                
                # コンセプト辞書から検索 ("concept" key)
                # 一般的なタグ名: "Revenues", "SalesRevenueNet", "NetIncomeLoss"
                for entry in ic:
                    concept = entry.get("concept", "")
                    value = entry.get("value", 0)
                    
                    if concept in ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet"]:
                        if revenue == 0: revenue = value
                    
                    if concept in ["OperatingIncomeLoss", "OperatingIncome"]:
                        if operating_income == 0: operating_income = value

                    if concept in ["NetIncomeLoss", "ProfitLoss"]:
                        if net_income == 0: net_income = value
                
                # 日付ラベル作成
                filed_date = item.get("filedDate", "")
                date_label = f"Q{quarter} '{str(year)[2:]}"
                
                # データがある場合のみ追加
                if revenue != 0:
                    financials_data.append({
                        "date_label": date_label,
                        "filed_date": filed_date, # ソート用
                        "revenue": revenue,
                        "operating_income": operating_income,
                        "net_income": net_income
                    })
                    
            except Exception:
                continue

        # --- Fallback: yfinance ---
        if not financials_data:
            try:
                import yfinance as yf
                yf_ticker = yf.Ticker(ticker)
                qf = yf_ticker.quarterly_financials
                
                # yfinance returns DataFrame with dates as columns
                # Indexes: "Total Revenue", "Operating Income", "Net Income" etc.
                if not qf.empty:
                    # 一般的なインデックス名を探す (yfinanceは変動することがある)
                    # Use .loc with flexible lookup or iterator
                    
                    # カラム（日付）でループ（新しい順に来るので逆にするか、あとでソート）
                    for date_obj in qf.columns:
                        try:
                            # 億ドル単位で扱いやすいように生の値を取得
                            # yfinanceのインデックスは日本語化されている場合と英語の場合があるが、
                            # ライブラリ内部的には英語キーが残っていることが多い。
                            # ここでは安全のため .get() ではなく loc検索、なければ0
                            
                            def get_val(df, keys):
                                for k in keys:
                                    if k in df.index: return df.loc[k, date_obj]
                                return 0

                            rev_keys = ["Total Revenue", "Operating Revenue", "Revenue"]
                            op_keys = ["Operating Income", "Operating Profit"]
                            net_keys = ["Net Income", "Net Income Common Stockholders"]
                            
                            revenue = get_val(qf, rev_keys)
                            operating_income = get_val(qf, op_keys)
                            net_income = get_val(qf, net_keys)
                            
                            if revenue != 0:
                                # yfinanceの四半期はTimestampオブジェクトなので、strftimeで整形
                                # Q%q はPythonのstrftimeにはないため、手動で計算するか近似
                                # ここでは簡易的に年と月で表示
                                financials_data.append({
                                    "date_label": date_obj.strftime("'%y-%m"), # 簡易表示
                                    "filed_date": date_obj.strftime("%Y-%m-%d"),
                                    "revenue": float(revenue),
                                    "operating_income": float(operating_income),
                                    "net_income": float(net_income)
                                })
                        except Exception as ey:
                            continue
            except Exception as e_yf:
                print(f"YFormation Fallback Failed: {e_yf}")

        if not financials_data:
            st.warning("財務データの解析に失敗しました (Finnhub & yfinance)")
            return

        # 日付順でソート（古い順）
        financials_data.sort(key=lambda x: x["filed_date"])
        
        # 直近6四半期程度に絞る
        financials_data = financials_data[-6:]
        
        dates = [d["date_label"] for d in financials_data]
        revenue_m = [d["revenue"] / 1e6 for d in financials_data]
        operating_income_m = [d["operating_income"] / 1e6 for d in financials_data]
        net_income_m = [d["net_income"] / 1e6 for d in financials_data]
        
        net_margin = []
        for r, n in zip(revenue_m, net_income_m):
            if r != 0:
                net_margin.append((n / r) * 100)
            else:
                net_margin.append(0)
        
        fig = go.Figure()
        
        # 1. 売上高 (棒グラフ・青)
        fig.add_trace(go.Bar(
            x=dates, y=revenue_m, name="売上高",
            marker_color="#4285F4", offsetgroup=1
        ))

        # 2. 営業利益 (棒グラフ・緑)
        fig.add_trace(go.Bar(
            x=dates, y=operating_income_m, name="営業利益",
            marker_color="#34A853", offsetgroup=2
        ))
        
        # 3. 純利益 (棒グラフ・水色)
        fig.add_trace(go.Bar(
            x=dates, y=net_income_m, name="純利益",
            marker_color="#64B5F6", offsetgroup=3
        ))
        
        # 4. 純利益率 (折れ線グラフ・オレンジ)
        fig.add_trace(go.Scatter(
            x=dates, y=net_margin, name="当期純利益率 %",
            mode="lines+markers",
            line=dict(color="#FB8C00", width=3),
            marker=dict(size=8, color="#FFFFFF", line=dict(width=2, color="#FB8C00")),
            yaxis="y2"
        ))
        
        fig.update_layout(
            title=dict(text="損益計算書 (四半期 / Finnhub)", font=dict(size=16)),
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
            
    except Exception as e:
        st.info(f"詳細データの表示中にエラーが発生しました: {e}")


def render_recent_earnings(ticker: str):
    """直近決算サプライズを描画（Finnhub版）"""
    try:
        from src.finnhub_client import get_earnings_surprises, is_configured
        
        # Finnhub未設定時はyfinanceフォールバック（またはメッセージ）
        if not is_configured():
            st.warning("Finnhub APIキーが設定されていません")
            return

        surprises = get_earnings_surprises(ticker, limit=5)
        
        if surprises:
            display_data = []
            
            for item in surprises:
                period = item.get("period", "") # YYYY-MM-DD
                est = item.get("estimate")
                act = item.get("actual")
                surp_pct = item.get("surprisePercent")
                
                surprise_str = "N/A"
                if surp_pct is not None:
                    surprise_str = f"{surp_pct:+.1f}%"
                
                beat_miss = "➖"
                if act is not None and est is not None:
                    if act > est: beat_miss = "✅ Beat"
                    elif act < est: beat_miss = "❌ Miss"
                
                display_data.append({
                    "決算日": period,
                    "EPS予想": f"${est:.2f}" if est is not None else "-",
                    "EPS実績": f"${act:.2f}" if act is not None else "-",
                    "サプライズ": surprise_str,
                    "結果": beat_miss
                })
            
            st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
            
        else:
            st.info("決算サプライズデータがありません (Finnhub)")
            
    except Exception as e:
        st.info(f"決算データの取得に失敗しました: {e}")
