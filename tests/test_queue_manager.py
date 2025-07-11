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
        # テスト用のリクエストを作成 (Request のコンストラクタの引数を実際の定義に合わせる)
        # request_time は datetime オブジェクトが必要。sim_arrival_time を使うので、適当な値でよい。
        import datetime
        dummy_time = datetime.datetime.now(datetime.timezone.utc)
        self.req_short_1 = Request(user_id="user_short_1", request_time=dummy_time, sim_arrival_time=0, processing_time=10)
        self.req_short_2 = Request(user_id="user_short_2", request_time=dummy_time, sim_arrival_time=0, processing_time=19.9)
        self.req_long_1 = Request(user_id="user_long_1", request_time=dummy_time, sim_arrival_time=0, processing_time=20)
        self.req_long_2 = Request(user_id="user_long_2", request_time=dummy_time, sim_arrival_time=0, processing_time=30)
        self.req_pt_none = Request(user_id="user_pt_none", request_time=dummy_time, sim_arrival_time=0, processing_time=None)
        self.req_pt_zero = Request(user_id="user_pt_zero", request_time=dummy_time, sim_arrival_time=0, processing_time=0) # 0秒は優先

        # 元のテストで使われていた req_no_processing_time は、意図が processing_time=0 と同じか、
        # 属性がないケースを想定していたかによる。processing_time=0 は req_pt_zero でカバー。
        # 属性がないケースは DummyTask のテストでカバーされている。
        # よって、self.req_no_processing_time は削除またはコメントアウトでよい。
        # self.req_no_processing_time = Request(user_id="user_no_pt", request_id="r_no_pt", sim_arrival_time=0, processing_time=0)


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

    # 新しいテストメソッド
    def test_len_internal_queues_and_get_counts_initial(self):
        """初期状態での各キュー長とエンキューカウントのテスト"""
        pqs = self.priority_queue_strategy
        self.assertEqual(pqs.len_priority_queue(), 0)
        self.assertEqual(pqs.len_normal_queue(), 0)
        counts = pqs.get_queue_counts()
        self.assertEqual(counts["priority_enqueued"], 0)
        self.assertEqual(counts["normal_enqueued"], 0)

    def test_enqueue_updates_lengths_and_counts(self):
        """エンキューによる各キュー長と総エンキューカウントの更新テスト"""
        pqs = self.priority_queue_strategy

        # 1. 優先キューへエンキュー (req_short_1)
        pqs.enqueue(self.req_short_1)
        self.assertEqual(pqs.len_priority_queue(), 1)
        self.assertEqual(pqs.len_normal_queue(), 0)
        counts = pqs.get_queue_counts()
        self.assertEqual(counts["priority_enqueued"], 1)
        self.assertEqual(counts["normal_enqueued"], 0)
        self.assertEqual(len(pqs), 1)

        # 2. 通常キューへエンキュー (req_long_1)
        pqs.enqueue(self.req_long_1)
        self.assertEqual(pqs.len_priority_queue(), 1)
        self.assertEqual(pqs.len_normal_queue(), 1)
        counts = pqs.get_queue_counts()
        self.assertEqual(counts["priority_enqueued"], 1)
        self.assertEqual(counts["normal_enqueued"], 1)
        self.assertEqual(len(pqs), 2)

        # 3. 再度優先キューへエンキュー (req_short_2)
        pqs.enqueue(self.req_short_2)
        self.assertEqual(pqs.len_priority_queue(), 2)
        self.assertEqual(pqs.len_normal_queue(), 1)
        counts = pqs.get_queue_counts()
        self.assertEqual(counts["priority_enqueued"], 2)
        self.assertEqual(counts["normal_enqueued"], 1)
        self.assertEqual(len(pqs), 3)

        # 4. processing_time が None の場合 (req_pt_none -> 通常キューへ)
        pqs.enqueue(self.req_pt_none)
        self.assertEqual(pqs.len_priority_queue(), 2)
        self.assertEqual(pqs.len_normal_queue(), 2) # normal_len が増える
        counts = pqs.get_queue_counts()
        self.assertEqual(counts["priority_enqueued"], 2)
        self.assertEqual(counts["normal_enqueued"], 2) # normal_enqueued が増える
        self.assertEqual(len(pqs), 4)

        # 5. processing_time が 0 の場合 (req_pt_zero -> 優先キューへ)
        pqs.enqueue(self.req_pt_zero)
        self.assertEqual(pqs.len_priority_queue(), 3) # priority_len が増える
        self.assertEqual(pqs.len_normal_queue(), 2)
        counts = pqs.get_queue_counts()
        self.assertEqual(counts["priority_enqueued"], 3) # priority_enqueued が増える
        self.assertEqual(counts["normal_enqueued"], 2)
        self.assertEqual(len(pqs), 5)


    def test_dequeue_does_not_affect_total_enqueued_counts(self):
        """デキュー操作は総エンキューカウントに影響しないことをテスト"""
        pqs = self.priority_queue_strategy
        pqs.enqueue(self.req_short_1) # P:1, N:0 -> counts P:1, N:0
        pqs.enqueue(self.req_long_1)  # P:1, N:1 -> counts P:1, N:1

        initial_counts = pqs.get_queue_counts()
        self.assertEqual(initial_counts["priority_enqueued"], 1)
        self.assertEqual(initial_counts["normal_enqueued"], 1)

        pqs.dequeue() # 1つデキュー
        counts_after_dequeue1 = pqs.get_queue_counts()
        self.assertEqual(counts_after_dequeue1["priority_enqueued"], 1) # 変わらない
        self.assertEqual(counts_after_dequeue1["normal_enqueued"], 1) # 変わらない
        self.assertEqual(len(pqs), 1)

        pqs.dequeue() # もう1つデキュー
        counts_after_dequeue2 = pqs.get_queue_counts()
        self.assertEqual(counts_after_dequeue2["priority_enqueued"], 1) # 変わらない
        self.assertEqual(counts_after_dequeue2["normal_enqueued"], 1) # 変わらない
        self.assertEqual(len(pqs), 0)
        self.assertTrue(pqs.is_empty())


if __name__ == "__main__":
    unittest.main()
