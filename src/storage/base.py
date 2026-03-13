from abc import ABC, abstractmethod
from typing import Any


class BaseStorage(ABC):
    """
    ストレージの基底インターフェース。
    PortfolioやKnowledgeなどのデータエンティティに対する共通のCRUD操作を定義します。
    """

    @abstractmethod
    def save(self, id: str, data: Any) -> bool:
        """データを保存または更新します"""
        pass

    @abstractmethod
    def load(self, id: str) -> Any | None:
        """IDでデータを取得します"""
        pass

    @abstractmethod
    def list_all(self) -> list[Any]:
        """全てのデータを取得します"""
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """IDでデータを削除します"""
        pass
