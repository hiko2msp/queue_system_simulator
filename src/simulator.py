import os
import time

from src.api_client import APIClient  # APIClient をインポート
from src.data_model import Request
from src.queue_manager import PriorityQueueStrategy  # PriorityQueueStrategy をインポート
from src.worker import Worker

# NUM_EXTERNAL_APIS と EXTERNAL_API_RPM_LIMIT は APIClient が config から読むので Simulator で直接読む必要はない


class Simulator:
    """
    システムアクセスのシミュレーションを実行するメインクラス。

    リクエストの到着、キューイング、ワーカーによる処理の全体的な流れを管理し、
    イベントドリブンな方法で時間を進めます。
    """

    def __init__(
        self,
        requests: list[Request],
        num_workers: int,
        queue_max_size: int | None = None,
        animation_mode: bool = False,
        animation_update_interval_seconds: float = 1.0,
    ):
        """
        Simulatorのコンストラクタ。

        Args:
            requests (list[Request]): シミュレーション対象のリクエストのリスト。
                                      このリストは内部で到着時刻順にソートされます。
            num_workers (int): シミュレーションで使用するワーカーの数。
            queue_max_size (Optional[int]): タスクキューの最大サイズ。
                                           Noneの場合は無制限。
            animation_mode (bool): アニメーションモードを有効にするかどうか。
            animation_update_interval_seconds (float): アニメーションモード時のシミュレーション時間更新間隔（秒）。
        """
        # 入力リクエストは変更しないようにコピーしてソート
        self.pending_requests: list[Request] = sorted(requests, key=lambda r: r.sim_arrival_time)
        self.animation_mode = animation_mode
        self.animation_update_interval_seconds = animation_update_interval_seconds
        # アニメーション速度: シミュレーション内の24時間 (86400秒) が現実の60秒で表示される
        self.animation_sleep_duration = self.animation_update_interval_seconds / (86400 / 60) if animation_mode else 0

        # TODO: 将来的には複数のキューや異なるキュータイプ (例: 優先度キュー) も考慮。
        # その場合、task_queue の管理方法や Worker へのキューの渡し方を変更する必要がある。
        # self.task_queue: FifoQueue[Request] = FifoQueue(max_size=queue_max_size) # 旧 FifoQueue
        self.task_queue: PriorityQueueStrategy[Request] = PriorityQueueStrategy()
        # 注意: 現在のPriorityQueueStrategyはmax_sizeをコンストラクタで受け付けないため、
        # queue_max_size引数はPriorityQueueStrategy利用時は無視されます。
        # 必要であればPriorityQueueStrategyを改修し、内部キューのサイズ制限を設定できるようにする必要があります。

        # APIClientのインスタンスを作成 (全ワーカーで共有)
        # simulator_time_func として self.get_current_time を渡す
        self.api_client = APIClient(simulator_time_func=self.get_current_time)

        self.workers: list[Worker] = [
            Worker(worker_id=i, task_queue=self.task_queue, api_client=self.api_client) for i in range(num_workers)
        ]
        self.current_time: float = 0.0
        self.completed_requests: list[Request] = []  # 処理済みまたはリジェクトされたリクエスト

        # シミュレーション開始時刻を最初のリクエスト到着時刻に設定（もしあれば）
        # sim_arrival_time は float なので、0 との比較は問題ない
        if (
            self.pending_requests and self.pending_requests[0].sim_arrival_time >= 0
        ):  # sim_arrival_time を使用し、0以上か確認
            self.current_time = self.pending_requests[0].sim_arrival_time
        else:
            # リクエストがない場合や、最初の到着時刻が0より小さい（通常はないはず）場合は0.0から開始
            self.current_time = 0.0

    def _get_next_event_time(self) -> float:
        """
        シミュレーション内で次に発生する可能性のあるイベントの時刻を計算します。

        考慮されるイベント:
        - 保留中のリクエストの次の到着時刻。
        - いずれかのワーカーが現在処理中のタスクを完了する時刻。

        Returns:
            float: 次のイベントが発生する最も早い時刻。
                   イベントがない場合は float('inf') を返します。
        """
        next_event_time = float("inf")

        # 1. 次のペンディングリクエストの到着時刻
        if self.pending_requests:
            next_event_time = min(next_event_time, self.pending_requests[0].sim_arrival_time)

        # 2. ワーカーがタスクを完了する時刻
        for worker in self.workers:
            if worker.current_task:  # ワーカーがタスクを処理中の場合
                next_event_time = min(next_event_time, worker.busy_until)

        return next_event_time

    def get_current_time(self) -> float:
        """現在のシミュレーション時刻を返す。"""
        return self.current_time

    def _display_animation_frame(self):
        """アニメーションモードで現在のシミュレーション状態を表示します。"""
        os.system("cls" if os.name == "nt" else "clear")  # noqa: S605
        print("--- Simulation Animation ---")
        print(f"Current Time: {self.current_time:.2f} s")

        # 時:分:秒 形式で表示
        hours = int(self.current_time // 3600)
        minutes = int((self.current_time % 3600) // 60)
        seconds = int(self.current_time % 60)
        print(f"Formatted Time: {hours:02d}:{minutes:02d}:{seconds:02d}")

        print(f"Pending Requests: {len(self.pending_requests)}")
        # キューの状態表示を詳細化
        if isinstance(self.task_queue, PriorityQueueStrategy):
            # PriorityQueueStrategyの場合、各内部キューの長さを表示
            priority_len = self.task_queue.len_priority_queue()
            normal_len = self.task_queue.len_normal_queue()
            print(f"Tasks in Priority Queue: {priority_len}")
            print(f"Tasks in Normal Queue: {normal_len}")
            print(f"Total Tasks in Queue: {priority_len + normal_len}")
        else:
            # それ以外のキュータイプの場合 (例: FifoQueue)
            print(f"Tasks in Queue: {len(self.task_queue)}")

        active_workers = sum(1 for w in self.workers if w.current_task)
        print(f"Active Workers: {active_workers}/{len(self.workers)}")

        print(f"Completed Requests: {len(self.completed_requests)}")

        if self.animation_mode and self.animation_sleep_duration > 0:
            time.sleep(self.animation_sleep_duration)

    def run(self) -> list[Request]:
        """
        シミュレーションを実行します。

        animation_modeがTrueの場合、固定時間ステップでアニメーション表示しながら実行します。
        Falseの場合、イベントドリブンで高速に実行します。

        Returns:
            list[Request]: 処理が完了した（またはリジェクトされた）リクエストのリスト。
                           完了時刻（リジェクトの場合は-1）などの情報が更新されています。
        """
        if self.animation_mode:
            # アニメーションモードのループ
            while self.pending_requests or not self.task_queue.is_empty() or any(w.current_task for w in self.workers):
                self._display_animation_frame()

                # 1. 新しいリクエストの到着を確認し、キューに追加 (現在の時刻までのもの)
                newly_arrived_indices = []
                for i, req in enumerate(self.pending_requests):
                    if req.sim_arrival_time <= self.current_time:  # request_time を sim_arrival_time に変更
                        newly_arrived_indices.append(i)
                    else:
                        break

                for i in sorted(newly_arrived_indices, reverse=True):
                    req_to_enqueue = self.pending_requests.pop(i)
                    req_to_enqueue.arrival_time_in_queue = self.current_time
                    if self.task_queue.is_full():
                        req_to_enqueue.finish_processing_time_by_worker = -1
                        self.completed_requests.append(req_to_enqueue)
                    else:
                        self.task_queue.enqueue(req_to_enqueue)

                # 2. ワーカーにタスクを処理させる
                for worker in self.workers:
                    completed_task = worker.process_task(self.current_time)
                    if completed_task:
                        self.completed_requests.append(completed_task)

                # 3. 時間を進める
                # 全ての処理が終わっていればループを抜ける (アニメーションの最後のフレームを表示するため、先に時間を進めない)
                if (
                    not self.pending_requests
                    and self.task_queue.is_empty()
                    and all(not w.current_task for w in self.workers)
                ):
                    self._display_animation_frame()  # 最後の状態を表示
                    break

                self.current_time += self.animation_update_interval_seconds

            if not (
                not self.pending_requests
                and self.task_queue.is_empty()
                and all(not w.current_task for w in self.workers)
            ):
                self._display_animation_frame()  # ループが途中で抜けた場合（例：最大時間など）も最終状態表示

        else:  # イベント駆動モード (既存のロジック)
            while self.pending_requests or not self.task_queue.is_empty() or any(w.current_task for w in self.workers):
                action_occurred_in_current_step = True
                while action_occurred_in_current_step:
                    action_occurred_in_current_step = False

                    newly_arrived_indices = []
                    for i, req in enumerate(self.pending_requests):
                        if req.sim_arrival_time <= self.current_time:  # request_time を sim_arrival_time に変更
                            newly_arrived_indices.append(i)
                        else:
                            break

                    if newly_arrived_indices:
                        action_occurred_in_current_step = True
                        for i in sorted(newly_arrived_indices, reverse=True):
                            req_to_enqueue = self.pending_requests.pop(i)
                            req_to_enqueue.arrival_time_in_queue = self.current_time
                            if self.task_queue.is_full():
                                req_to_enqueue.finish_processing_time_by_worker = -1
                                self.completed_requests.append(req_to_enqueue)
                            else:
                                self.task_queue.enqueue(req_to_enqueue)

                    for worker in self.workers:
                        original_busy_until = worker.busy_until
                        original_current_task_id = id(worker.current_task) if worker.current_task else None
                        completed_task = worker.process_task(self.current_time)
                        new_current_task_id = id(worker.current_task) if worker.current_task else None

                        if completed_task:
                            self.completed_requests.append(completed_task)
                            action_occurred_in_current_step = True

                        if (
                            worker.current_task
                            and new_current_task_id != original_current_task_id
                            or worker.current_task
                            and worker.busy_until != original_busy_until
                            and original_current_task_id == new_current_task_id
                        ):
                            action_occurred_in_current_step = True

                next_event_time = self._get_next_event_time()
                if next_event_time == float("inf"):
                    if (
                        not self.pending_requests
                        and self.task_queue.is_empty()
                        and all(not w.current_task for w in self.workers)
                    ):
                        break
                    else:
                        break

                if next_event_time > self.current_time:
                    self.current_time = next_event_time
                elif next_event_time <= self.current_time:
                    if not (
                        self.pending_requests
                        or not self.task_queue.is_empty()
                        or any(w.current_task for w in self.workers)
                    ):
                        break
                    pass

        self.completed_requests.sort(
            key=lambda r: (
                r.finish_processing_time_by_worker if r.finish_processing_time_by_worker != -1 else float("inf"),
                r.arrival_time_in_queue,
            )
        )
        return self.completed_requests
