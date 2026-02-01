"""
テーマ定義ファイル
各テーマに対して代表銘柄（ETFまたは個別株）を紐付けます。
2026年2月更新版 - 最新の市況・M&A・ティッカー変更を反映
"""

THEMES: dict[str, list[str]] = {
    # ========================================
    # AI・テクノロジー (14 themes)
    # ========================================
    "AI半導体": ["NVDA", "AMD", "TSM", "AVGO", "MRVL", "QCOM", "ARM", "MU"],
    "AIインフラ/データセンター": ["NVDA", "SMCI", "DELL", "VRT", "ANET", "CRWV", "HPE"],
    "AI利活用/ソフトウェア": ["MSFT", "GOOGL", "META", "CRM", "NOW", "PLTR", "AI", "SNOW"],
    "AIエッジ/オンデバイスAI": ["QCOM", "ARM", "INTC", "MRVL", "ADI", "AAPL"],
    "自動運転AI": ["TSLA", "GOOGL", "MBLY", "LAZR", "ON", "APTV"],
    "医療AI": ["ISRG", "VEEV", "DXCM", "HIMS", "DOCS", "GEHC"],
    "クラウド": ["AMZN", "MSFT", "GOOGL", "SNOW", "NET", "DDOG", "MDB"],
    "サイバーセキュリティ": ["CRWD", "PANW", "ZS", "FTNT", "S", "OKTA", "CYBR"],
    "量子コンピュータ": ["IONQ", "RGTI", "QUBT", "IBM", "GOOGL", "MSFT"],
    "AR/VR/空間コンピューティング": ["META", "AAPL", "SNAP", "RBLX", "U"],
    "フィンテック": ["SQ", "PYPL", "AFRM", "SOFI", "COIN", "HOOD", "NU"],
    "ブロックチェーン/暗号資産": ["COIN", "MARA", "RIOT", "MSTR", "CLSK", "BITF"],
    "AIエージェント": ["CRM", "NOW", "PLTR", "PATH", "DOCN", "HUBS"],
    "生成AI": ["NVDA", "MSFT", "GOOGL", "META", "ADBE", "AI", "UPST"],

    # ========================================
    # 宇宙・防衛 (7 themes)
    # ========================================
    "宇宙/衛星": ["RKLB", "LUNR", "ASTS", "RDW", "BKSY", "PL", "IRDM"],
    "防衛": ["LMT", "RTX", "NOC", "GD", "BA", "HII", "LHX"],
    "衛星通信/スターリンク関連": ["ASTS", "GSAT", "IRDM", "VSAT", "GILT"],
    "ドローン/eVTOL": ["AVAV", "JOBY", "ACHR", "RCAT"],
    "軍事AI/サイバー防衛": ["PLTR", "BAH", "LDOS", "SAIC", "CACI"],
    "核抑止/原子力防衛": ["LMT", "NOC", "GD", "BWX", "BWXT"],
    "ミサイル防衛": ["LMT", "RTX", "NOC", "LHX"],

    # ========================================
    # 資源・エネルギー (14 themes)
    # ========================================
    "レアアース/戦略金属": ["MP", "REMX", "LAC", "ALB", "UUUU"],
    "リチウム": ["ALB", "SQM", "LAC"],
    "ウラン": ["CCJ", "URA", "NNE", "LEU", "UEC", "DNN", "UUUU"],
    "銅": ["FCX", "SCCO", "TECK", "COPX", "IVPAF"],
    "金・貴金属": ["GLD", "GDX", "NEM", "GOLD", "AEM", "KGC", "WPM"],
    "銀": ["SLV", "PAAS", "AG", "HL", "WPM"],
    "石油・ガス": ["XOM", "CVX", "COP", "SLB", "OXY", "EOG", "DVN"],
    "LNG": ["LNG", "GLNG", "EQT", "AR"],
    "原子力/SMR": ["CCJ", "URA", "NNE", "LEU", "SMR", "OKLO", "BWX"],
    "太陽光": ["ENPH", "FSLR", "RUN", "ARRY", "SEDG", "JKS"],  # NOVA削除
    "風力/再エネ": ["NEE", "CWEN", "AES", "BEP", "BEPC"],
    "水素/燃料電池": ["PLUG", "FCEL", "BLDP", "BE", "HYDR"],
    "エネルギー貯蔵/蓄電池": ["ENPH", "STEM", "FLUX", "SEDG"],
    "CCS/炭素回収": ["OXY", "XOM", "CVX", "ET"],

    # ========================================
    # 金融・不動産 (9 themes)
    # ========================================
    "メガバンク": ["JPM", "BAC", "GS", "MS", "C", "WFC"],
    "地銀/リージョナルバンク": ["USB", "PNC", "TFC", "FITB", "KEY", "CFG"],
    "保険": ["BRK-B", "PGR", "AIG", "MET", "ALL", "TRV"],
    "資産運用": ["BLK", "SCHW", "TROW", "BEN", "IVZ", "COIN"],
    "REIT（商業）": ["SPG", "O", "MAC", "KIM", "REG"],
    "REIT（物流/データセンター）": ["PLD", "DLR", "EQIX", "AMT", "CCI"],
    "仮想通貨関連": ["COIN", "MSTR", "MARA", "RIOT", "HOOD", "BITO"],
    "決済/ペイメント": ["V", "MA", "PYPL", "AFRM", "GPN"],
    "ネオバンク/デジタル銀行": ["SOFI", "NU", "HOOD", "LZ"],

    # ========================================
    # ヘルスケア (9 themes)
    # ========================================
    "バイオテック": ["XBI", "MRNA", "REGN", "VRTX", "AMGN", "GILD", "BIIB"],
    "医薬品大手": ["LLY", "NVO", "JNJ", "PFE", "MRK", "ABBV", "BMY"],
    "医療機器": ["ABT", "MDT", "SYK", "BSX", "EW", "ISRG", "GEHC"],
    "遺伝子治療/CRISPR": ["CRSP", "BEAM", "NTLA", "EDIT"],  # BLUE削除
    "肥満治療薬 (GLP-1)": ["LLY", "NVO", "AMGN", "VKTX", "ALT"],  # ZEAL削除
    "ヘルステック": ["VEEV", "DOCS", "HIMS", "OSCR", "TDOC"],
    "介護・高齢化": ["HCA", "UHS", "DVA", "EHC", "ENSG"],
    "CRO/CDMO": ["IQV", "CRL", "WST", "TMO"],  # IQVIA→IQV, PPD削除
    "核医学/放射性医薬品": ["LLY", "NVS", "AZN"],

    # ========================================
    # 製造・インフラ (9 themes)
    # ========================================
    "半導体製造装置": ["ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ONTO"],
    "EV/電池": ["TSLA", "RIVN", "LCID", "QS", "F", "GM"],
    "ロボティクス/自動化": ["ISRG", "ROK", "TER", "PATH", "FANUY", "ABBV"],  # ABB→ABBV(別銘柄)
    "産業オートメーション": ["ROK", "EMR", "HON", "FANUY", "GNRC"],
    "電力インフラ": ["ETN", "EMR", "APH", "PWR", "GNRC", "VRT"],
    "変圧器/送電/グリッド": ["ETN", "GE", "POWI", "VICR", "VRT"],
    "データセンターREIT": ["DLR", "EQIX", "AMT", "CCI", "SBAC"],
    "5G/通信インフラ": ["T", "VZ", "TMUS", "AMT", "CCI", "ERIC", "NOK"],
    "電力/ユーティリティ": ["NEE", "DUK", "SO", "D", "AEP"],

    # ========================================
    # 消費・メディア (8 themes)
    # ========================================
    "Eコマース": ["AMZN", "SHOP", "MELI", "SE", "BABA", "JD", "PDD"],
    "ストリーミング": ["NFLX", "DIS", "WBD", "ROKU", "SPOT"],  # PARA削除
    "ゲーム/Eスポーツ": ["EA", "TTWO", "RBLX", "NTDOY", "MSFT"],  # ATVI削除(MS買収)
    "高級ブランド": ["LVMUY", "RACE", "TPR", "RL"],  # RMS,KER,CPRI削除
    "ペット関連": ["CHWY", "IDXX", "ZTS", "WOOF", "FRPT"],
    "大麻/CBD": ["TLRY", "CGC", "ACB", "MJ", "MSOS"],
    "飲食/QSR": ["MCD", "SBUX", "CMG", "DPZ", "YUM"],
    "スポーツベッティング": ["DKNG", "FLUT", "PENN", "MGM"],

    # ========================================
    # 新興テーマ 2026 (6 themes)
    # ========================================
    "AI PC/エッジAIデバイス": ["AAPL", "MSFT", "DELL", "HPQ", "QCOM", "AMD"],
    "合成生物学": ["CDXS", "DNA", "BEAM"],
    "長寿/アンチエイジング": ["ABBV", "REGN", "ALNY", "FATE"],
    "気候テック": ["ENPH", "RUN", "PLUG", "STEM", "TSLA"],
    "インドテック": ["INFY", "WIT", "IBN", "HDB", "INDA"],
    "日本株ADR": ["TM", "SONY", "MUFG", "NMR", "SMFG"],
}

# 期間定義 (日数)
PERIODS: dict[str, int] = {
    "1日": 1,
    "5日": 5,
    "2週間": 14,
    "1ヶ月": 30,
    "3ヶ月": 90,
}
