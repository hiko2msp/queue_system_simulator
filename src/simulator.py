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

    def __init__(self, requests: list[Request], num_workers: int, queue_max_size: int | None = None):
        """
        Simulatorのコンストラクタ。

        Args:
            requests (List[Request]): シミュレーション対象のリクエストのリスト。
                                      このリストは内部で到着時刻順にソートされます。
            num_workers (int): シミュレーションで使用するワーカーの数。
            queue_max_size (Optional[int]): タスクキューの最大サイズ。
                                           Noneの場合は無制限。
        """
        # 入力リクエストは変更しないようにコピーしてソート
        self.pending_requests: list[Request] = sorted(list(requests), key=lambda r: r.sim_arrival_time)

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

    def run(self) -> list[Request]:
        """
        シミュレーションを実行します。

        シミュレーションは、保留中のリクエストがなくなり、タスクキューが空になり、
        かつ全てのワーカーがアイドル状態になるまで継続します。
        時間はイベントドリブンで進みます。

        Returns:
            List[Request]: 処理が完了した（またはリジェクトされた）リクエストのリスト。
                           完了時刻（リジェクトの場合は-1）などの情報が更新されています。
        """
        while self.pending_requests or not self.task_queue.is_empty() or any(w.current_task for w in self.workers):
            # print(f"--- Loop Start: Current Time: {self.current_time:.2f}, Pending: {len(self.pending_requests)}, Queue: {len(self.task_queue)}, BusyWorkers: {sum(1 for w in self.workers if w.current_task)} ---")

            action_occurred_in_current_step = True
            while action_occurred_in_current_step:
                action_occurred_in_current_step = False

                # 1. 新しいリクエストの到着を確認し、キューに追加
                newly_arrived_indices = []
                for i, req in enumerate(self.pending_requests):
                    if req.sim_arrival_time <= self.current_time:  # sim_arrival_time を使用
                        newly_arrived_indices.append(i)
                    else:
                        break

                if newly_arrived_indices:
                    action_occurred_in_current_step = True
                    for i in sorted(newly_arrived_indices, reverse=True):
                        req_to_enqueue = self.pending_requests.pop(i)
                        req_to_enqueue.arrival_time_in_queue = self.current_time
                        # TODO: アドミッションコントロール戦略をパラメータ化する。
                        # 現在は単純なis_fullチェックだが、ストラテジーパターンなどで拡張可能にする。
                        if self.task_queue.is_full():
                            # print(f"[Time: {self.current_time:.2f}] Queue full. Request {req_to_enqueue.user_id} rejected at arrival_time_in_queue: {req_to_enqueue.arrival_time_in_queue:.2f}")
                            req_to_enqueue.finish_processing_time_by_worker = -1
                            self.completed_requests.append(req_to_enqueue)
                        else:
                            self.task_queue.enqueue(req_to_enqueue)
                            # print(f"[Time: {self.current_time:.2f}] Request {req_to_enqueue.user_id} enqueued. Arrival_time_in_queue: {req_to_enqueue.arrival_time_in_queue:.2f}")

                # 2. ワーカーにタスクを処理させる (タスク完了 or 新規タスク開始)
                for worker in self.workers:
                    # process_task はタスク完了時に完了タスクを返し、アイドルなら新規タスクを開始する
                    original_busy_until = worker.busy_until
                    original_current_task_id = id(worker.current_task) if worker.current_task else None

                    completed_task = worker.process_task(self.current_time)

                    new_current_task_id = id(worker.current_task) if worker.current_task else None

                    if completed_task:
                        self.completed_requests.append(completed_task)
                        action_occurred_in_current_step = True
                        # print(f"[Time: {self.current_time:.2f}] Task {completed_task.user_id} completed by Worker {worker.worker_id}. Recorded finish_time: {completed_task.finish_processing_time_by_worker:.2f}. Queue len: {len(self.task_queue)}")

                    # 新しいタSKを開始した場合も action_occurred とする
                    if (
                        worker.current_task
                        and new_current_task_id != original_current_task_id
                        or worker.current_task
                        and worker.busy_until != original_busy_until
                        and original_current_task_id == new_current_task_id
                    ):  # 新しいタスクが割り当てられた
                        action_occurred_in_current_step = True

            # 3. 次のイベント時刻に進む
            next_event_time = self._get_next_event_time()
            # print(f"Next event time calculated: {next_event_time}")

            if next_event_time == float("inf"):
                if (
                    not self.pending_requests
                    and self.task_queue.is_empty()
                    and all(not w.current_task for w in self.workers)
                ):
                    # print("--- Simulation End: No more events or tasks. ---")
                    break
                else:
                    # print(f"Warning: next_event_time is inf, but simulation is not over. Current time: {self.current_time}")
                    # print(f"Pending: {len(self.pending_requests)}, Queue: {len(self.task_queue)}, Workers busy: {sum(1 for w in self.workers if w.current_task)}")
                    # print("Forcing break due to potential deadlock.")
                    break  # Potential deadlock or error in logic

            if next_event_time > self.current_time:
                self.current_time = next_event_time
                # print(f"--- Advancing Time to: {self.current_time:.2f} ---")
            elif next_event_time <= self.current_time:
                # この状態は、現在の時刻でまだ処理できるイベントがあるか、
                # もしくは全ての処理が完了して次のイベントがない場合。
                # action_occurred_in_current_step ループで処理されるか、
                # 上の next_event_time == float('inf') でbreakする。
                # 基本的には、時間が進まない場合は、action_occurred_in_current_stepループで何かが起こるはず。
                # それでも進まない場合は、上記のinfチェックで終了する。
                # print(f"Warning or Info: next_event_time ({next_event_time}) <= current_time ({self.current_time}). Action_occurred_in_current_step should handle this or it's end of simulation.")
                # もし、action_occurred_in_current_step が False で、かつ next_event_time <= self.current_time で、
                # さらにシミュレーション終了条件も満たさない場合、無限ループの可能性がある。
                # そのため、_get_next_event_time が常に current_time より厳密に大きい値を返すか、
                # float('inf') を返すように保証することが重要。
                # worker.busy_until は current_time + processing_time なので、processing_time > 0 なら常に未来。
                # processing_time = 0 の場合は busy_until = current_time となりうる。
                # その場合、worker.process_task で完了し、action_occurred が true になる。
                # そして、再度 _get_next_event_time が呼ばれる。
                if not (
                    self.pending_requests or not self.task_queue.is_empty() or any(w.current_task for w in self.workers)
                ):
                    # print("--- Simulation End: All tasks processed and no pending. ---")
                    break  # All tasks processed
                pass

        self.completed_requests.sort(
            key=lambda r: (
                r.finish_processing_time_by_worker if r.finish_processing_time_by_worker != -1 else float("inf"),
                r.arrival_time_in_queue,
            )
        )
        # print(f"Total completed (incl. rejected): {len(self.completed_requests)}")
        return self.completed_requests
