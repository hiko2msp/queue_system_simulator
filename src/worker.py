from src.api_client import APIClient  # APIClientをインポート
from src.data_model import Request  # Requestに status, api_attempts などのフィールド追加を検討
from src.queue_manager import FifoQueue, PriorityQueueStrategy  # PriorityQueueStrategy をインポート


class Worker:
    """
    タスクキューからリクエストを取得し、外部API呼び出しを含む処理を実行するワーカー。
    各ワーカーは一度に1つのタスクのみを処理します。

    Attributes:
        worker_id (int): ワーカーの一意な識別子。
        task_queue (Union[FifoQueue[Request], PriorityQueueStrategy, Any]): ワーカーがタスクを取得するキュー。 # Anyは一時的な措置、より厳密な型も検討可
        api_client (APIClient): 外部APIと通信するためのクライアント。
        current_task (Optional[Request]): 現在処理中のタスク。アイドル状態の場合はNone。
        busy_until (float): ワーカーが現在のタスクの処理を完了するシミュレーション時刻。
                           アイドル状態の場合は過去の時刻または0.0。
        task_processing_status (Optional[str]): 現在のタスクのAPI処理結果 ("success", "failed_api_limit")
    """

    def __init__(self, worker_id: int, task_queue: FifoQueue[Request] | PriorityQueueStrategy[Request], api_client: APIClient):
        """
        Workerのコンストラクタ。

        Args:
            worker_id (int): ワーカーのID。
            task_queue (FifoQueue[Request]): タスクを取得するためのキューのインスタンス。
            api_client (APIClient): APIクライアントのインスタンス。
        """
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.api_client = api_client
        self.current_task: Request | None = None
        self.busy_until: float = 0.0
        self.task_processing_status: str | None = None

    def _perform_api_call(self, task: Request, task_data: dict) -> tuple[str, dict | None]: # 'task' 引数を追加
        """
        APIクライアントを使用して外部API呼び出しを実行する。
        成功なら ("success", response_data),
        APIエラーなら ("failed_api_error", None), ※ APIClientがrequest_obj.api_error_occurredをTrueにする
        全API試行失敗なら ("failed_all_apis", None) を返す。
        """
        try:
            # APIClient.make_request に task オブジェクトを渡す
            response = self.api_client.make_request(task, task_data)
            if response:
                # task.api_error_occurred は APIClient 側で設定される
                return "success", response
            else:
                # make_request が None を返した場合 (全APIが利用不可またはレート制限)
                # task.api_error_occurred は、もしサーバーエラーが原因ならTrueになっているはず
                return "failed_all_apis", None
        except Exception as e:
            # このExceptionは通常、make_request内でキャッチされず、より深刻な問題を示唆するかもしれないが、
            # make_request が None を返すようになったため、ここに来るケースは減るはず。
            # しかし、予期せぬエラーのために残しておく。
            print(f"Worker {self.worker_id}: Unexpected error during API call for task {task.user_id}: {e}")
            task.api_error_occurred = True # 予期せぬエラーもAPIエラーとしてマーク
            return "failed_unexpected_error", None

    def process_task(self, current_time: float) -> Request | None:
        """
        指定された現在のシミュレーション時刻に基づいてワーカーの処理を進めます。
        タスク処理にはAPI呼び出しが含まれます。

        Args:
            current_time (float): 現在のシミュレーション時刻。

        Returns:
            Optional[Request]: タスクがこの呼び出しで完了した場合、その完了したタスク。
                               それ以外の場合はNone。
        """
        # 1. 現在のタスクが完了しているか確認
        if self.current_task and current_time >= self.busy_until:
            completed_task = self.current_task
            completed_task.finish_processing_time_by_worker = self.busy_until

            # Requestモデルに処理ステータスを記録するフィールドを追加した場合
            # setattr(completed_task, 'processing_status', self.task_processing_status)
            # 例: completed_task.status = self.task_processing_status

            print(
                f"[Time: {current_time:.2f}] Worker {self.worker_id} completed task {completed_task.user_id} at {self.busy_until:.2f} with status: {self.task_processing_status}"
            )

            self.current_task = None
            self.task_processing_status = None
            return completed_task

        # 2. 新しいタスクを開始できるか確認 (アイドルかつキューにタスクあり)
        if self.current_task is None and not self.task_queue.is_empty():
            task_to_process = self.task_queue.dequeue()
            if task_to_process:
                self.current_task = task_to_process
                self.current_task.start_processing_time_by_worker = current_time
                self.current_task.api_error_occurred = False # 新しいタスクなのでリセット

                api_call_status, response_data = self._perform_api_call(
                    self.current_task, # current_task を渡す
                    {"user_id": self.current_task.user_id, "data": "sample_payload"}
                )
                self.task_processing_status = api_call_status

                if api_call_status == "success" and response_data:
                    self.current_task.used_api_id = response_data.get("api_used_id")
                # api_error_occurred は _perform_api_call -> api_client.make_request で設定される

                self.busy_until = current_time + self.current_task.processing_time

                print(
                    f"[Time: {current_time:.2f}] Worker {self.worker_id} started task {self.current_task.user_id}, "
                    f"API call status: {api_call_status}, busy until {self.busy_until:.2f}"
                )

        return None

    def is_busy(self, current_time: float) -> bool:
        """
        指定された現在のシミュレーション時刻において、ワーカーが処理中かどうかを返します。

        Args:
            current_time (float): 現在のシミュレーション時刻。

        Returns:
            bool: ワーカーが処理中の場合はTrue、そうでない場合はFalse。
        """
        # current_taskが存在し、かつ busy_until が現在時刻より未来であること
        return self.current_task is not None and current_time < self.busy_until
