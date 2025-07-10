from typing import Optional
from src.data_model import Request
from src.queue_manager import FifoQueue

class Worker:
    """
    タスクキューからリクエストを取得し処理を実行するワーカーを表すクラス。
    各ワーカーは一度に1つのタスクのみを処理します。

    Attributes:
        worker_id (int): ワーカーの一意な識別子。
        task_queue (FifoQueue[Request]): ワーカーがタスクを取得するキュー。
        current_task (Optional[Request]): 現在処理中のタスク。アイドル状態の場合はNone。
        busy_until (float): ワーカーが現在のタスクの処理を完了するシミュレーション時刻。
                           アイドル状態の場合は過去の時刻または0.0。
    """
    def __init__(self, worker_id: int, task_queue: FifoQueue[Request]):
        """
        Workerのコンストラクタ。

        Args:
            worker_id (int): ワーカーのID。
            task_queue (FifoQueue[Request]): タスクを取得するためのキューのインスタンス。
        """
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.current_task: Optional[Request] = None
        self.busy_until: float = 0.0  # この時刻までワーカーは処理中

    def process_task(self, current_time: float) -> Optional[Request]:
        """
        指定された現在のシミュレーション時刻に基づいてワーカーの処理を進めます。

        このメソッドは以下のいずれかを行います:
        1. 現在処理中のタスクがあれば、それが完了したか確認し、完了していればそのタスクを返す。
        2. アイドル状態（現在のタスクがない）で、かつタスクキューにタスクがあれば、
           新しいタスクをデキューして処理を開始する。この場合、何も返さない（None）。
        3. 処理中だがまだ完了していない、またはアイドルでキューも空の場合、何も返さない（None）。

        Args:
            current_time (float): 現在のシミュレーション時刻。

        Returns:
            Optional[Request]: タスクがこの呼び出しで完了した場合、その完了したタスク。
                               それ以外の場合はNone。
        """
        # 1. 現在のタスクが完了しているか確認
        if self.current_task and current_time >= self.busy_until:
            completed_task = self.current_task
            completed_task.finish_processing_time_by_worker = self.busy_until # 実際の完了時刻
            self.current_task = None
            # print(f"[Time: {current_time:.2f}] Worker {self.worker_id} completed task {completed_task.user_id} at {self.busy_until:.2f}")
            return completed_task

        # 2. 新しいタスクを開始できるか確認 (アイドルかつキューにタスクあり)
        if self.current_task is None and not self.task_queue.is_empty():
            task_to_process = self.task_queue.dequeue()
            if task_to_process:
                self.current_task = task_to_process
                self.current_task.start_processing_time_by_worker = current_time
                self.busy_until = current_time + self.current_task.processing_time
                # print(f"[Time: {current_time:.2f}] Worker {self.worker_id} started task {self.current_task.user_id}, busy until {self.busy_until:.2f}")

        return None # 上記以外（処理中だが未完了、またはアイドルでキューも空）

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
