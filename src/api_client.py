import logging
import random # for error simulation
from collections import deque
from collections.abc import Callable  # Callable をインポート
from typing import TYPE_CHECKING

from config.settings import EXTERNAL_API_RPM_LIMIT, NUM_EXTERNAL_APIS

if TYPE_CHECKING:
    from src.data_model import Request


class APIClient:
    def __init__(self, simulator_time_func: Callable[[], float]):  # simulator_time_func を引数に追加し、型ヒントも設定
        self.num_apis = NUM_EXTERNAL_APIS
        self.rpm_limit = EXTERNAL_API_RPM_LIMIT
        self.api_endpoints = [f"https://api.example.com/v1/endpoint{i+1}" for i in range(self.num_apis)]
        self.request_timestamps: list[deque] = [deque() for _ in range(self.num_apis)]
        self.current_api_index = 0
        self.simulator_time_func = simulator_time_func  # 時間取得関数を保存

    def _can_make_request(self, api_index: int) -> bool:
        """指定されたAPIがRPM制限内か確認する"""
        now = self.simulator_time_func()  # time.time() の代わりに simulator_time_func を使用
        # 1分以上前のタイムスタンプを削除
        while self.request_timestamps[api_index] and now - self.request_timestamps[api_index][0] > 60:
            self.request_timestamps[api_index].popleft()

        return len(self.request_timestamps[api_index]) < self.rpm_limit

    def make_request(self, request_obj: 'Request', data: dict) -> dict | None: # request_obj を追加、戻り値型変更
        """
        外部APIにリクエストを送信する。
        レート制限に達した場合は次のAPIにフォールバックする。
        APIエラーが発生した場合は request_obj.api_error_occurred を True に設定する。
        成功時はレスポンス辞書を、全API試行失敗時はNoneを返す。
        """
        initial_api_index = self.current_api_index
        attempts = 0
        last_error_was_server_fault = False

        while attempts < self.num_apis:
            api_index_to_try = (initial_api_index + attempts) % self.num_apis
            last_error_was_server_fault = False # Reset for current attempt

            if self._can_make_request(api_index_to_try):
                logging.debug(f"Making request to API {api_index_to_try + 1} for request {request_obj.user_id} with data: {data}")
                self.request_timestamps[api_index_to_try].append(
                    self.simulator_time_func()
                )

                # Simulate API call and potential errors
                # 5% chance of a 500 error, otherwise 200 OK or 429 for rate limit
                if random.random() < 0.05: # 5% chance of 500 error
                    response_status = 500
                else:
                    # For simplicity, assume _can_make_request is the primary gate for 429.
                    # Real APIs might also return 429 if they are overloaded.
                    response_status = 200

                if response_status == 429: # Rate limit by API itself
                    logging.debug(f"API {api_index_to_try + 1} returned 429 (Rate Limit Exceeded) for request {request_obj.user_id}. Trying next API.")
                    # This is a rate limit, not a server error, so api_error_occurred is not set.
                elif response_status == 200:
                    logging.debug(f"Request to API {api_index_to_try + 1} successful for request {request_obj.user_id}.")
                    self.current_api_index = api_index_to_try
                    request_obj.used_api_id = api_index_to_try + 1
                    request_obj.api_error_occurred = False # Explicitly set to False on success
                    return {
                        "status": "success",
                        "api_used_id": api_index_to_try + 1,
                        "data": f"response from {self.api_endpoints[api_index_to_try]}",
                    }
                else: # Other errors (e.g., 500 internal server error)
                    logging.warning(
                        f"API {api_index_to_try + 1} returned error {response_status} for request {request_obj.user_id}. Trying next API."
                    )
                    request_obj.api_error_occurred = True # Mark as API server error
                    last_error_was_server_fault = True
                    # Continue to try next API
            else: # Client-side rate limited (our check prevented the call)
                logging.debug(
                    f"API {api_index_to_try + 1} is rate limited by client for request {request_obj.user_id}. Trying next API."
                )

            attempts += 1
            # self.current_api_index = (initial_api_index + attempts) % self.num_apis # Update only on success or actual attempt.
            # More robust: update current_api_index only when an API is chosen and successfully used,
            # or when moving to the next due to *our* rate limit.
            # For now, simple round-robin on failure/client-rate-limit.
            if attempts < self.num_apis: # Avoid index out of bounds if all fail
                 self.current_api_index = (initial_api_index + attempts) % self.num_apis


        # すべてのAPIが試されたが成功しなかった
        logging.error(
            f"All external APIs are unavailable, rate limited, or failed for request {request_obj.user_id}. Last error was server fault: {last_error_was_server_fault}"
        )
        # If the loop finished, it means no API call was successful.
        # request_obj.api_error_occurred would be True if the *last* attempt that was not a client-side rate limit
        # resulted in a server error. Or if any previous attempt resulted in a server error.
        # The flag is sticky once set to True for the request.
        # If all attempts were client-side rate limits, or server-side 429s, api_error_occurred remains False.
        return None # Indicate failure to get a successful response


if __name__ == "__main__":
    import datetime # datetime をインポート
    from src.data_model import Request # Request をインポート

    # テスト用
    current_sim_time = 0.0
    def get_dummy_time():
        global current_sim_time
        current_sim_time += 0.1
        return current_sim_time

    logging.basicConfig(level=logging.DEBUG) # Enable logging for test
    client = APIClient(simulator_time_func=get_dummy_time)

    for i in range(NUM_EXTERNAL_APIS * EXTERNAL_API_RPM_LIMIT + 5):
        dummy_request = Request(
            user_id=f"test_user_{i}",
            request_time=datetime.datetime.now(datetime.timezone.utc), # aware datetime
            processing_time=10,
            sim_arrival_time=current_sim_time
        )
        try:
            logging.debug(f"Attempt {i+1}: Current Sim Time: {current_sim_time:.2f}, Request: {dummy_request.user_id}")
            response = client.make_request(dummy_request, {"payload": f"data_{i}"})
            if response:
                logging.debug(f"Response: {response}, API error: {dummy_request.api_error_occurred}")
            else:
                logging.debug(f"No successful response. API error: {dummy_request.api_error_occurred}")

        except Exception as e: # Should not happen if make_request returns None on failure
            logging.error(f"Exception during make_request: {e}") # Log unexpected exceptions
            # break # Depending on test case, might want to break or continue

        if current_sim_time > 70 : # Limit test duration
            logging.debug("Exiting test loop due to time limit.")
            break

    # Fallback test logic might need more specific mock conditions if detailed behavior of 429 vs 500 is tested.
    # The current random error simulation in make_request provides some variability.
