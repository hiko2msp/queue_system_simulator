import unittest
from unittest.mock import patch, MagicMock
from src.api_client import APIClient
# from config import settings as test_settings # これは直接使わない

class TestAPIClient(unittest.TestCase):

    # setUp と tearDown は、モジュールレベルの定数をパッチするため、ここでは不要。
    # 各テストメソッドで直接パッチする。

    @patch('src.api_client.EXTERNAL_API_RPM_LIMIT', 10)
    @patch('src.api_client.NUM_EXTERNAL_APIS', 3)
    @patch('src.api_client.time') # timeモジュール自体ではなく、time.time()をモックするためにtime.timeをパッチ
    def test_initialization_with_settings(self, mock_time_module_time_method):
        # mock_time_module_time_method は src.api_client.time.time のモック
        client = APIClient()
        self.assertEqual(client.num_apis, 3)
        self.assertEqual(client.rpm_limit, 10)
        self.assertEqual(len(client.api_endpoints), 3)
        self.assertEqual(client.api_endpoints[0], "https://api.example.com/v1/endpoint1")

    @patch('src.api_client.EXTERNAL_API_RPM_LIMIT', 2)
    @patch('src.api_client.NUM_EXTERNAL_APIS', 1)
    @patch('src.api_client.time')
    def test_rate_limit_single_api(self, mock_time_module):
        mock_time_module.time.side_effect = [t/10.0 for t in range(100)] # time.time()が返す値
        client = APIClient()

        response1 = client.make_request({"data": "req1"})
        self.assertEqual(response1["api_used_id"], 1)

        response2 = client.make_request({"data": "req2"})
        self.assertEqual(response2["api_used_id"], 1)

        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req3"})
        self.assertEqual(len(client.request_timestamps[0]), 2)


    @patch('src.api_client.EXTERNAL_API_RPM_LIMIT', 1)
    @patch('src.api_client.NUM_EXTERNAL_APIS', 2)
    @patch('src.api_client.time')
    def test_fallback_mechanism(self, mock_time_module):
        mock_time_module.time.side_effect = [t * 0.1 for t in range(100)]
        client = APIClient()

        # 1回目: API 1 を使用
        # print("Fallback test: Request 1")
        response1 = client.make_request({"data": "req1_api1"})
        self.assertEqual(response1["api_used_id"], 1)
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 0)
        # APIClientのcurrent_api_indexは成功したAPIを指すはず (ここでは0)

        # 2回目: API 1 はレート制限、API 2 を使用
        # print("Fallback test: Request 2")
        response2 = client.make_request({"data": "req2_api2"})
        self.assertEqual(response2["api_used_id"], 2) # API 2 が使われる
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 1)
        # current_api_index は 1 を指すはず

        # 3回目: API 1, API 2 ともにレート制限 -> 例外
        # print("Fallback test: Request 3")
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req3_fail"})
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 1)


    @patch('src.api_client.EXTERNAL_API_RPM_LIMIT', 1)
    @patch('src.api_client.NUM_EXTERNAL_APIS', 2)
    @patch('src.api_client.time')
    def test_all_apis_rate_limited_then_exception(self, mock_time_module):
        mock_time_module.time.side_effect = [t * 0.1 for t in range(100)]
        client = APIClient()

        # API 1 を使用 (成功)
        client.make_request({"data": "req1"}) # API 1 (index 0) を使用, current_api_index = 0
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 0)


        # API 2 を使用 (成功)
        # make_request は (initial_api_index + attempts) % self.num_apis で試す
        # initial_api_index は self.current_api_index (前回成功したAPIインデックス)
        # 前回 API 0 が成功したので、次は API 0 から試行 -> レート超過
        # 次に API 1 を試行 -> 成功
        client.make_request({"data": "req2"}) # API 2 (index 1) を使用, current_api_index = 1
        self.assertEqual(len(client.request_timestamps[0]), 1) # API 0 は変わらず
        self.assertEqual(len(client.request_timestamps[1]), 1) # API 1 が使われる


        # 3回目のリクエスト (両APIともレート制限により例外)
        # 前回 API 1 が成功したので、次は API 1 から試行 -> レート超過
        # 次に API 0 を試行 -> レート超過
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req3"})
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 1)


    @patch('src.api_client.EXTERNAL_API_RPM_LIMIT', 1)
    @patch('src.api_client.NUM_EXTERNAL_APIS', 1)
    @patch('src.api_client.time')
    def test_rate_limit_reset_after_one_minute(self, mock_time_module):
        client = APIClient()

        # 最初の時間
        mock_time_module.time.return_value = 0.0
        response1 = client.make_request({"data": "req1"})
        self.assertEqual(response1["api_used_id"], 1)
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(client.request_timestamps[0][0], 0.0)

        # 10秒経過 (レート制限内)
        mock_time_module.time.return_value = 10.0
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req2_rate_limited"})
        self.assertEqual(len(client.request_timestamps[0]), 1) # タイムスタンプは追加されない

        # 60.1秒経過 (最初の呼び出しから1分以上経過)
        mock_time_module.time.return_value = 60.1
        response3 = client.make_request({"data": "req3_after_reset"})
        self.assertEqual(response3["api_used_id"], 1)
        # 古いタイムスタンプ(0.0)はpopされ、新しいタイムスタンプ(60.1)が入るので長さは1
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(client.request_timestamps[0][0], 60.1)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
