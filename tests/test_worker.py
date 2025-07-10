import unittest
from src.worker import Worker
from src.queue_manager import FifoQueue
from src.data_model import Request

class TestWorker(unittest.TestCase):
    def setUp(self):
        self.task_queue: FifoQueue[Request] = FifoQueue()
        self.worker = Worker(worker_id=1, task_queue=self.task_queue)

    def test_worker_initialization(self):
        self.assertEqual(self.worker.worker_id, 1)
        self.assertIsNone(self.worker.current_task)
        self.assertEqual(self.worker.busy_until, 0.0)
        self.assertFalse(self.worker.is_busy(0.0))

    def test_process_task_empty_queue(self):
        completed_task = self.worker.process_task(current_time=0.0)
        self.assertIsNone(completed_task)
        self.assertIsNone(self.worker.current_task)
        self.assertFalse(self.worker.is_busy(0.0))

    def test_process_task_starts_and_completes(self):
        req1 = Request(user_id="user1", request_time=0.0, processing_time=2.0)
        self.task_queue.enqueue(req1)

        # 時刻 0.0: タスク開始
        self.assertIsNone(self.worker.process_task(current_time=0.0)) # タスク開始時は何も返さない
        self.assertIsNotNone(self.worker.current_task)
        self.assertEqual(self.worker.current_task, req1)
        self.assertEqual(self.worker.current_task.start_processing_time_by_worker, 0.0)
        self.assertEqual(self.worker.busy_until, 2.0)
        self.assertTrue(self.worker.is_busy(0.0))
        self.assertTrue(self.worker.is_busy(1.0))
        self.assertTrue(self.worker.is_busy(1.99))
        # is_busy は current_time < busy_until なので、ちょうど完了時刻では False になる
        self.assertFalse(self.worker.is_busy(2.0))


        # 時刻 1.0: 処理中なので新しいタスクは取らない (キューに次のタスクがあっても)
        req2 = Request(user_id="user2", request_time=0.5, processing_time=1.0)
        self.task_queue.enqueue(req2)
        self.assertIsNone(self.worker.process_task(current_time=1.0))
        self.assertEqual(self.worker.current_task, req1) # 依然としてreq1を処理中

        # 時刻 2.0: req1が完了
        completed_task = self.worker.process_task(current_time=2.0)
        self.assertIsNotNone(completed_task)
        self.assertEqual(completed_task, req1)
        self.assertEqual(completed_task.finish_processing_time_by_worker, 2.0)
        self.assertIsNone(self.worker.current_task) # タスク完了後はクリアされる
        self.assertFalse(self.worker.is_busy(2.0))


        # 時刻 2.0 (再度呼び出し): キューからreq2を取得して開始
        self.assertIsNone(self.worker.process_task(current_time=2.0)) # タスク開始時は何も返さない
        self.assertIsNotNone(self.worker.current_task)
        self.assertEqual(self.worker.current_task, req2)
        self.assertEqual(self.worker.current_task.start_processing_time_by_worker, 2.0)
        self.assertEqual(self.worker.busy_until, 3.0) # 2.0 + 1.0
        self.assertTrue(self.worker.is_busy(2.5))

        # 時刻 3.0: req2が完了
        completed_task_2 = self.worker.process_task(current_time=3.0)
        self.assertIsNotNone(completed_task_2)
        self.assertEqual(completed_task_2, req2)
        self.assertEqual(completed_task_2.finish_processing_time_by_worker, 3.0)
        self.assertIsNone(self.worker.current_task)
        self.assertFalse(self.worker.is_busy(3.0))
        self.assertTrue(self.task_queue.is_empty())


    def test_process_task_takes_from_queue_only_when_idle(self):
        req1 = Request(user_id="user1", request_time=0.0, processing_time=1.0)
        req2 = Request(user_id="user2", request_time=0.1, processing_time=1.0)
        self.task_queue.enqueue(req1)
        self.task_queue.enqueue(req2)

        # 時刻 0.0: req1 を開始
        self.assertIsNone(self.worker.process_task(current_time=0.0))
        self.assertEqual(self.worker.current_task, req1)
        self.assertEqual(self.worker.busy_until, 1.0)

        # 時刻 0.5: req1 を処理中。キューに req2 があっても新しいタスクは取らない
        self.assertIsNone(self.worker.process_task(current_time=0.5))
        self.assertEqual(self.worker.current_task, req1) # 変わらず req1

        # 時刻 1.0: req1 が完了。戻り値として完了タスクを返す
        completed = self.worker.process_task(current_time=1.0)
        self.assertEqual(completed, req1)
        self.assertEqual(completed.finish_processing_time_by_worker, 1.0)
        self.assertIsNone(self.worker.current_task) # current_taskはクリア

        # 時刻 1.0 (再度呼び出し): アイドルなので req2 を開始
        self.assertIsNone(self.worker.process_task(current_time=1.0)) # 開始時はNone
        self.assertEqual(self.worker.current_task, req2)
        self.assertEqual(self.worker.current_task.start_processing_time_by_worker, 1.0)
        self.assertEqual(self.worker.busy_until, 2.0)

    def test_is_busy_logic(self):
        self.assertFalse(self.worker.is_busy(0.0)) # 最初はアイドル

        req = Request("user1", 0.0, 2.0)
        self.task_queue.enqueue(req)
        self.worker.process_task(0.0) # タスク開始

        self.assertTrue(self.worker.is_busy(0.0))   # 開始直後
        self.assertTrue(self.worker.is_busy(0.1))
        self.assertTrue(self.worker.is_busy(1.0))
        self.assertTrue(self.worker.is_busy(1.999))
        self.assertFalse(self.worker.is_busy(2.0))  # busy_untilちょうどはビジーではない
        self.assertFalse(self.worker.is_busy(2.1))  # busy_until以降はビジーではない

        # タスク完了後
        self.worker.process_task(2.0) # タスク完了処理
        self.assertFalse(self.worker.is_busy(2.0))


if __name__ == '__main__':
    unittest.main()
