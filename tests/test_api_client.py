import unittest
from unittest.mock import patch, MagicMock, call
import time

# config.settings の値をテスト用に上書きできるようにする
# 通常、テスト実行前に環境変数やテスト用の設定ファイルで制御するが、
# ここでは簡略化のため、モジュール読み込み時にパッチを当てるアプローチも考えられる。
# ただし、よりクリーンなのは、APIClientが設定値をコンストラクタで受け取れるようにするか、
# テスト専用の設定をロードする仕組み。今回はconfig.settingsを直接利用する前提で進める。

from src.api_client import APIClient
from config import settings as test_settings # テスト中に値を変更するため

class TestAPIClient(unittest.TestCase):

    def setUp(self):
        # 各テストの前にsettingsの値をデフォルトに戻すか、テストケースごとに設定する
        self.original_num_apis = test_settings.NUM_EXTERNAL_APIS
        self.original_rpm_limit = test_settings.EXTERNAL_API_RPM_LIMIT

    def tearDown(self):
        # テスト後にsettingsの値を元に戻す
        test_settings.NUM_EXTERNAL_APIS = self.original_num_apis
        test_settings.EXTERNAL_API_RPM_LIMIT = self.original_rpm_limit
        # APIClient内のグローバルな設定変更を伴う場合、モジュールの再読み込みなどが必要になることがあるが、
        # APIClientがインスタンスごとに設定を読み込むなら不要。現状はインスタンス化時に読み込む。

    def test_initialization_with_settings(self):
        test_settings.NUM_EXTERNAL_APIS = 3
        test_settings.EXTERNAL_API_RPM_LIMIT = 10
        client = APIClient()
        self.assertEqual(client.num_apis, 3)
        self.assertEqual(client.rpm_limit, 10)
        self.assertEqual(len(client.api_endpoints), 3)

    @patch('time.time')
    def test_rate_limit_single_api(self, mock_time):
        test_settings.NUM_EXTERNAL_APIS = 1
        test_settings.EXTERNAL_API_RPM_LIMIT = 2
        client = APIClient()

        # time.time() が単調増加する値を返すように設定
        mock_time.side_effect = [t for t in range(100)]

        # 1回目のリクエスト (成功)
        response1 = client.make_request({"data": "req1"})
        self.assertEqual(response1["api_used"], 1)

        # 2回目のリクエスト (成功)
        response2 = client.make_request({"data": "req2"})
        self.assertEqual(response2["api_used"], 1)

        # 3回目のリクエスト (レート制限、APIClientはExceptionを出すか、特定のエラーレスポンスを返す)
        # 現在の実装では、make_requestは全APIがダメになるまでフォールバックしようとする。
        # NUM_EXTERNAL_APIS = 1 なので、即座に Exception が期待される。
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req3"})

    @patch('time.time')
    def test_fallback_mechanism(self, mock_time):
        test_settings.NUM_EXTERNAL_APIS = 2
        test_settings.EXTERNAL_API_RPM_LIMIT = 1 # 各APIは1リクエスト/分まで
        client = APIClient()

        # API呼び出しをモック化して、特定のAPIが429を返すようにする
        # ただし、現在のAPIClient.make_requestは内部でAPIコールをシミュレートしており、
        # 外部ライブラリ(requestsなど)を使っていないため、直接レスポンスをモックするのが難しい。
        # 代わりに、_can_make_request の振る舞いか、make_request内のレスポンス処理を調整する。
        # ここでは、_can_make_request がレート制限を正しく判定することに依存してテストする。

        mock_time.side_effect = [t * 0.1 for t in range(100)] # 時間経過を細かく

        # 1回目: API 1 を使用
        print("Fallback test: Request 1")
        response1 = client.make_request({"data": "req1_api1"})
        self.assertEqual(response1["api_used"], 1)
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 0)


        # 2回目: API 1 はレート制限、API 2 を使用
        print("Fallback test: Request 2")
        response2 = client.make_request({"data": "req2_api2"})
        self.assertEqual(response2["api_used"], 2)
        self.assertEqual(len(client.request_timestamps[0]), 1) # API1のカウントは変わらず
        self.assertEqual(len(client.request_timestamps[1]), 1) # API2がカウントアップ

        # 3回目: API 1, API 2 ともにレート制限 -> 例外
        print("Fallback test: Request 3")
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req3_fail"})

        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 1)


    @patch('time.time')
    def test_all_apis_rate_limited_then_exception(self, mock_time):
        test_settings.NUM_EXTERNAL_APIS = 2
        test_settings.EXTERNAL_API_RPM_LIMIT = 1
        client = APIClient()

        mock_time.side_effect = [t * 0.1 for t in range(100)]

        # API 1 を使用 (成功)
        client.make_request({"data": "req1"})
        # API 2 を使用 (成功) - 内部でフォールバックはしないが、次のリクエストはAPI2から試行される可能性がある
        # client.current_api_index が更新されるため。
        # より厳密には、make_requestの最初の試行がAPI1で、次にAPI2、という流れをテストしたい。
        # そのためには、make_request内部のAPI選択ロジックを考慮するか、
        # もしくはAPIClientのcurrent_api_indexをリセットするメソッドがテスト用にあると便利。
        # 現在のmake_requestは、前回成功したAPIから試し始めるわけではない。
        # 常に (initial_api_index + attempts) % self.num_apis で試す。
        # initial_api_index は self.current_api_index であり、これは前回のリクエストで更新される。

        client.make_request({"data": "req2"}) # API 1 が使われるはず (前回API1が成功なら) -> レート超過 -> API 2へ
                                            # もし前回の成功がAPI2なら、API2から試行 -> レート超過 -> API1へ

        # 2回のリクエストで両方のAPIが1回ずつ使われたはず
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 1)

        # 3回目のリクエスト (両APIともレート制限により例外)
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req3"})

    @patch('time.time')
    def test_rate_limit_reset_after_one_minute(self, mock_time):
        test_settings.NUM_EXTERNAL_APIS = 1
        test_settings.EXTERNAL_API_RPM_LIMIT = 1
        client = APIClient()

        # 最初の時間
        current_simulated_time = 0
        mock_time.return_value = current_simulated_time

        # 1回目のリクエスト (成功)
        response1 = client.make_request({"data": "req1"})
        self.assertEqual(response1["api_used"], 1)
        self.assertEqual(len(client.request_timestamps[0]), 1)

        # 2回目のリクエスト (レート制限)
        current_simulated_time += 10 # 10秒経過
        mock_time.return_value = current_simulated_time
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req2"})

        # 61秒経過 (最初の呼び出しから)
        current_simulated_time = 0 + 61
        mock_time.return_value = current_simulated_time

        # 3回目のリクエスト (レート制限解除され成功)
        response3 = client.make_request({"data": "req3"})
        self.assertEqual(response3["api_used"], 1)
        self.assertEqual(len(client.request_timestamps[0]), 1) # 古いのは消え、新しいのが入る


    # make_request が実際に429を返すAPIをシミュレートするテスト
    # これには、APIClient.make_request内のAPIコール部分をモック可能にする必要がある
    # (例: `requests.post` を使っていればそれをモックする)
    # 現状のAPIClientはAPIコールを内部でシミュレートしているため、この種のテストは書きにくい。
    # `_can_make_request` に依存したテストが主となる。
    #
    # もし make_request がHTTPクライアントライブラリを使うようになったら、以下のようなテストが可能:
    # @patch('src.api_client.requests.post') # 仮にrequests.postを使っているとする
    # @patch('time.time')
    # def test_fallback_on_actual_429_response(self, mock_time, mock_post):
    #     test_settings.NUM_EXTERNAL_APIS = 2
    #     test_settings.EXTERNAL_API_RPM_LIMIT = 5 # レートは十分
    #     client = APIClient()

    #     mock_time.side_effect = [t * 0.1 for t in range(100)]

    #     # API1は429を返し、API2は200を返すように設定
    #     mock_response_429 = MagicMock()
    #     mock_response_429.status_code = 429
    #     mock_response_200 = MagicMock()
    #     mock_response_200.status_code = 200
    #     mock_response_200.json.return_value = {"message": "success from API2"}

    #     # 最初の呼び出しはAPI1 (api.example.com/v1/endpoint1) に行くはず
    #     # 次の呼び出しはAPI2 (api.example.com/v1/endpoint2) に行くはず
    #     mock_post.side_effect = [mock_response_429, mock_response_200]

    #     response = client.make_request({"data": "req_fallback_429"})

    #     self.assertEqual(response["status"], "success")
    #     self.assertEqual(response["api_used"], 2) # API2が使われた
    #     mock_post.assert_any_call(client.api_endpoints[0], json={"data": "req_fallback_429"})
    #     mock_post.assert_any_call(client.api_endpoints[1], json={"data": "req_fallback_429"})
    #     self.assertEqual(mock_post.call_count, 2)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
    # vscodeのテストエクスプローラーでうまく動かすため exit=False と argv を指定
    # 通常のコマンドライン実行では unittest.main() でOK

# 注意:
# 1. `APIClient` が `config.settings` をモジュールレベルで読み込んでいる場合、
#    テスト中に `test_settings.NUM_EXTERNAL_APIS = X` のように変更しても、
#    既に読み込まれた `APIClient` 内の定数には影響しない可能性があります。
#    `APIClient` のインスタンス化のたびに `settings` から値を読み直す実装であれば問題ありません。
#    現在の `APIClient` は `__init__` で `NUM_EXTERNAL_APIS` と `EXTERNAL_API_RPM_LIMIT` を
#    `self.num_apis`, `self.rpm_limit` に代入しているので、インスタンスごとに設定が反映されます。
#
# 2. `time.time` のモックは、`APIClient` が内部で `time.time()` を呼び出す方法に依存します。
#    `from time import time` ではなく `import time` であれば `@patch('src.api_client.time.time')` のように
#    `APIClient` モジュール内の `time` オブジェクトの `time` メソッドをパッチする必要があります。
#    現在の `APIClient` は `import time` なので `@patch('src.api_client.time.time')` (または単に `@patch('time.time')` がグローバルに効く場合も)
#    `@patch('time.time')` でテストファイル内で `time.time` をパッチすれば、`APIClient` が `time.time()` を呼び出す際に
#    モックされたものが使われるはずです。
#    `APIClient` が `from time import time` としている場合は、`@patch('src.api_client.time')` (time関数自体を置き換え)
#    または `@patch.object(src.api_client.time_module, 'time')` のような形になる。
#    `APIClient` は `import time` としているので、`@patch('time.time')` で動作するはず。
#    `test_fallback_mechanism` の print 文で動作確認。
#    `src.api_client.py` が `import time` で `time.time()` を呼んでいるので、
#    テスト側で `@patch('time.time', new_callable=MagicMock)` などとすれば、
#    Pythonの `time` モジュール全体の `time` 関数がモックされる。
#    `src.api_client.time` をパッチするのがより正確。-> `@patch('src.api_client.time')` を試す。
#    より具体的には `@patch('src.api_client.time.time')` だが、`time` モジュール自体を置き換えるのでも良い場合がある。
#    `@patch('time.time')` はグローバルな `time.time` を指す。`APIClient` が `import time` していれば、このグローバルなものを参照する。
#    今回のコードでは `@patch('time.time')` で動作するはず。
#
# 3. `make_request`内のAPI呼び出しシミュレーション部分が現状ハードコード(常に200 OKを返す)ため、
#    429エラーによるフォールバックを直接テストするのが難しい。
#    `_can_make_request` が False になることによるフォールバックはテスト可能。
#    実際の429レスポンスをテストするには、`APIClient` が `requests`のようなHTTPクライアントを使うようにし、
#    そのクライアントのメソッドをモックする必要がある。コメントアウトされたテストケースはその例。

```python
import unittest
from unittest.mock import patch, MagicMock, call
import time

# config.settings の値をテスト用に上書きできるようにする
from config import settings as test_settings
from src.api_client import APIClient
import importlib # モジュールの再読み込み用

class TestAPIClient(unittest.TestCase):

    def setUp(self):
        # 各テストの前にsettingsの値を保存し、テスト用の値に設定
        self.original_num_apis = test_settings.NUM_EXTERNAL_APIS
        self.original_rpm_limit = test_settings.EXTERNAL_API_RPM_LIMIT

        # APIClientがsettingsを読み込むのはインスタンス化時なので、
        # APIClientをインスタンス化する前にsettingsの値を変更する。
        # また、他のテストの影響を避けるため、src.api_clientを再読み込みすることも検討。
        # ただし、通常はテストごとに独立した環境が望ましい。

    def tearDown(self):
        # テスト後にsettingsの値を元に戻す
        test_settings.NUM_EXTERNAL_APIS = self.original_num_apis
        test_settings.EXTERNAL_API_RPM_LIMIT = self.original_rpm_limit
        # APIClientモジュールがグローバルなsettingsを参照している場合、
        # importlib.reload(src.api_client) のような対応が必要になることも。
        # 今回のAPIClientはインスタンス化時にsettingsを読むので、基本的には不要。

    def _reload_api_client_module(self):
        # settings変更後にAPIClientの定義を再評価させるため
        # (APIClientがモジュールレベルでsettings値をキャッシュしている場合に必要)
        # 今回のAPIClientは__init__で読み込むので、これは厳密には不要かもしれないが、念のため。
        import src.api_client
        importlib.reload(src.api_client)
        # グローバルなAPIClientクラスの参照を更新
        globals()['APIClient'] = src.api_client.APIClient


    @patch('src.api_client.time') # APIClient内のtimeモジュールをモック
    def test_initialization_and_settings_loading(self, mock_time_module):
        test_settings.NUM_EXTERNAL_APIS = 3
        test_settings.EXTERNAL_API_RPM_LIMIT = 10
        # self._reload_api_client_module() # settings変更を反映させるため
        client = APIClient() # この時点でsettingsが読まれる

        self.assertEqual(client.num_apis, 3)
        self.assertEqual(client.rpm_limit, 10)
        self.assertEqual(len(client.api_endpoints), 3)
        self.assertEqual(client.api_endpoints[0], "https://api.example.com/v1/endpoint1")

    @patch('src.api_client.time')
    def test_rate_limit_single_api(self, mock_time_module):
        test_settings.NUM_EXTERNAL_APIS = 1
        test_settings.EXTERNAL_API_RPM_LIMIT = 2
        # self._reload_api_client_module()
        client = APIClient()

        mock_time_module.time.side_effect = [0.0, 0.1, 0.2, 0.3, 0.4] # time.time()が返す値

        # Request 1 (allowed)
        client.make_request({"data": "req1"})
        self.assertEqual(len(client.request_timestamps[0]), 1)

        # Request 2 (allowed)
        client.make_request({"data": "req2"})
        self.assertEqual(len(client.request_timestamps[0]), 2)

        # Request 3 (rate limited)
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req3"})
        self.assertEqual(len(client.request_timestamps[0]), 2) # No new timestamp added

    @patch('src.api_client.time')
    def test_fallback_when_rate_limited(self, mock_time_module):
        test_settings.NUM_EXTERNAL_APIS = 2
        test_settings.EXTERNAL_API_RPM_LIMIT = 1
        # self._reload_api_client_module()
        client = APIClient()

        mock_time_module.time.side_effect = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

        # Request 1: Uses API 1
        response1 = client.make_request({"data": "req1"})
        self.assertEqual(response1["api_used"], 1)
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 0)
        # client.current_api_index should be 0 after this if API 1 was chosen and successful

        # Request 2: API 1 is rate-limited, falls back to API 2
        # The client.current_api_index might influence starting point.
        # Let's assume it tries API 1 (index 0) first due to current_api_index or default logic
        response2 = client.make_request({"data": "req2"})
        self.assertEqual(response2["api_used"], 2)
        self.assertEqual(len(client.request_timestamps[0]), 1) # API 1 still has its one request
        self.assertEqual(len(client.request_timestamps[1]), 1) # API 2 now has one request
        # client.current_api_index should be 1

        # Request 3: API 1 and API 2 are rate-limited
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req3"})
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(len(client.request_timestamps[1]), 1)

    @patch('src.api_client.time')
    def test_all_apis_unavailable_exception(self, mock_time_module):
        test_settings.NUM_EXTERNAL_APIS = 2
        test_settings.EXTERNAL_API_RPM_LIMIT = 0 # No requests allowed
        # self._reload_api_client_module()
        client = APIClient()
        mock_time_module.time.return_value = 0.0

        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req1"})

    @patch('src.api_client.time')
    def test_rate_limit_reset_after_one_minute(self, mock_time_module):
        test_settings.NUM_EXTERNAL_APIS = 1
        test_settings.EXTERNAL_API_RPM_LIMIT = 1
        # self._reload_api_client_module()
        client = APIClient()

        # Initial time
        mock_time_module.time.return_value = 0.0

        # Request 1 (uses API 1)
        client.make_request({"data": "req1"})
        self.assertEqual(len(client.request_timestamps[0]), 1)
        self.assertEqual(client.request_timestamps[0][0], 0.0)

        # Advance time by 30 seconds (still within rate limit window)
        mock_time_module.time.return_value = 30.0
        with self.assertRaisesRegex(Exception, "All external APIs are unavailable or rate limited."):
            client.make_request({"data": "req2"})
        self.assertEqual(len(client.request_timestamps[0]), 1) # Still 1, as the previous one is recent

        # Advance time past 60 seconds from the first request
        mock_time_module.time.return_value = 60.1 # Timestamp 0.0 is now older than 60s

        # Request 3 (should be allowed as rate limit for timestamp 0.0 has expired)
        response3 = client.make_request({"data": "req3"})
        self.assertEqual(response3["api_used"], 1)
        self.assertEqual(len(client.request_timestamps[0]), 1) # Old one popped, new one added
        self.assertEqual(client.request_timestamps[0][0], 60.1)

    # Test for 429 response handling
    # This requires mocking the part of make_request that simulates the actual API call.
    # Currently, make_request always assumes a 200 OK unless _can_make_request is false.
    # To test actual 429s, we'd need to:
    # 1. Modify APIClient to use something like `requests.post`
    # 2. Mock that `requests.post` call in the test.
    #
    # For now, we assume that if `_can_make_request` is true, the call "succeeds" (status 200),
    # and if it's false, it's like a pre-emptive rate limit block.
    # The current `make_request` has a placeholder for `response_status` which could be
    # manipulated for more direct testing if it were, for example, returned by a helper method.

    # Example of how to test 429 if APIClient was refactored for easier mocking of response:
    # @patch.object(APIClient, '_execute_actual_request') # Assume this method exists and returns a status
    # @patch('src.api_client.time')
    # def test_fallback_on_simulated_429_response(self, mock_time_module, mock_execute_request):
    #     test_settings.NUM_EXTERNAL_APIS = 2
    #     test_settings.EXTERNAL_API_RPM_LIMIT = 5 # RPM limit is high
    #     # self._reload_api_client_module()
    #     client = APIClient()
    #     mock_time_module.time.return_value = 0.0

    #     # API 1 returns 429, API 2 returns 200
    #     mock_execute_request.side_effect = [
    #         (429, {}), # Call to API 1
    #         (200, {"data": "success from API2"})  # Call to API 2
    #     ]

    #     response = client.make_request({"payload": "test"})
    #     self.assertEqual(response["status"], "success")
    #     self.assertEqual(response["api_used"], 2)
    #     self.assertEqual(mock_execute_request.call_count, 2)
    #     # Check calls were made to correct (simulated) endpoints
    #     # args_list = mock_execute_request.call_args_list
    #     # self.assertIn(client.api_endpoints[0], args_list[0][0][0]) # Assuming endpoint URL is first arg
    #     # self.assertIn(client.api_endpoints[1], args_list[1][0][0])


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

```

**上記テストコードのポイントと修正点:**
- **`config.settings` のモック**: テスト中に `test_settings.NUM_EXTERNAL_APIS` や `test_settings.EXTERNAL_API_RPM_LIMIT` の値を変更しています。`APIClient` はインスタンス化時にこれらの値を読み込むため、`APIClient()` を呼び出す前にこれらの値を設定する必要があります。
    - `setUp` と `tearDown` で元の値を保存・復元します。
    - `importlib.reload(src.api_client)` を使ってモジュールを再読み込みするアプローチも考えられましたが、`APIClient` がインスタンスごとに設定を読み込むため、通常は不要です。今回は`APIClient`のコードを変更せず、テスト側で対応します。
- **`time.time` のモック**: `@patch('src.api_client.time')` を使用して、`APIClient` モジュールが参照する `time` モジュール自体をモックオブジェクトに置き換えます。そして、そのモックオブジェクトの `time` メソッド (`mock_time_module.time`) に `side_effect` や `return_value` を設定して、`time.time()` の呼び出し結果を制御します。
- **レート制限のテスト (`test_rate_limit_single_api`)**: RPM制限を超えた場合に、新しいリクエストがタイムスタンプキューに追加されず、例外が発生することを確認します。
- **フォールバックのテスト (`test_fallback_when_rate_limited`)**: 最初のAPIがレート制限に達したときに、次のAPIが使用されることを確認します。`client.request_timestamps` の各APIに対応するキューの長さで確認します。
- **全APIが利用不可の場合のテスト (`test_all_apis_unavailable_exception`)**: RPMを0に設定し、最初のリクエストから例外が発生することを確認します。
- **レート制限のリセットテスト (`test_rate_limit_reset_after_one_minute`)**: 60秒以上経過すると、古いタイムスタンプがキューから削除され、新しいリクエストが許可されることを確認します。
- **429レスポンスの直接テストについて**: `APIClient` の現在の `make_request` メソッドは、実際のHTTPリクエストをシミュレートしておらず、`_can_make_request` が True であれば常に成功（ステータス200扱い）としています。そのため、APIが実際に429エラーを返した場合のフォールバックをこのテストスイートで直接テストするのは困難です。これを行うには、`APIClient` をリファクタリングして、実際のHTTPリクエスト部分（例: `requests.post` の呼び出し）をモック可能な形で分離する必要があります。コメントアウトされたテストケース `test_fallback_on_simulated_429_response` は、そのようなリファクタリングが行われた場合のテストのアイデアを示しています。

このテストファイル `tests/test_api_client.py` を作成しました。
次に `tests/test_worker.py` のテストを追加します。
