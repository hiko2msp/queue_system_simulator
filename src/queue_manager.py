from collections import deque
from typing import Generic, TypeVar

T = TypeVar("T")


class FifoQueue(Generic[T]):
    """
    FIFO (First-In, First-Out) の原則に従うジェネリックなキュークラス。
    オプションで最大サイズを設定できます。

    Attributes:
        max_size (Optional[int]): キューの最大サイズ。Noneの場合は無制限。
    """

    def __init__(self, max_size: int | None = None):
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

    def dequeue(self) -> T | None:
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

    def peek(self) -> T | None:
        """
        キューの先頭にあるアイテムを、キューから削除せずに返します。
        キューが空の場合はNoneを返します。

        Returns:
            Optional[T]: キューの先頭のアイテム。キューが空の場合はNone。
        """
        if not self.is_empty():
            return self._queue[0]
        return None


class PriorityQueueStrategy(Generic[T]):
    """
    優先度付きキュー戦略。
    処理時間が短いタスクを優先キューに、それ以外を通常キューに入れる。
    デキュー時、優先キューと通常キューを確率的に選択する。
    """

    def __init__(self, priority_threshold_seconds: float = 20.0, priority_bias: float = 0.8):
        """
        PriorityQueueStrategyのコンストラクタ。

        Args:
            priority_threshold_seconds (float): この秒数未満の処理時間のタスクが優先キューに入る。
            priority_bias (float): 優先キューからデキューする確率 (0.0 から 1.0)。
                                     通常キューからのデキュー確率は (1.0 - priority_bias)。
        """
        self.priority_queue: FifoQueue[T] = FifoQueue()
        self.normal_queue: FifoQueue[T] = FifoQueue()
        self.priority_threshold_seconds = priority_threshold_seconds
        self.priority_bias = priority_bias
        if not (0.0 <= priority_bias <= 1.0):
            raise ValueError("priority_biasは0.0から1.0の間である必要があります。")

        # 統計情報用カウンター
        self.priority_enqueued_count = 0
        self.normal_enqueued_count = 0

    def enqueue(self, item: T) -> bool:
        """
        タスクを適切なキューに追加します。
        Requestオブジェクトであることを期待し、processing_time属性を参照します。

        Args:
            item (T): キューに追加するアイテム。Request型を想定。

        Returns:
            bool: アイテムが正常に追加された場合はTrue。
        """
        # itemがRequest型でprocessing_time属性を持つことを期待
        if hasattr(item, "processing_time") and isinstance(item.processing_time, (int, float)):
            if item.processing_time < self.priority_threshold_seconds:
                enqueued = self.priority_queue.enqueue(item)
                if enqueued:
                    self.priority_enqueued_count += 1
                return enqueued
            else:
                enqueued = self.normal_queue.enqueue(item)
                if enqueued:
                    self.normal_enqueued_count += 1
                return enqueued
        else:
            # processing_timeがない、または不正な場合は通常キューに入れるか、エラーを発生させる
            # ここでは通常キューに入れる仕様とする
            # warnings.warn("Item does not have a valid 'processing_time' attribute, enqueuing to normal queue.")
            enqueued = self.normal_queue.enqueue(item)
            if enqueued:
                self.normal_enqueued_count += 1 # こちらもカウント
            return enqueued

    def dequeue(self) -> T | None:
        """
        優先度と確率に基づいてキューからアイテムをデキューします。
        80%の確率で優先キューから、20%の確率で通常キューから試行します。
        選択したキューが空の場合、もう一方のキューからデキューします。

        Returns:
            Optional[T]: デキューされたアイテム。両方のキューが空の場合はNone。
        """
        import random  # randomモジュールをインポート

        priority_q_empty = self.priority_queue.is_empty()
        normal_q_empty = self.normal_queue.is_empty()

        if priority_q_empty and normal_q_empty:
            return None

        # どちらか一方が空の場合の処理
        if priority_q_empty:
            return self.normal_queue.dequeue()
        if normal_q_empty:
            return self.priority_queue.dequeue()

        # 両方にアイテムがある場合、確率に基づいて選択
        if random.random() < self.priority_bias:  # 優先キューを試行
            return self.priority_queue.dequeue()
        else:  # 通常キューを試行
            return self.normal_queue.dequeue()
        # Note: 上記のロジックだと、例えば優先キューを試行して空だった場合に通常キューにフォールバックしない。
        # 要件「選択したキューが空の場合、もう一方のキューからデキューします」を満たすように修正する。

    def dequeue_corrected(self) -> T | None:
        """
        優先度と確率に基づいてキューからアイテムをデキューします。(修正版)
        指定された確率で優先キューまたは通常キューを選択し、
        もし選択したキューが空であれば、もう一方のキューからデキューを試みます。

        Returns:
            Optional[T]: デキューされたアイテム。両方のキューが空の場合はNone。
        """
        import random

        priority_q_has_items = not self.priority_queue.is_empty()
        normal_q_has_items = not self.normal_queue.is_empty()

        if not priority_q_has_items and not normal_q_has_items:
            return None

        chose_priority = random.random() < self.priority_bias

        if chose_priority:
            if priority_q_has_items:
                return self.priority_queue.dequeue()
            elif normal_q_has_items:  # 優先キューが空なら通常キューから
                return self.normal_queue.dequeue()
        else:  # chose_normal
            if normal_q_has_items:
                return self.normal_queue.dequeue()
            elif priority_q_has_items:  # 通常キューが空なら優先キューから
                return self.priority_queue.dequeue()

        return None  # 両方空の場合(最初のチェックで捕捉されるはずだが念のため)

    # dequeueメソッドを修正版に置き換える
    dequeue = dequeue_corrected

    def is_empty(self) -> bool:
        """
        両方のキューが空かどうかを確認します。

        Returns:
            bool: 両方のキューが空の場合はTrue、そうでない場合はFalse。
        """
        return self.priority_queue.is_empty() and self.normal_queue.is_empty()

    def __len__(self) -> int:
        """
        両方のキュー内の現在のアイテムの合計数を返します。

        Returns:
            int: 両方のキューの合計サイズ。
        """
        return len(self.priority_queue) + len(self.normal_queue)

    def peek_priority(self) -> T | None:
        """優先キューの先頭を覗き見します。"""
        return self.priority_queue.peek()

    def peek_normal(self) -> T | None:
        """通常キューの先頭を覗き見します。"""
        return self.normal_queue.peek()

    def is_full(self) -> bool:
        """
        キューが満杯かどうかを確認します。
        現在のPriorityQueueStrategyは内部キューのサイズ制限をサポートしていないため、
        常にFalse（満杯ではない）を返します。
        将来的にサイズ制限を導入する場合は、このメソッドのロジックを修正する必要があります。
        """
        return False  # サイズ制限がないため、常に満杯ではない

    # 新しいメソッド
    def len_priority_queue(self) -> int:
        """優先キューの現在の長さを返します。"""
        return len(self.priority_queue)

    def len_normal_queue(self) -> int:
        """通常キューの現在の長さを返します。"""
        return len(self.normal_queue)

    def get_queue_counts(self) -> dict[str, int]:
        """
        各内部キューにエンキューされたリクエストの総数を返します。
        Returns:
            Dict[str, int]: キーが "priority_enqueued", "normal_enqueued" の辞書。
        """
        return {
            "priority_enqueued": self.priority_enqueued_count,
            "normal_enqueued": self.normal_enqueued_count,
        }
