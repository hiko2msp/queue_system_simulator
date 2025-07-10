from collections import deque
from typing import Optional, TypeVar, Generic

T = TypeVar('T')

class FifoQueue(Generic[T]):
    """
    FIFO (First-In, First-Out) の原則に従うジェネリックなキュークラス。
    オプションで最大サイズを設定できます。

    Attributes:
        max_size (Optional[int]): キューの最大サイズ。Noneの場合は無制限。
    """
    def __init__(self, max_size: Optional[int] = None):
        """
        FifoQueueのコンストラクタ。

        Args:
            max_size (Optional[int]): キューが保持できるアイテムの最大数。
                                      Noneの場合、キューのサイズは無制限。
        """
        self._queue: deque[T] = deque()
        self.max_size = max_size

    def enqueue(self, item: T) -> bool:
        """
        キューの末尾にアイテムを追加します。

        Args:
            item (T): キューに追加するアイテム。

        Returns:
            bool: アイテムが正常に追加された場合はTrue。
                  キューがmax_sizeに達していて追加できなかった場合はFalse。
        """
        if self.max_size is not None and len(self._queue) >= self.max_size:
            return False  # キューが満杯
        self._queue.append(item)
        return True

    def dequeue(self) -> Optional[T]:
        """
        キューの先頭からアイテムを取り出し、そのアイテムを返します。
        キューが空の場合はNoneを返します。

        Returns:
            Optional[T]: キューの先頭のアイテム。キューが空の場合はNone。
        """
        if not self.is_empty():
            return self._queue.popleft()
        return None

    def is_empty(self) -> bool:
        """
        キューが空かどうかを確認します。

        Returns:
            bool: キューが空の場合はTrue、そうでない場合はFalse。
        """
        return len(self._queue) == 0

    def is_full(self) -> bool:
        """
        キューが満杯（現在のサイズがmax_size以上）かどうかを確認します。
        max_sizeが設定されていない場合、このメソッドは常にFalseを返します。

        Returns:
            bool: キューが満杯の場合はTrue、そうでない場合はFalse。
        """
        if self.max_size is None:
            return False
        return len(self._queue) >= self.max_size

    def __len__(self) -> int:
        """
        キュー内の現在のアイテム数を返します。

        Returns:
            int: キューの現在のサイズ。
        """
        return len(self._queue)

    def peek(self) -> Optional[T]:
        """
        キューの先頭にあるアイテムを、キューから削除せずに返します。
        キューが空の場合はNoneを返します。

        Returns:
            Optional[T]: キューの先頭のアイテム。キューが空の場合はNone。
        """
        if not self.is_empty():
            return self._queue[0]
        return None
