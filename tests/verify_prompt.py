"""
プロンプト生成プロセスの統合テスト
"""
import sys
import os
from unittest.mock import MagicMock, patch

# パス設定
sys.path.append(os.getcwd())

# モック設定
sys.modules["streamlit"] = MagicMock()
sys.modules["google.generativeai"] = MagicMock()
sys.modules["src.earnings_data"] = MagicMock() # 追加
sys.modules["src.knowledge_storage"] = MagicMock() # 追加

from src.news_analyst import generate_market_recap

def test_prompt_generation():
    print("Testing generate_market_recap prompt generation...")
    
    # ダミーデータ
    market_data = {
        "S&P 500": {"price": 5000, "change": 1.5},
        "weekly_performance": {"S&P 500": "+2.0%", "Bitcoin": "+5.0%"},
        "trend_1mo": {
            "S&P 500": {"change_1mo": "+3%", "trend": "上昇", "start_date": "2024-01-01", "end_date": "2024-02-01"}
        }
    }
    
    news_data = [
        {"title": "Fed kept rates unchanged", "source": "GNews", "category": "BUSINESS", "summary": "The Federal Reserve..."},
        {"title": "Oil prices surge", "source": "YFinance", "related_ticker": "CL=F", "summary": "Crude oil jumped..."}
    ]
    
    option_analysis = [{"ticker": "SPY", "sentiment": "強気", "analysis": ["PCR low"]}]
    
    # テスト実行（APIコールはモックされているため、プロンプト構築までが検証される）
    try:
        # generate_market_recap内部でgenai.GenerativeModelが呼ばれるが、モック済み
        with patch("src.news_analyst.genai.GenerativeModel") as mock_model:
            mock_chat = MagicMock()
            mock_model.return_value = mock_chat
            mock_chat.generate_content.return_value.text = "Mock Report Content"

            result = generate_market_recap(market_data, news_data, option_analysis)
            
            # プロンプトが正しく渡されたか確認（引数の検証）
            args, _ = mock_chat.generate_content.call_args
            prompt = args[0]
            
            print("\n--- Prompt Verification ---")
            if "CROSS-ASSET LINKAGE FRAMEWORK" in prompt:
                print("[OK] Cross-Asset Framework included")
            else:
                print("[MISSING] Cross-Asset Framework MISSING")
                
            if "OUTPUT FORMAT (MARKDOWN) - 3 SECTIONS ONLY" in prompt:
                 print("[OK] 3-Section Format included")
            else:
                 print("[MISSING] 3-Section Format MISSING")
                 
            if "【週次パフォーマンス (1週間) - アセットクラス横断】" in prompt:
                print("[OK] Weekly Performance Context included")
            else:
                print("[MISSING] Weekly Performance Context MISSING")
            
            if "Bitcoin: +5.0%" in prompt:
                print("[OK] Weekly Data Values included")
            else:
                 print("[MISSING] Weekly Data Values MISSING")

            print("\nTest Finished Successfully")

    except Exception as e:
        print(f"Test Failed with error: {e}")
        raise e

if __name__ == "__main__":
    test_prompt_generation()
