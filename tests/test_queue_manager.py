import unittest
from unittest.mock import patch  # patch をインポート

from src.data_model import Request  # テストでRequestオブジェクトを使用するため
from src.queue_manager import FifoQueue, PriorityQueueStrategy  # PriorityQueueStrategy をインポート


class TestFifoQueue(unittest.TestCase):
    def test_enqueue_dequeue(self):
        queue: FifoQueue[int] = FifoQueue()
        self.assertTrue(queue.is_empty())
        self.assertTrue(queue.enqueue(1))
        self.assertFalse(queue.is_empty())
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue.dequeue(), 1)
        self.assertTrue(queue.is_empty())
        self.assertEqual(len(queue), 0)
        self.assertIsNone(queue.dequeue())

    def test_fifo_order(self):
        queue: FifoQueue[str] = FifoQueue()
        queue.enqueue("a")
        queue.enqueue("b")
        queue.enqueue("c")
        self.assertEqual(queue.dequeue(), "a")
        self.assertEqual(queue.dequeue(), "b")
        self.assertEqual(queue.dequeue(), "c")
        self.assertTrue(queue.is_empty())

    def test_peek(self):
        queue: FifoQueue[int] = FifoQueue()
        self.assertIsNone(queue.peek())
        queue.enqueue(10)
        self.assertEqual(queue.peek(), 10)
        self.assertEqual(len(queue), 1)  # peekしても要素は減らない
        queue.enqueue(20)
        self.assertEqual(queue.peek(), 10)  # 先頭は変わらない
        self.assertEqual(queue.dequeue(), 10)
        self.assertEqual(queue.peek(), 20)

    def test_max_size(self):
        queue: FifoQueue[Request] = FifoQueue(max_size=2)
        req1 = Request("u1", 0, 1)
        req2 = Request("u2", 0, 1)
        req3 = Request("u3", 0, 1)

        self.assertTrue(queue.enqueue(req1))
        self.assertFalse(queue.is_full())
        self.assertTrue(queue.enqueue(req2))
        self.assertTrue(queue.is_full())
        self.assertFalse(queue.enqueue(req3))  # 満杯なので追加できない
        self.assertTrue(queue.is_full())
        self.assertEqual(len(queue), 2)

        self.assertEqual(queue.dequeue(), req1)
        self.assertFalse(queue.is_full())
        self.assertTrue(queue.enqueue(req3))  # 空きができたので追加できる
        self.assertEqual(len(queue), 2)
        self.assertTrue(queue.is_full())

    def test_no_max_size(self):
        queue: FifoQueue[int] = FifoQueue()  # max_size指定なし
        self.assertFalse(queue.is_full())
        for i in range(1000):
            self.assertTrue(queue.enqueue(i))
        self.assertEqual(len(queue), 1000)
        self.assertFalse(queue.is_full())  # max_sizeがなければ常にFalse


class TestPriorityQueueStrategy(unittest.TestCase):
    def setUp(self):
        self.priority_queue_strategy = PriorityQueueStrategy(priority_threshold_seconds=20.0, priority_bias=0.8)
        # テスト用のリクエストを作成
        self.req_short_1 = Request(user_id="user_short_1", request_time=0, processing_time=10)  # 優先
        self.req_short_2 = Request(user_id="user_short_2", request_time=0, processing_time=19.9)  # 優先
        self.req_long_1 = Request(user_id="user_long_1", request_time=0, processing_time=20)  # 通常
        self.req_long_2 = Request(user_id="user_long_2", request_time=0, processing_time=30)  # 通常
        self.req_no_processing_time = Request(
            user_id="user_no_pt", request_time=0, processing_time=0
        )  # processing_timeがない場合を模倣 (実際には0)
        # delattr(self.req_no_processing_time, 'processing_time') # 属性自体を削除するテストは enqueue の実装に依る

    def test_enqueue_distribution(self):
        """processing_timeに基づいて正しくキューに振り分けられるかテスト"""
        self.priority_queue_strategy.enqueue(self.req_short_1)
        self.assertEqual(len(self.priority_queue_strategy.priority_queue), 1)
        self.assertEqual(len(self.priority_queue_strategy.normal_queue), 0)
        self.assertEqual(self.priority_queue_strategy.priority_queue.peek(), self.req_short_1)

        self.priority_queue_strategy.enqueue(self.req_long_1)
        self.assertEqual(len(self.priority_queue_strategy.priority_queue), 1)
        self.assertEqual(len(self.priority_queue_strategy.normal_queue), 1)
        self.assertEqual(self.priority_queue_strategy.normal_queue.peek(), self.req_long_1)

        self.priority_queue_strategy.enqueue(self.req_short_2)
        self.assertEqual(len(self.priority_queue_strategy.priority_queue), 2)
        self.assertEqual(len(self.priority_queue_strategy.normal_queue), 1)

        self.priority_queue_strategy.enqueue(self.req_long_2)
        self.assertEqual(len(self.priority_queue_strategy.priority_queue), 2)
        self.assertEqual(len(self.priority_queue_strategy.normal_queue), 2)

    def test_enqueue_item_without_processing_time_attr(self):
        """processing_time属性がないアイテムは通常キューに入ることを確認（現在の仕様）"""

        # Requestモデルは必ずprocessing_timeを持つので、ダミーオブジェクトでテスト
        class DummyTask:
            def __init__(self, user_id):
                self.user_id = user_id

        dummy_task = DummyTask("dummy1")
        self.priority_queue_strategy.enqueue(dummy_task)
        self.assertEqual(len(self.priority_queue_strategy.priority_queue), 0)
        self.assertEqual(len(self.priority_queue_strategy.normal_queue), 1)
        self.assertEqual(self.priority_queue_strategy.normal_queue.peek(), dummy_task)

    def test_is_empty_and_len(self):
        """is_emptyと__len__が正しく機能するかテスト"""
        self.assertTrue(self.priority_queue_strategy.is_empty())
        self.assertEqual(len(self.priority_queue_strategy), 0)

        self.priority_queue_strategy.enqueue(self.req_short_1)
        self.assertFalse(self.priority_queue_strategy.is_empty())
        self.assertEqual(len(self.priority_queue_strategy), 1)

        self.priority_queue_strategy.enqueue(self.req_long_1)
        self.assertFalse(self.priority_queue_strategy.is_empty())
        self.assertEqual(len(self.priority_queue_strategy), 2)

        self.priority_queue_strategy.dequeue()
        self.assertEqual(len(self.priority_queue_strategy), 1)
        self.priority_queue_strategy.dequeue()
        self.assertEqual(len(self.priority_queue_strategy), 0)
        self.assertTrue(self.priority_queue_strategy.is_empty())

    def test_dequeue_empty_returns_none(self):
        """空のキューからデキューするとNoneが返ることをテスト"""
        self.assertIsNone(self.priority_queue_strategy.dequeue())

    # dequeueの確率的な部分とフォールバックのテストは random.random をモックする必要がある
    # それらは次のステップで追加する

    @patch("random.random")
    def test_dequeue_logic_with_mocked_random(self, mock_random):
        """random.randomをモックしてdequeueのロジックをテスト"""
        # --- 両方のキューにアイテムがある場合 ---
        self.priority_queue_strategy.enqueue(self.req_short_1)  # Prio
        self.priority_queue_strategy.enqueue(self.req_long_1)  # Normal

        # Case 1: random < bias (0.8) -> 優先キューからデキュー
        mock_random.return_value = 0.5  # < 0.8
        dequeued_item = self.priority_queue_strategy.dequeue()
        self.assertEqual(dequeued_item, self.req_short_1)
        self.assertEqual(len(self.priority_queue_strategy.priority_queue), 0)
        self.assertEqual(len(self.priority_queue_strategy.normal_queue), 1)

        # Case 2: random >= bias (0.8) -> 通常キューからデキュー
        self.priority_queue_strategy.enqueue(self.req_short_2)  # Prioに戻す
        mock_random.return_value = 0.9  # >= 0.8
        dequeued_item = self.priority_queue_strategy.dequeue()
        self.assertEqual(dequeued_item, self.req_long_1)
        self.assertEqual(len(self.priority_queue_strategy.priority_queue), 1)  # req_short_2が残る
        self.assertEqual(len(self.priority_queue_strategy.normal_queue), 0)

        # --- 片方のキューが空の場合のフォールバック ---
        # Reset queues
        self.priority_queue_strategy.priority_queue = FifoQueue()
        self.priority_queue_strategy.normal_queue = FifoQueue()

        # Case 3: 優先を選択、しかし優先は空 -> 通常からデキュー
        self.priority_queue_strategy.enqueue(self.req_long_1)  # Normalのみ
        mock_random.return_value = 0.5  # 優先を選択
        dequeued_item = self.priority_queue_strategy.dequeue()
        self.assertEqual(dequeued_item, self.req_long_1)
        self.assertTrue(self.priority_queue_strategy.is_empty())

        # Case 4: 通常を選択、しかし通常は空 -> 優先からデキュー
        self.priority_queue_strategy.enqueue(self.req_short_1)  # Prioのみ
        mock_random.return_value = 0.9  # 通常を選択
        dequeued_item = self.priority_queue_strategy.dequeue()
        self.assertEqual(dequeued_item, self.req_short_1)
        self.assertTrue(self.priority_queue_strategy.is_empty())

        # --- 両方空の場合 (再確認) ---
        self.assertIsNone(self.priority_queue_strategy.dequeue())  # 両方空

        # --- 優先のみアイテムがあり、通常を選択したがフォールバック ---
        self.priority_queue_strategy.enqueue(self.req_short_1)  # Prio
        mock_random.return_value = 0.9  # 通常を選択 (しかし通常は空)
        dequeued_item = self.priority_queue_strategy.dequeue()
        self.assertEqual(dequeued_item, self.req_short_1)
        self.assertTrue(self.priority_queue_strategy.is_empty())

        # --- 通常のみアイテムがあり、優先を選択したがフォールバック ---
        self.priority_queue_strategy.enqueue(self.req_long_1)  # Normal
        mock_random.return_value = 0.5  # 優先を選択 (しかし優先は空)
        dequeued_item = self.priority_queue_strategy.dequeue()
        self.assertEqual(dequeued_item, self.req_long_1)
        self.assertTrue(self.priority_queue_strategy.is_empty())

    def test_dequeue_only_priority_has_items(self):
        """優先キューのみにアイテムがある場合、常に優先キューからデキューされることをテスト"""
        self.priority_queue_strategy.enqueue(self.req_short_1)
        self.priority_queue_strategy.enqueue(self.req_short_2)
        self.assertEqual(self.priority_queue_strategy.dequeue(), self.req_short_1)
        self.assertEqual(self.priority_queue_strategy.dequeue(), self.req_short_2)
        self.assertIsNone(self.priority_queue_strategy.dequeue())

    def test_dequeue_only_normal_has_items(self):
        """通常キューのみにアイテムがある場合、常に通常キューからデキューされることをテスト"""
        self.priority_queue_strategy.enqueue(self.req_long_1)
        self.priority_queue_strategy.enqueue(self.req_long_2)
        self.assertEqual(self.priority_queue_strategy.dequeue(), self.req_long_1)
        self.assertEqual(self.priority_queue_strategy.dequeue(), self.req_long_2)
        self.assertIsNone(self.priority_queue_strategy.dequeue())


if __name__ == "__main__":
    unittest.main()
