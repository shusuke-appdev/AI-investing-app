"""
EDINET DB API Client
日本企業の財務情報をEDINET（金融庁）から取得・解析する。
"""

import os

try:
    import edinet_tools
except ImportError:
    edinet_tools = None

from src.cache import ttl_cache
from src.constants import CACHE_TTL_DAILY
from src.log_config import get_logger
from src.settings_storage import get_edinet_api_key

logger = get_logger(__name__)


def is_configured() -> bool:
    """EDINET API キーが設定されているかどうかを返す"""
    if edinet_tools is None:
        return False

    api_key = get_edinet_api_key()
    if api_key:
        os.environ["EDINET_API_KEY"] = api_key
        return True
    return False


@ttl_cache(ttl=CACHE_TTL_DAILY)
def get_company_finance(ticker: str, limit: int = 4) -> dict | None:
    """
    指定した企業の直近の財務情報（売上高、営業利益など）を取得する。
    limit: 取得する四半期/年次報告書の最大数 (今回は直近4四半期)
    """
    if not is_configured():
        logger.warning("EDINET API Key is not configured.")
        return None

    # 証券コードから数字部分を抽出 (例: "7203.T" -> "7203")
    code = "".join(filter(str.isdigit, str(ticker)))
    if len(code) != 4:
        logger.debug(
            f"Ticker {ticker} does not appear to be a standard 4-digit Japanese stock code."
        )
        return None

    try:
        # edinet-tools を使って企業を検索
        entity = edinet_tools.entity(code)
        if not entity:
            logger.warning(f"Could not find EDINET entity for code {code}")
            return None

        # 直近1.5年(500日)の書類を取得して、4つ分の報告書を抽出する
        docs = entity.documents(days=500)

        financial_history = []
        for doc in docs:
            # 決算関連のみ（四半期報告書 または 有価証券報告書）
            title = doc.doc_type_name or ""
            if "有価証券報告書" in title or "四半期報告書" in title:
                try:
                    report = doc.parse()

                    # 属性の取得 (XBRLパーサー側で対応している属性)
                    net_sales = getattr(report, "net_sales", None)
                    operating_income = getattr(report, "operating_income", None)
                    net_income = getattr(report, "net_income", None)
                    total_assets = getattr(report, "total_assets", None)
                    net_assets = getattr(report, "net_assets", None)

                    # 売上高が存在する（有効な財務諸表を含んでいる）場合のみ追加
                    if net_sales is not None:
                        record = {
                            "date": doc.period_end
                            if hasattr(doc, "period_end")
                            else (
                                doc.filing_datetime.strftime("%Y-%m-%d")
                                if hasattr(doc.filing_datetime, "strftime")
                                else str(doc.filing_datetime)
                            ),
                            "type": title,
                            "net_sales": net_sales,
                            "operating_income": operating_income,
                            "net_income": net_income,
                            "total_assets": total_assets,
                            "net_assets": net_assets,
                        }
                        financial_history.append(record)

                        if len(financial_history) >= limit:
                            break

                except Exception as parse_err:
                    logger.debug(f"Failed to parse report {doc.doc_id}: {parse_err}")

        return {
            "company_name": entity.name,
            "edinet_code": getattr(entity, "edinet_code", None),
            "financials": financial_history,
        }

    except Exception as e:
        logger.error(f"EDINET fetch failed for {ticker}: {e}")
        return None
