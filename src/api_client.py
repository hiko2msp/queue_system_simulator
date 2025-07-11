import time # time モジュールは simulator_time_func が提供されない場合のフォールバックや型ヒントのために残すことも検討できますが、今回は直接は使用しません。
from collections import deque
from typing import Callable # Callable をインポート
from config.settings import NUM_EXTERNAL_APIS, EXTERNAL_API_RPM_LIMIT

class APIClient:
    def __init__(self, simulator_time_func: Callable[[], float]): # simulator_time_func を引数に追加し、型ヒントも設定
        self.num_apis = NUM_EXTERNAL_APIS
        self.rpm_limit = EXTERNAL_API_RPM_LIMIT
        self.api_endpoints = [f"https://api.example.com/v1/endpoint{i+1}" for i in range(self.num_apis)]
        self.request_timestamps = [deque() for _ in range(self.num_apis)]
        self.current_api_index = 0
        self.simulator_time_func = simulator_time_func # 時間取得関数を保存

    def _can_make_request(self, api_index):
        """指定されたAPIがRPM制限内か確認する"""
        now = self.simulator_time_func() # time.time() の代わりに simulator_time_func を使用
        # 1分以上前のタイムスタンプを削除
        while (self.request_timestamps[api_index] and
               now - self.request_timestamps[api_index][0] > 60):
            self.request_timestamps[api_index].popleft()

        return len(self.request_timestamps[api_index]) < self.rpm_limit

    def make_request(self, data):
        """
        外部APIにリクエストを送信する。
        レート制限に達した場合は次のAPIにフォールバックする。
        """
        initial_api_index = self.current_api_index
        attempts = 0
        while attempts < self.num_apis:
            api_index_to_try = (initial_api_index + attempts) % self.num_apis

            if self._can_make_request(api_index_to_try):
                # 実際のAPIコールをシミュレート
                print(f"Making request to API {api_index_to_try + 1} with data: {data}")
                self.request_timestamps[api_index_to_try].append(self.simulator_time_func()) # time.time() の代わりに simulator_time_func を使用

                # ここで実際のAPI呼び出しを行う (例: requests.post)
                # response = requests.post(self.api_endpoints[api_index_to_try], json=data)

                # ダミーレスポンス
                # 429エラーをシミュレートするために、特定の条件下でダミーの429を発生させることも可能
                # if some_condition_for_429:
                #     print(f"Simulating 429 error from API {api_index_to_try + 1}")
                #     # フォールバックをテストするために、意図的に429を発生させる
                #     if attempts < self.num_apis -1: #最後のAPIでなければ429を返す
                #          response_status = 429
                #     else: #最後のAPIなら成功させるか、別のエラーを返す
                #          response_status = 200
                # else:
                #     response_status = 200

                response_status = 200 # 仮に常に成功するとする

                if response_status == 429:
                    print(f"API {api_index_to_try + 1} returned 429 (Rate Limit Exceeded). Trying next API.")
                    attempts += 1
                    self.current_api_index = (api_index_to_try + 1) % self.num_apis # 次の試行のためにインデックスを更新
                    continue
                elif response_status == 200:
                    # リクエスト成功
                    print(f"Request to API {api_index_to_try + 1} successful.")
                    self.current_api_index = api_index_to_try # 成功したAPIを記憶
                    return {
                        "status": "success",
                        "api_used_id": api_index_to_try + 1, # 1から始まるAPI ID
                        "data": f"response from {self.api_endpoints[api_index_to_try]}"
                    }
                else:
                    # その他のエラー
                    print(f"API {api_index_to_try + 1} returned error {response_status}. Trying next API.")
                    attempts += 1
                    self.current_api_index = (api_index_to_try + 1) % self.num_apis
                    continue
            else:
                # 現在のAPIがレート制限に達している
                print(f"API {api_index_to_try + 1} is rate limited. Trying next API.")
                attempts += 1
                self.current_api_index = (api_index_to_try + 1) % self.num_apis # 次の試行のためにインデックスを更新
                continue

        # すべてのAPIが試されたが成功しなかった
        raise Exception("All external APIs are unavailable or rate limited.")

if __name__ == '__main__':
    # テスト用
    # APIClient のコンストラクタが変更されたため、テストコードも修正が必要
    # ダミーの時間関数を定義
    current_sim_time = 0
    def get_dummy_time():
        global current_sim_time
        # time.sleep(0.1) の代わりにシミュレーション時間を進める
        current_sim_time += 0.1 # 例: 0.1秒ずつ進む
        return current_sim_time

    client = APIClient(simulator_time_func=get_dummy_time) # 変更: simulator_time_func を渡す
    for i in range(NUM_EXTERNAL_APIS * EXTERNAL_API_RPM_LIMIT + 5):
        try:
            print(f"Attempt {i+1}: Current Sim Time: {current_sim_time:.2f}") # シミュレーション時刻も表示
            response = client.make_request({"payload": f"data_{i}"})
            print(response)
        except Exception as e:
            print(e)
            break
        # time.sleep(0.1) # 実際の時間は待たない（get_dummy_timeで進むため）

    print("\n--- Testing Fallback ---")
    # RPM制限を意図的に超えさせてフォールバックをテストする
    # (実際のAPIコール部分をコメントアウトしているため、現在のコードでは
    #  _can_make_request が常にTrueを返し、フォールバックのテストが難しい。
    #  429をシミュレートするロジックを追加するか、実際のAPIコールを模倣する必要がある)

    # 以下は、APIClientのインスタンスを再作成し、
    # make_request内で意図的に429を発生させる場合のテストシナリオの例

    class MockResponse:
        def __init__(self, status_code):
            self.status_code = status_code

    # requestsライブラリの代わりにモックを使用するようにmake_requestを調整する必要がある
    # もしくは、make_request内でAPIからのレスポンスステータスを直接操作できるようにする

    # 簡単なシミュレーション:
    # 1番目のAPIが数回後に429を返し始めると仮定
    # 2番目のAPIがその次に使われる...という流れ

    # client_for_fallback_test = APIClient()
    # for i in range(10): # 10回リクエスト試行
    #     try:
    #         print(f"Fallback Test Attempt {i+1}:")
    #         # make_request の中で、特定のAPIが429を返すように細工する
    #         # 例えば、api_index_to_try == 0 かつ i > 2 の場合に response_status = 429 とする等
    #         response = client_for_fallback_test.make_request({"payload": f"fallback_data_{i}"})
    #         print(response)
    #     except Exception as e:
    #         print(e)
    #     time.sleep(0.5) # リクエスト間隔を少し開ける
