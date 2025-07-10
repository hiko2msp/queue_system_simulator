import unittest
from src.queue_manager import FifoQueue
from src.data_model import Request # テストでRequestオブジェクトを使用するため

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
        self.assertEqual(len(queue), 1) # peekしても要素は減らない
        queue.enqueue(20)
        self.assertEqual(queue.peek(), 10) # 先頭は変わらない
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
        self.assertFalse(queue.enqueue(req3)) # 満杯なので追加できない
        self.assertTrue(queue.is_full())
        self.assertEqual(len(queue), 2)

        self.assertEqual(queue.dequeue(), req1)
        self.assertFalse(queue.is_full())
        self.assertTrue(queue.enqueue(req3)) # 空きができたので追加できる
        self.assertEqual(len(queue), 2)
        self.assertTrue(queue.is_full())

    def test_no_max_size(self):
        queue: FifoQueue[int] = FifoQueue() # max_size指定なし
        self.assertFalse(queue.is_full())
        for i in range(1000):
            self.assertTrue(queue.enqueue(i))
        self.assertEqual(len(queue), 1000)
        self.assertFalse(queue.is_full()) # max_sizeがなければ常にFalse

if __name__ == '__main__':
    unittest.main()
