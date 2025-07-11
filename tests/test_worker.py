import unittest
from unittest.mock import MagicMock, patch
from src.worker import Worker
from src.queue_manager import FifoQueue
from src.data_model import Request
# from src.api_client import APIClient # WorkerはAPIClientのインスタンスを取るが、テストではモックする

class TestWorkerWithAPIClient(unittest.TestCase):
    def setUp(self):
        self.task_queue = FifoQueue[Request]()
        # APIClientをモック
        self.mock_api_client = MagicMock()
        # Workerの初期化時にモックAPIClientを渡す
        self.worker = Worker(worker_id=1, task_queue=self.task_queue, api_client=self.mock_api_client)

    def test_worker_initialization_with_mock_apiclient(self):
        self.assertEqual(self.worker.worker_id, 1)
        self.assertEqual(self.worker.api_client, self.mock_api_client)
        self.assertIsNone(self.worker.current_task)
        self.assertEqual(self.worker.busy_until, 0.0)
        self.assertFalse(self.worker.is_busy(0.0))

    def test_process_task_api_call_success(self):
        req1 = Request(user_id="user1", request_time=0.0, processing_time=2.0)
        self.task_queue.enqueue(req1)

        # APIClient.make_request が成功レスポンスを返すように設定
        expected_api_response = {"status": "success", "api_used_id": 1, "data": "response_data"}
        self.mock_api_client.make_request.return_value = expected_api_response

        # 時刻 0.0: タスク開始
        # process_task内で _perform_api_call が呼ばれ、それが mock_api_client.make_request を呼ぶ
        self.assertIsNone(self.worker.process_task(current_time=0.0))

        self.mock_api_client.make_request.assert_called_once_with({"user_id": "user1", "data": "sample_payload"})
        self.assertIsNotNone(self.worker.current_task)
        self.assertEqual(self.worker.current_task, req1)
        self.assertEqual(self.worker.current_task.start_processing_time_by_worker, 0.0)
        self.assertEqual(self.worker.current_task.used_api_id, 1) # used_api_idが設定されたか確認
        self.assertEqual(self.worker.busy_until, 2.0) # APIコール時間とは別に処理時間がある想定
        self.assertEqual(self.worker.task_processing_status, "success")
        self.assertTrue(self.worker.is_busy(1.0))

        # 時刻 2.0: req1が完了
        completed_task = self.worker.process_task(current_time=2.0)
        self.assertIsNotNone(completed_task)
        self.assertEqual(completed_task, req1)
        self.assertEqual(completed_task.finish_processing_time_by_worker, 2.0)
        # TODO: RequestオブジェクトにAPI処理結果を格納するフィールドがあれば、それもテスト
        # self.assertEqual(completed_task.api_status, "success")
        self.assertIsNone(self.worker.current_task)
        self.assertIsNone(self.worker.task_processing_status) # 完了後はクリアされる

    def test_process_task_api_call_failure_all_apis_unavailable(self):
        req1 = Request(user_id="user2", request_time=0.0, processing_time=1.5)
        self.task_queue.enqueue(req1)

        # APIClient.make_request が例外を発生させるように設定 (全APIがレート制限などの場合)
        self.mock_api_client.make_request.side_effect = Exception("All external APIs are unavailable or rate limited.")

        # 時刻 0.0: タスク開始
        self.assertIsNone(self.worker.process_task(current_time=0.0))

        self.mock_api_client.make_request.assert_called_once_with({"user_id": "user2", "data": "sample_payload"})
        self.assertIsNotNone(self.worker.current_task)
        self.assertEqual(self.worker.current_task, req1)
        self.assertEqual(self.worker.busy_until, 1.5) # API失敗でも処理時間は消費する想定
        self.assertEqual(self.worker.task_processing_status, "failed_api_limit")

        # 時刻 1.5: req1が完了 (APIコールは失敗したが、タスクとしては処理時間を終えた)
        completed_task = self.worker.process_task(current_time=1.5)
        self.assertIsNotNone(completed_task)
        self.assertEqual(completed_task, req1)
        # TODO: RequestオブジェクトにAPI処理結果を格納するフィールドがあれば、それもテスト
        # self.assertEqual(completed_task.api_status, "failed_api_limit")
        self.assertIsNone(self.worker.current_task)
        self.assertIsNone(self.worker.task_processing_status)

    def test_process_task_empty_queue_no_api_call(self):
        self.worker.process_task(current_time=0.0)
        self.mock_api_client.make_request.assert_not_called()
        self.assertIsNone(self.worker.current_task)

    def test_worker_busy_no_new_task_or_api_call(self):
        req1 = Request(user_id="user1", request_time=0.0, processing_time=2.0)
        self.task_queue.enqueue(req1)
        self.mock_api_client.make_request.return_value = {"status": "success"}

        # Start task req1
        self.worker.process_task(current_time=0.0)
        self.mock_api_client.make_request.assert_called_once() # Called for req1
        self.mock_api_client.reset_mock() # Reset call count for next assertion

        req2 = Request(user_id="user2", request_time=0.1, processing_time=1.0)
        self.task_queue.enqueue(req2)

        # At time 1.0, worker is still busy with req1
        self.worker.process_task(current_time=1.0)
        self.mock_api_client.make_request.assert_not_called() # Not called again as worker is busy
        self.assertEqual(self.worker.current_task, req1) # Still processing req1


# 既存のTestWorkerクラスもAPIClientをモックするように修正するか、
# この新しいクラスにテストを統合する必要がある。
# ここでは新しいクラス TestWorkerWithAPIClient を作成し、APIClient関連のテストを追加した。
# 既存のテストは、WorkerがAPIClientのモックインスタンスを受け取るように setUp を変更すれば、
# APIClientの呼び出しを伴わないロジック（キューからのデキュータイミングなど）はそのまま使える可能性がある。

# 既存のテストを活かすための修正例（TestWorkerのsetUpを変更）
class TestWorkerOriginalLogicWithMockAPI(unittest.TestCase):
    def setUp(self):
        self.task_queue: FifoQueue[Request] = FifoQueue()
        self.mock_api_client = MagicMock() # APIClientをモック
        # APIClient.make_requestが常に成功を返すようにデフォルト設定
        self.mock_api_client.make_request.return_value = {"status": "success", "api_used_id": 1, "data": "dummy_response"}
        self.worker = Worker(worker_id=1, task_queue=self.task_queue, api_client=self.mock_api_client)


    def test_worker_initialization(self): # 既存のテストケース
        self.assertEqual(self.worker.worker_id, 1)
        self.assertIsNone(self.worker.current_task)
        self.assertEqual(self.worker.busy_until, 0.0)
        self.assertFalse(self.worker.is_busy(0.0))

    def test_process_task_empty_queue(self): # 既存のテストケース
        completed_task = self.worker.process_task(current_time=0.0)
        self.assertIsNone(completed_task)
        self.assertIsNone(self.worker.current_task)
        self.assertFalse(self.worker.is_busy(0.0))
        self.mock_api_client.make_request.assert_not_called()


    def test_process_task_starts_and_completes(self): # 既存のテストケース（APIコールを考慮）
        req1 = Request(user_id="user1", request_time=0.0, processing_time=2.0)
        self.task_queue.enqueue(req1)

        # 時刻 0.0: タスク開始
        self.assertIsNone(self.worker.process_task(current_time=0.0))
        self.mock_api_client.make_request.assert_called_with({"user_id": "user1", "data": "sample_payload"})
        self.assertIsNotNone(self.worker.current_task)
        self.assertEqual(self.worker.current_task, req1)
        self.assertEqual(self.worker.current_task.start_processing_time_by_worker, 0.0)
        self.assertEqual(self.worker.busy_until, 2.0)
        self.assertTrue(self.worker.is_busy(1.0))


        # 時刻 1.0: 処理中
        self.mock_api_client.reset_mock() # APIコール数をリセット
        req2 = Request(user_id="user2", request_time=0.5, processing_time=1.0)
        self.task_queue.enqueue(req2)
        self.assertIsNone(self.worker.process_task(current_time=1.0))
        self.assertEqual(self.worker.current_task, req1)
        self.mock_api_client.make_request.assert_not_called() # 処理中なのでAPIコールなし

        # 時刻 2.0: req1が完了
        completed_task = self.worker.process_task(current_time=2.0)
        self.assertIsNotNone(completed_task)
        self.assertEqual(completed_task, req1)
        self.assertIsNone(self.worker.current_task)

        # 時刻 2.0 (再度呼び出し): req2を開始
        self.mock_api_client.reset_mock()
        self.assertIsNone(self.worker.process_task(current_time=2.0))
        self.mock_api_client.make_request.assert_called_with({"user_id": "user2", "data": "sample_payload"})
        self.assertIsNotNone(self.worker.current_task)
        self.assertEqual(self.worker.current_task, req2)
        self.assertEqual(self.worker.busy_until, 3.0) # 2.0 + 1.0

        # 時刻 3.0: req2が完了
        completed_task_2 = self.worker.process_task(current_time=3.0)
        self.assertIsNotNone(completed_task_2)
        self.assertEqual(completed_task_2, req2)
        self.assertIsNone(self.worker.current_task)
        self.assertTrue(self.task_queue.is_empty())

    # is_busy_logic はAPIコールの有無に直接依存しないため、大きな変更は不要かもしれないが、
    # process_task がAPIコールをするようになったので、その呼び出しを考慮する必要がある。
    def test_is_busy_logic(self):
        self.assertFalse(self.worker.is_busy(0.0))

        req = Request("user1", 0.0, 2.0)
        self.task_queue.enqueue(req)
        self.worker.process_task(0.0) # タスク開始、APIコール発生

        self.assertTrue(self.worker.is_busy(0.0))
        self.assertTrue(self.worker.is_busy(1.999))
        self.assertFalse(self.worker.is_busy(2.0))

        self.worker.process_task(2.0) # タスク完了処理
        self.assertFalse(self.worker.is_busy(2.0))


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
