import unittest
from src.data_model import Request

class TestRequest(unittest.TestCase):
    def test_request_creation(self):
        request = Request(user_id="test_user", request_time=1.0, processing_time=2.5)
        self.assertEqual(request.user_id, "test_user")
        self.assertEqual(request.request_time, 1.0)
        self.assertEqual(request.processing_time, 2.5)
        self.assertEqual(request.arrival_time_in_queue, 0.0) # 初期値の確認
        self.assertEqual(request.start_processing_time_by_worker, 0.0) # 初期値の確認
        self.assertEqual(request.finish_processing_time_by_worker, 0.0) # 初期値の確認
        self.assertIsNone(request.used_api_id) # used_api_id の初期値がNoneであることの確認

    def test_request_field_assignment(self):
        request = Request(user_id="test_user", request_time=1.0, processing_time=2.5)
        request.arrival_time_in_queue = 1.1
        request.start_processing_time_by_worker = 1.2
        request.finish_processing_time_by_worker = 3.7
        request.used_api_id = 1

        self.assertEqual(request.arrival_time_in_queue, 1.1)
        self.assertEqual(request.start_processing_time_by_worker, 1.2)
        self.assertEqual(request.finish_processing_time_by_worker, 3.7)
        self.assertEqual(request.used_api_id, 1) # used_api_id の値設定確認

if __name__ == '__main__':
    unittest.main()
