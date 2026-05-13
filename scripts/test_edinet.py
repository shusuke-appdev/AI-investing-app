import os

import edinet_tools

# Replace with an actual check if you have a mocked key or run it when set
os.environ["EDINET_API_KEY"] = os.environ.get("EDINET_API_KEY", "YOUR_API_KEY")

def test_edinet():
    try:
        toyota = edinet_tools.entity("7203")
        print(f"Company: {toyota.name}, Code: {getattr(toyota, 'edinet_code', 'N/A')}")
        docs = toyota.documents(days=365)
        print(f"Found {len(docs)} documents.")
        count = 0
        for doc in docs:
            # 決算関連のみ（四半期報告書 または 有価証券報告書）
            if "有価証券" in doc.doc_type_name or "四半期" in doc.doc_type_name:
                print(f"Parsing: {doc.doc_type_name} ({doc.filing_datetime})")
                report = doc.parse()
                print(f"  Sales: {getattr(report, 'net_sales', 'N/A')}")
                print(f"  OpInc: {getattr(report, 'operating_income', 'N/A')}")
                print(f"  Assets: {getattr(report, 'total_assets', 'N/A')}")
                count += 1
                if count >= 4:
                    break
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_edinet()
