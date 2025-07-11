import os
import time

from src.api_client import APIClient  # APIClient をインポート
from src.data_model import Request
from src.queue_manager import PriorityQueueStrategy  # PriorityQueueStrategy をインポート
from src.worker import Worker

import csv # csvモジュールをインポート
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
        queue_max_size: int | None = None, # PriorityQueueStrategyでは現在未使用
        animation_mode: bool = False,
        animation_update_interval_seconds: float = 1.0,
        log_file_path: str = "simulator_log.csv",
        log_interval_seconds: float = 60.0,
    ):
        """
        Simulatorのコンストラクタ。

        Args:
            requests (list[Request]): シミュレーション対象のリクエストのリスト。
            num_workers (int): シミュレーションで使用するワーカーの数。
            queue_max_size (Optional[int]): タスクキューの最大サイズ (PriorityQueueStrategyでは現在未使用)。
            animation_mode (bool): アニメーションモードを有効にするか。
            animation_update_interval_seconds (float): アニメーションモード時のシミュレーション時間更新間隔（秒）。
            log_file_path (str): ログ出力先のCSVファイルパス。
            log_interval_seconds (float): ログ出力間隔（シミュレーション時間での秒数）。
        """
        self.pending_requests: list[Request] = sorted(requests, key=lambda r: r.sim_arrival_time)
        self.animation_mode = animation_mode
        self.animation_update_interval_seconds = animation_update_interval_seconds
        self.animation_sleep_duration = self.animation_update_interval_seconds / (86400 / 60) if animation_mode else 0

        self.task_queue: PriorityQueueStrategy[Request] = PriorityQueueStrategy()
        # queue_max_size は PriorityQueueStrategy では直接使用されない点に注意

        self.api_client = APIClient(simulator_time_func=self.get_current_time)
        self.workers: list[Worker] = [
            Worker(worker_id=i, task_queue=self.task_queue, api_client=self.api_client) for i in range(num_workers)
        ]
        self.current_time: float = 0.0
        self.completed_requests: list[Request] = []

        # ログ関連の初期化
        self.log_file_path = log_file_path
        self.log_interval_seconds = log_interval_seconds
        self.log_file = None  # ファイルオブジェクトは _initialize_logger で設定
        self.last_log_time: float = 0.0 # 最初のログはシミュレーション開始直後に出力するため0に
        self.cumulative_rejected_requests: int = 0
        self.cumulative_successful_requests: int = 0
        self.cumulative_api_errors: int = 0
        self.successful_requests_since_last_log: int = 0
        # _initialize_logger() は run() の開始時に呼び出す

        if self.pending_requests and self.pending_requests[0].sim_arrival_time >= 0:
            self.current_time = self.pending_requests[0].sim_arrival_time
        else:
            self.current_time = 0.0
        self.last_log_time = self.current_time # last_log_timeも初期時刻に合わせる

    # (コンストラクタの後に追加)

    def _initialize_logger(self):
        """ログファイルを開き、ヘッダーを書き込みます。"""
        try:
            # newline='' はWindowsでの余分な改行を防ぐため
            self.log_file = open(self.log_file_path, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.log_file)
            header = [
                "Timestamp (min)",
                "QueueName",
                "TasksInQueue",
                "CumulativeRejected",
                "CumulativeSucceeded",
                "CumulativeApiErrors",
                "ApiThroughput (req/min)",
            ]
            self.csv_writer.writerow(header)
            # 最初のログエントリを書き込むために、現在の時刻を記録
            # self.last_log_time = self.current_time # コンストラクタで初期化済み
            # 最初のログエントリを即座に書き込む (0分の時点の状態)
            # run 開始時に self.current_time が確定してから初回ログを出すのが良い
            # self._write_log_entry(force_log=True) # runの最初で呼び出す

        except IOError as e:
            print(f"Error: Could not open log file {self.log_file_path}: {e}")
            self.log_file = None # ログ出力が無効になるようにする
            self.csv_writer = None


    def _write_log_entry(self, force_log: bool = False):
        """現在の統計情報をログファイルに書き込みます。"""
        if not self.log_file or not hasattr(self, 'csv_writer') or not self.csv_writer : # csv_writerの存在も確認
            return # ログファイルが正常に開けなかった場合は何もしない

        # force_logがTrueでない場合は、ログ間隔を確認
        # ただし、current_time が last_log_time より小さい場合はログ出力しない (初期状態など)
        if not force_log and (self.current_time < self.last_log_time + self.log_interval_seconds or self.current_time <= self.last_log_time):
            return

        current_simulation_time_minutes = self.current_time / 60.0

        # スループット計算 (直近のログ間隔での成功数 / ログ間隔(分))
        # log_interval_seconds が0の場合はdivision by zeroを避ける
        time_since_last_log_seconds = self.current_time - self.last_log_time
        if time_since_last_log_seconds > 0: # ゼロ除算防止と初回ログ用
            # スループットは「記録間隔」での「単位時間(分)あたり」の処理数
            throughput = (self.successful_requests_since_last_log * 60.0) / time_since_last_log_seconds
        else:
            # 初回ログ(time_since_last_log_seconds=0) またはログ間隔が0の場合、スループットは0とするか、
            # もしくは直近1分間の定義を厳密にする必要がある。
            # ここでは、time_since_last_log_seconds が0なら0とする。
            throughput = 0.0


        if isinstance(self.task_queue, PriorityQueueStrategy):
            # Priority Queue
            self.csv_writer.writerow([
                f"{current_simulation_time_minutes:.2f}",
                "priority",
                self.task_queue.len_priority_queue(),
                self.cumulative_rejected_requests,
                self.cumulative_successful_requests,
                self.cumulative_api_errors,
                f"{throughput:.2f}",
            ])
            # Normal Queue
            self.csv_writer.writerow([
                f"{current_simulation_time_minutes:.2f}",
                "normal",
                self.task_queue.len_normal_queue(),
                self.cumulative_rejected_requests,
                self.cumulative_successful_requests,
                self.cumulative_api_errors,
                f"{throughput:.2f}",
            ])
        else: # 単一キューの場合 (将来の拡張用)
            self.csv_writer.writerow([
                f"{current_simulation_time_minutes:.2f}",
                "default",
                len(self.task_queue),
                self.cumulative_rejected_requests,
                self.cumulative_successful_requests,
                self.cumulative_api_errors,
                f"{throughput:.2f}",
            ])

        self.log_file.flush()
        self.last_log_time = self.current_time
        self.successful_requests_since_last_log = 0

    def _close_logger(self):
        """シミュレーション終了時にログファイルを閉じます。"""
        if self.log_file:
            # runループの最後で最終ログを書き込む設計なので、ここでは閉じるだけ
            self.log_file.close()
            self.log_file = None
            if hasattr(self, 'csv_writer'): # csv_writerが存在する場合のみ削除
                del self.csv_writer


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
        self._initialize_logger() # ログ初期化

        if self.animation_mode:
            # アニメーションモードのループ
            self._write_log_entry(force_log=True) # 初回ログ
            while self.pending_requests or not self.task_queue.is_empty() or any(w.current_task for w in self.workers):
                self._display_animation_frame()
                self._write_log_entry() # 定期的なログ出力

                # 1. 新しいリクエストの到着を確認し、キューに追加 (現在の時刻までのもの)
                newly_arrived_indices = []
                for i, req in enumerate(self.pending_requests):
                    if req.sim_arrival_time <= self.current_time:
                        newly_arrived_indices.append(i)
                    else:
                        break

                for i in sorted(newly_arrived_indices, reverse=True):
                    req_to_enqueue = self.pending_requests.pop(i)
                    req_to_enqueue.arrival_time_in_queue = self.current_time
                    if self.task_queue.is_full(): # PriorityQueueStrategyでは現状常にFalse
                        req_to_enqueue.finish_processing_time_by_worker = -1
                        self.completed_requests.append(req_to_enqueue)
                        self.cumulative_rejected_requests += 1 # リジェクトカウント
                    else:
                        self.task_queue.enqueue(req_to_enqueue)

                # 2. ワーカーにタスクを処理させる
                for worker in self.workers:
                    completed_task = worker.process_task(self.current_time)
                    if completed_task:
                        self.completed_requests.append(completed_task)
                        if completed_task.finish_processing_time_by_worker != -1: # 正常完了
                            self.cumulative_successful_requests += 1
                            self.successful_requests_since_last_log += 1
                            if completed_task.api_error_occurred:
                                self.cumulative_api_errors += 1
                        # リジェクトはキュー追加時にカウント済み (finish_processing_time_by_worker == -1 の場合)


                # 3. 時間を進める
                # 全ての処理が終わっていればループを抜ける (アニメーションの最後のフレームを表示するため、先に時間を進めない)
                if (
                    not self.pending_requests
                    and self.task_queue.is_empty()
                    and all(not w.current_task for w in self.workers)
                ):
                    self._display_animation_frame()  # 最後の状態を表示
                    self._write_log_entry(force_log=True) # 最後の状態をログに書く
                    break

                self.current_time += self.animation_update_interval_seconds

            if not ( # ループが途中で抜けた場合（例：最大時間など）も最終状態表示とログ
                not self.pending_requests
                and self.task_queue.is_empty()
                and all(not w.current_task for w in self.workers)
            ):
                self._display_animation_frame()
                self._write_log_entry(force_log=True)


        else:  # イベント駆動モード (既存のロジック)
            self._write_log_entry(force_log=True) # 初回ログ
            while self.pending_requests or not self.task_queue.is_empty() or any(w.current_task for w in self.workers):
                self._write_log_entry() # 定期的なログ出力 (イベント発生時にも評価される)
                action_occurred_in_current_step = True
                while action_occurred_in_current_step:
                    action_occurred_in_current_step = False

                    newly_arrived_indices = []
                    for i, req in enumerate(self.pending_requests):
                        if req.sim_arrival_time <= self.current_time:
                            newly_arrived_indices.append(i)
                        else:
                            break

                    if newly_arrived_indices:
                        action_occurred_in_current_step = True
                        for i in sorted(newly_arrived_indices, reverse=True):
                            req_to_enqueue = self.pending_requests.pop(i)
                            req_to_enqueue.arrival_time_in_queue = self.current_time
                            if self.task_queue.is_full(): # PriorityQueueStrategyでは現状常にFalse
                                req_to_enqueue.finish_processing_time_by_worker = -1
                                self.completed_requests.append(req_to_enqueue)
                                self.cumulative_rejected_requests += 1 # リジェクトカウント
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
                            if completed_task.finish_processing_time_by_worker != -1: # 正常完了
                                self.cumulative_successful_requests += 1
                                self.successful_requests_since_last_log += 1
                                if completed_task.api_error_occurred:
                                    self.cumulative_api_errors += 1


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
                        self._write_log_entry(force_log=True) # 最後の状態をログに書く
                        break
                    else:
                        # This case might indicate an issue or an edge case not fully handled
                        # For now, assume it eventually resolves or is covered by the outer loop condition
                        self._write_log_entry(force_log=True) # 最後の状態をログに書く
                        break

                if next_event_time > self.current_time:
                    self.current_time = next_event_time
                elif next_event_time <= self.current_time: # Should ideally not spin if no state change
                    if not (
                        self.pending_requests
                        or not self.task_queue.is_empty()
                        or any(w.current_task for w in self.workers)
                    ):
                        self._write_log_entry(force_log=True) # 最後の状態をログに書く
                        break
                    # If stuck here, it implies current_time did not advance but events might still be processable
                    # or _get_next_event_time() is returning current_time.
                    # This could lead to a busy loop if not handled carefully.
                    # For now, we assume the logic within the inner while loop advances state or
                    # _get_next_event_time will eventually return a future time or inf.
                    pass
            # Ensure final log entry if loop terminates for other reasons
            self._write_log_entry(force_log=True)


        self._close_logger() # ログクローズ

        self.completed_requests.sort(
            key=lambda r: (
                r.finish_processing_time_by_worker if r.finish_processing_time_by_worker != -1 else float("inf"),
                r.arrival_time_in_queue,
            )
        )
        return self.completed_requests
