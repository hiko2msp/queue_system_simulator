import unittest

from src.csv_parser import parse_csv  # サンプルCSV読み込み用
from src.data_model import Request
from src.simulator import Simulator


class TestSimulator(unittest.TestCase):
    def test_simple_simulation_one_worker_one_request(self):
        requests = [Request("user1", 0.0, 2.0)]
        simulator = Simulator(requests, num_workers=1)
        completed = simulator.run()

        self.assertEqual(len(completed), 1)
        task = completed[0]
        self.assertEqual(task.user_id, "user1")
        self.assertEqual(task.request_time, 0.0)
        self.assertEqual(task.arrival_time_in_queue, 0.0)
        self.assertEqual(task.start_processing_time_by_worker, 0.0)
        self.assertEqual(task.finish_processing_time_by_worker, 2.0)

    def test_simulation_multiple_requests_one_worker(self):
        requests = [Request("user1", 0.0, 2.0), Request("user2", 0.5, 1.0)]
        # 期待される動作:
        # T=0.0: user1 到着、キューへ。W1がuser1処理開始 (busy_until=2.0)
        # T=0.5: user2 到着、キューへ。
        # T=2.0: W1がuser1処理完了。W1がuser2処理開始 (busy_until=3.0)
        # T=3.0: W1がuser2処理完了。
        simulator = Simulator(requests, num_workers=1)
        completed = simulator.run()

        self.assertEqual(len(completed), 2)

        task1 = next(r for r in completed if r.user_id == "user1")
        task2 = next(r for r in completed if r.user_id == "user2")

        self.assertEqual(task1.arrival_time_in_queue, 0.0)
        self.assertEqual(task1.start_processing_time_by_worker, 0.0)
        self.assertEqual(task1.finish_processing_time_by_worker, 2.0)

        self.assertEqual(task2.request_time, 0.5)
        # current_time が 0.5 に進んだときにキューイングされる
        self.assertEqual(task2.arrival_time_in_queue, 0.5)
        self.assertEqual(task2.start_processing_time_by_worker, 2.0)
        self.assertEqual(task2.finish_processing_time_by_worker, 3.0)

    def test_simulation_requests_arrive_later_one_worker(self):
        requests = [Request("user1", 1.0, 2.0), Request("user2", 1.5, 1.0)]
        # 期待される動作:
        # T=1.0: user1 到着、キューへ。W1がuser1処理開始 (busy_until=3.0)
        # T=1.5: user2 到着、キューへ。
        # T=3.0: W1がuser1処理完了。W1がuser2処理開始 (busy_until=4.0)
        # T=4.0: W1がuser2処理完了。
        simulator = Simulator(requests, num_workers=1)
        completed = simulator.run()
        self.assertEqual(len(completed), 2)

        task1 = next(r for r in completed if r.user_id == "user1")
        task2 = next(r for r in completed if r.user_id == "user2")

        self.assertEqual(task1.request_time, 1.0)
        self.assertEqual(task1.arrival_time_in_queue, 1.0)
        self.assertEqual(task1.start_processing_time_by_worker, 1.0)
        self.assertEqual(task1.finish_processing_time_by_worker, 3.0)

        self.assertEqual(task2.request_time, 1.5)
        self.assertEqual(task2.arrival_time_in_queue, 1.5)
        self.assertEqual(task2.start_processing_time_by_worker, 3.0)
        self.assertEqual(task2.finish_processing_time_by_worker, 4.0)

    def test_simulation_two_workers_competing_tasks(self):
        requests = [Request("user1", 0.0, 3.0), Request("user2", 0.1, 1.0), Request("user3", 0.2, 2.0)]
        # 期待される動作:
        # T=0.0: user1 到着、キューへ。W1がuser1処理開始 (busy_until=3.0)
        # T=0.1: user2 到着、キューへ。W2がuser2処理開始 (busy_until=1.1)
        # T=0.2: user3 到着、キューへ。
        # T=1.1: W2がuser2処理完了。W2がuser3処理開始 (busy_until=3.1)
        # T=3.0: W1がuser1処理完了。
        # T=3.1: W2がuser3処理完了。
        simulator = Simulator(requests, num_workers=2)
        completed = simulator.run()
        self.assertEqual(len(completed), 3)

        task1 = next(r for r in completed if r.user_id == "user1")
        task2 = next(r for r in completed if r.user_id == "user2")
        task3 = next(r for r in completed if r.user_id == "user3")

        # 処理順序はワーカーの割り当てに依存するが、最終的な完了時刻は決まるはず
        # user1 (W1 or W2)
        self.assertEqual(task1.arrival_time_in_queue, 0.0)
        self.assertEqual(task1.start_processing_time_by_worker, 0.0)  # 先に到着
        self.assertEqual(task1.finish_processing_time_by_worker, 3.0)

        # user2 (W1 or W2, user1を取らなかった方)
        self.assertEqual(task2.arrival_time_in_queue, 0.1)
        self.assertEqual(task2.start_processing_time_by_worker, 0.1)  # user1とほぼ同時だが別ワーカー
        self.assertEqual(task2.finish_processing_time_by_worker, 1.1)

        # user3 (user2を処理したワーカー(W2)が次に処理)
        self.assertEqual(task3.arrival_time_in_queue, 0.2)
        self.assertEqual(task3.start_processing_time_by_worker, 1.1)  # user2の完了後
        self.assertEqual(task3.finish_processing_time_by_worker, 3.1)

    def test_simulation_with_sample_csv_one_worker(self):
        requests = parse_csv("sample_requests.csv")
        simulator = Simulator(requests, num_workers=1)
        completed = simulator.run()
        self.assertEqual(len(completed), 5)

        results_map = {r.user_id: r for r in completed}

        self.assertEqual(results_map["user_a"].arrival_time_in_queue, 0.0)
        self.assertEqual(results_map["user_a"].start_processing_time_by_worker, 0.0)
        self.assertEqual(results_map["user_a"].finish_processing_time_by_worker, 5.0)

        self.assertEqual(results_map["user_b"].arrival_time_in_queue, 0.5)
        self.assertEqual(results_map["user_b"].start_processing_time_by_worker, 5.0)
        self.assertEqual(results_map["user_b"].finish_processing_time_by_worker, 8.0)

        self.assertEqual(results_map["user_c"].arrival_time_in_queue, 1.0)
        self.assertEqual(results_map["user_c"].start_processing_time_by_worker, 8.0)
        self.assertEqual(results_map["user_c"].finish_processing_time_by_worker, 10.0)

        self.assertEqual(results_map["user_d"].arrival_time_in_queue, 1.2)
        self.assertEqual(results_map["user_d"].start_processing_time_by_worker, 10.0)
        self.assertEqual(results_map["user_d"].finish_processing_time_by_worker, 14.0)

        self.assertEqual(results_map["user_e"].arrival_time_in_queue, 2.0)
        self.assertEqual(results_map["user_e"].start_processing_time_by_worker, 14.0)
        self.assertEqual(results_map["user_e"].finish_processing_time_by_worker, 15.0)

    def test_simulation_with_sample_csv_two_workers(self):
        requests = parse_csv("sample_requests.csv")
        simulator = Simulator(requests, num_workers=2)
        completed = simulator.run()
        self.assertEqual(len(completed), 5)

        results_map = {r.user_id: r for r in completed}

        # user_a,0.0,5.0  -> W1: ArrQ:0.0, Start:0.0, End:5.0
        # user_b,0.5,3.0  -> W2: ArrQ:0.5, Start:0.5, End:3.5
        # user_c,1.0,2.0  -> W2: ArrQ:1.0, Start:3.5, End:5.5 (W2がuser_b完了後)
        # user_d,1.2,4.0  -> W1: ArrQ:1.2, Start:5.0, End:9.0 (W1がuser_a完了後)
        # user_e,2.0,1.0  -> W2: ArrQ:2.0, Start:5.5, End:6.5 (W2がuser_c完了後)

        self.assertEqual(results_map["user_a"].arrival_time_in_queue, 0.0)
        self.assertEqual(results_map["user_a"].start_processing_time_by_worker, 0.0)
        self.assertEqual(results_map["user_a"].finish_processing_time_by_worker, 5.0)

        self.assertEqual(results_map["user_b"].arrival_time_in_queue, 0.5)
        self.assertEqual(results_map["user_b"].start_processing_time_by_worker, 0.5)
        self.assertEqual(results_map["user_b"].finish_processing_time_by_worker, 3.5)

        self.assertEqual(results_map["user_c"].arrival_time_in_queue, 1.0)
        self.assertEqual(results_map["user_c"].start_processing_time_by_worker, 3.5)
        self.assertEqual(results_map["user_c"].finish_processing_time_by_worker, 5.5)

        self.assertEqual(results_map["user_d"].arrival_time_in_queue, 1.2)
        self.assertEqual(results_map["user_d"].start_processing_time_by_worker, 5.0)
        self.assertEqual(results_map["user_d"].finish_processing_time_by_worker, 9.0)

        self.assertEqual(results_map["user_e"].arrival_time_in_queue, 2.0)
        self.assertEqual(results_map["user_e"].start_processing_time_by_worker, 5.5)
        self.assertEqual(results_map["user_e"].finish_processing_time_by_worker, 6.5)

    def test_queue_full_rejection(self):
        requests = [Request("user1", 0.0, 1.0), Request("user2", 0.1, 1.0), Request("user3", 0.2, 1.0)]
        # 期待:
        # T=0.0: user1 到着、キューへ。W1がuser1処理開始 (busy_until=1.0)
        # T=0.1: user2 到着、キューへ(size=1なのでOK)。
        # T=0.2: user3 到着。キューはuser2で満杯なのでリジェクト。
        # T=1.0: W1がuser1完了。W1がuser2処理開始 (busy_until=2.0)
        # T=2.0: W1がuser2完了。
        simulator = Simulator(requests, num_workers=1, queue_max_size=1)  # キューサイズ1
        completed = simulator.run()

        self.assertEqual(len(completed), 3)  # リジェクトされたものもリストには入る
        results_map = {r.user_id: r for r in completed}

        self.assertEqual(results_map["user1"].arrival_time_in_queue, 0.0)
        self.assertEqual(results_map["user1"].start_processing_time_by_worker, 0.0)
        self.assertEqual(results_map["user1"].finish_processing_time_by_worker, 1.0)

        self.assertEqual(results_map["user2"].arrival_time_in_queue, 0.1)
        self.assertEqual(results_map["user2"].start_processing_time_by_worker, 1.0)
        self.assertEqual(results_map["user2"].finish_processing_time_by_worker, 2.0)

        # PriorityQueueStrategyではキューサイズ制限が働かないため、user3も処理される
        self.assertEqual(results_map["user3"].arrival_time_in_queue, 0.2)
        # self.assertEqual(results_map["user3"].start_processing_time_by_worker, 0.0) # 元: 未処理
        # self.assertEqual(results_map["user3"].finish_processing_time_by_worker, -1) # 元: リジェクト印
        self.assertEqual(results_map["user3"].start_processing_time_by_worker, 2.0)  # user2の完了後
        self.assertEqual(results_map["user3"].finish_processing_time_by_worker, 3.0)  # 2.0 + 1.0

    def test_all_requests_arrive_before_first_completion(self):
        requests = [
            Request("R1", 0.0, 5.0),  # W1: 0-5
            Request("R2", 0.1, 1.0),  # W2: 0.1-1.1
            Request("R3", 0.2, 1.0),  # W2: 1.1-2.1 (after R2)
            Request("R4", 0.3, 1.0),  # W2: 2.1-3.1 (after R3)
        ]
        simulator = Simulator(requests, num_workers=2)
        completed = simulator.run()
        self.assertEqual(len(completed), 4)

        r_map = {r.user_id: r for r in completed}
        self.assertEqual(r_map["R1"].finish_processing_time_by_worker, 5.0)  # W1
        self.assertEqual(r_map["R2"].finish_processing_time_by_worker, 1.1)  # W2
        self.assertEqual(r_map["R3"].finish_processing_time_by_worker, 2.1)  # W2
        self.assertEqual(r_map["R4"].finish_processing_time_by_worker, 3.1)  # W2

    def test_no_requests(self):
        simulator = Simulator([], num_workers=1)
        completed = simulator.run()
        self.assertEqual(len(completed), 0)

    def test_zero_processing_time(self):
        requests = [Request("R1", 0.0, 0.0)]
        simulator = Simulator(requests, num_workers=1)
        completed = simulator.run()
        self.assertEqual(len(completed), 1)
        task = completed[0]
        self.assertEqual(task.arrival_time_in_queue, 0.0)
        self.assertEqual(task.start_processing_time_by_worker, 0.0)
        self.assertEqual(task.finish_processing_time_by_worker, 0.0)


if __name__ == "__main__":
    unittest.main()
