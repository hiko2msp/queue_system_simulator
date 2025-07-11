import unittest

import numpy as np

from src.data_model import Request
from src.statistics import calculate_percentiles, calculate_queuing_times, calculate_simulation_statistics


class TestStatistics(unittest.TestCase):
    def test_calculate_queuing_times(self):
        requests = [
            Request(
                "u1",
                0,
                1,
                arrival_time_in_queue=0.0,
                start_processing_time_by_worker=0.0,
                finish_processing_time_by_worker=1.0,
            ),  # Q time = 0
            Request(
                "u2",
                0,
                1,
                arrival_time_in_queue=0.1,
                start_processing_time_by_worker=1.0,
                finish_processing_time_by_worker=2.0,
            ),  # Q time = 0.9
            Request(
                "u3",
                0,
                1,
                arrival_time_in_queue=0.2,
                start_processing_time_by_worker=0.2,
                finish_processing_time_by_worker=1.2,
            ),  # Q time = 0
            Request(
                "u4",
                0,
                1,
                arrival_time_in_queue=0.3,
                start_processing_time_by_worker=2.0,
                finish_processing_time_by_worker=3.0,
            ),  # Q time = 1.7
            Request(
                "u5",
                0,
                1,
                arrival_time_in_queue=0.4,
                start_processing_time_by_worker=0.0,
                finish_processing_time_by_worker=-1,
            ),  # Rejected, start_processing_time_by_worker is dummy
        ]
        queuing_times = calculate_queuing_times(
            requests
        )  # calculate_queuing_timesは完了リスト全体を受け取るが、内部でフィルタする

        # 正しくは、calculate_queuing_times には処理済みリクエストのみを渡すことを想定しているが、
        # 現在の実装では completed_requests 全体を受け取り、内部でフィルタリングしている。
        # テストデータはそれを反映。

        processed_requests_for_queuing_calc = [r for r in requests if r.finish_processing_time_by_worker != -1]
        queuing_times_direct = calculate_queuing_times(processed_requests_for_queuing_calc)

        self.assertEqual(len(queuing_times_direct), 4)  # u5は除外
        self.assertAlmostEqual(queuing_times_direct[0], 0.0)
        self.assertAlmostEqual(queuing_times_direct[1], 0.9)
        self.assertAlmostEqual(queuing_times_direct[2], 0.0)
        self.assertAlmostEqual(queuing_times_direct[3], 1.7)

    def test_calculate_queuing_times_attributes_not_set(self):
        # arrival_time_in_queue や start_processing_time_by_worker が初期値(0.0)のままのリクエスト
        # (シミュレーションロジックで適切に設定されるはずだが、万が一の場合)
        requests = [
            Request(
                "u1", 0, 1, finish_processing_time_by_worker=1.0
            ),  # arrival_time_in_queue と start_processing_time_by_worker が 0.0
            Request(
                "u2", 0, 1, arrival_time_in_queue=1.0, finish_processing_time_by_worker=2.0
            ),  # start_processing_time_by_worker が 0.0
        ]
        # u1: start(0) - arrival(0) = 0
        # u2: start(0) - arrival(1) = -1 -> このケースは queuing_times には追加されない (start >= arrival の条件のため)
        queuing_times = calculate_queuing_times(requests)
        self.assertEqual(len(queuing_times), 1)
        self.assertAlmostEqual(queuing_times[0], 0.0)

    def test_calculate_queuing_times_empty(self):
        self.assertEqual(calculate_queuing_times([]), [])
        requests_all_rejected = [
            Request(
                "u5",
                0,
                1,
                arrival_time_in_queue=0.4,
                start_processing_time_by_worker=0.0,
                finish_processing_time_by_worker=-1,
            )
        ]
        self.assertEqual(calculate_queuing_times(requests_all_rejected), [])

    def test_calculate_percentiles(self):
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # p50=5.5, p75=7.75
        percentiles = calculate_percentiles(data, [50, 75, 90])
        self.assertAlmostEqual(percentiles["p50"], 5.5)
        self.assertAlmostEqual(percentiles["p75"], 7.75)
        self.assertAlmostEqual(percentiles["p90"], 9.1)

    def test_calculate_percentiles_single_value(self):
        data = [5]
        percentiles = calculate_percentiles(data, [0, 50, 100])
        self.assertAlmostEqual(percentiles["p0"], 5.0)
        self.assertAlmostEqual(percentiles["p50"], 5.0)
        self.assertAlmostEqual(percentiles["p100"], 5.0)

    def test_calculate_percentiles_empty_data(self):
        percentiles = calculate_percentiles([], [50, 75])
        self.assertTrue(np.isnan(percentiles["p50"]))
        self.assertTrue(np.isnan(percentiles["p75"]))

    def test_calculate_percentiles_invalid_percentile_value(self):
        with self.assertRaises(ValueError):
            calculate_percentiles([1, 2, 3], [-10])
        with self.assertRaises(ValueError):
            calculate_percentiles([1, 2, 3], [110])

    def test_calculate_simulation_statistics(self):
        requests = [
            Request(
                "u1",
                0,
                1,
                arrival_time_in_queue=0.0,
                start_processing_time_by_worker=0.0,
                finish_processing_time_by_worker=1.0,
            ),
            Request(
                "u2",
                0,
                1,
                arrival_time_in_queue=0.1,
                start_processing_time_by_worker=1.0,
                finish_processing_time_by_worker=2.0,
            ),
            Request(
                "u3",
                0,
                1,
                arrival_time_in_queue=0.2,
                start_processing_time_by_worker=0.2,
                finish_processing_time_by_worker=1.2,
            ),
            Request(
                "u4",
                0,
                1,
                arrival_time_in_queue=0.3,
                start_processing_time_by_worker=2.0,
                finish_processing_time_by_worker=3.0,
            ),
            Request(
                "u5",
                0,
                1,
                arrival_time_in_queue=0.4,
                start_processing_time_by_worker=0.0,
                finish_processing_time_by_worker=-1,
            ),
        ]
        # Queuing times for processed: [0.0, 0.9, 0.0, 1.7]

        stats = calculate_simulation_statistics(requests)
        self.assertEqual(stats["total_requests_processed"], 4)
        self.assertEqual(stats["total_requests_rejected"], 1)
        self.assertAlmostEqual(stats["average_queuing_time"], 0.65)
        self.assertAlmostEqual(stats["p50"], 0.45)
        self.assertAlmostEqual(stats["p75"], 1.1)
        self.assertAlmostEqual(stats["p90"], 1.46)
        self.assertAlmostEqual(stats["p99"], 1.676)

    def test_calculate_simulation_statistics_all_rejected(self):
        requests = [
            Request(
                "u1",
                0,
                1,
                arrival_time_in_queue=0.0,
                start_processing_time_by_worker=0.0,
                finish_processing_time_by_worker=-1,
            ),
            Request(
                "u2",
                0,
                1,
                arrival_time_in_queue=0.1,
                start_processing_time_by_worker=0.0,
                finish_processing_time_by_worker=-1,
            ),
        ]
        stats = calculate_simulation_statistics(requests)
        self.assertEqual(stats["total_requests_processed"], 0)
        self.assertEqual(stats["total_requests_rejected"], 2)
        self.assertTrue(np.isnan(stats["average_queuing_time"]))
        self.assertTrue(np.isnan(stats["p50"]))
        self.assertTrue(np.isnan(stats["p75"]))

    def test_calculate_simulation_statistics_no_requests(self):
        stats = calculate_simulation_statistics([])
        self.assertEqual(stats["total_requests_processed"], 0)
        self.assertEqual(stats["total_requests_rejected"], 0)
        self.assertTrue(np.isnan(stats["average_queuing_time"]))
        self.assertTrue(np.isnan(stats["p50"]))
        self.assertTrue(np.isnan(stats["p75"]))

    def test_calculate_simulation_statistics_one_processed_request(self):
        requests = [
            Request(
                "u1",
                0,
                1,
                arrival_time_in_queue=0.0,
                start_processing_time_by_worker=0.1,
                finish_processing_time_by_worker=1.1,
            ),  # Q time = 0.1
        ]
        stats = calculate_simulation_statistics(requests)
        self.assertEqual(stats["total_requests_processed"], 1)
        self.assertEqual(stats["total_requests_rejected"], 0)
        self.assertAlmostEqual(stats["average_queuing_time"], 0.1)
        self.assertAlmostEqual(stats["p50"], 0.1)
        self.assertAlmostEqual(stats["p75"], 0.1)
        self.assertAlmostEqual(stats["p90"], 0.1)
        self.assertAlmostEqual(stats["p99"], 0.1)

    def test_calculate_simulation_statistics_api_usage(self):
        # settings.NUM_EXTERNAL_APIS をテスト用に設定
        from config import settings as test_settings

        original_num_apis = test_settings.NUM_EXTERNAL_APIS
        test_settings.NUM_EXTERNAL_APIS = 3  # テスト中は3つのAPIがあると仮定

        requests = [
            Request("u1", 0, 1, used_api_id=1, finish_processing_time_by_worker=1.0),
            Request("u2", 0, 1, used_api_id=2, finish_processing_time_by_worker=1.0),
            Request("u3", 0, 1, used_api_id=1, finish_processing_time_by_worker=1.0),
            Request("u4", 0, 1, used_api_id=3, finish_processing_time_by_worker=1.0),
            Request("u5", 0, 1, used_api_id=None, finish_processing_time_by_worker=1.0),  # API IDなし
            Request("u6", 0, 1, used_api_id=1, finish_processing_time_by_worker=1.0),
            Request("u7", 0, 1, used_api_id=4, finish_processing_time_by_worker=1.0),  # 想定外のAPI ID
            Request(
                "u8", 0, 1, used_api_id=2, finish_processing_time_by_worker=-1
            ),  # リジェクトされたタスク (API使用カウントに影響しない)
        ]

        # calculate_simulation_statistics は src.statistics モジュールレベルで settings を import しているため、
        # リロードが必要な場合がある。今回はテスト実行時に settings が評価されることを期待。
        # (より堅牢なのは、NUM_EXTERNAL_APIS を関数に渡すか、クラスのメソッドにするなど依存性を注入する形)
        import importlib

        from src import statistics

        importlib.reload(statistics)  # settingsの変更を反映させるため

        stats = statistics.calculate_simulation_statistics(requests)

        expected_api_usage = {
            "api_1": 3,  # u1, u3, u6
            "api_2": 1,  # u2
            "api_3": 1,  # u4
            # api_4 は NUM_EXTERNAL_APIS = 3 の範囲外なので、基本的にはキーとして存在しないか、
            # もし未知のキーとしてカウントするロジックがあればそちらで。現在の実装ではprint Warningして無視。
            # テストケースのu7は、現状のロジックではapi_usage_countsに含まれない（Warningが出る）
        }
        # NUM_EXTERNAL_APIS に基づいて初期化されるので、キーは存在するはず
        self.assertIn("api_usage_counts", stats)
        actual_counts = stats["api_usage_counts"]

        self.assertEqual(actual_counts.get("api_1", 0), 3)
        self.assertEqual(actual_counts.get("api_2", 0), 1)
        self.assertEqual(actual_counts.get("api_3", 0), 1)
        # api_4 は NUM_EXTERNAL_APIS=3 のため、キーとして存在しないか、値が0のはず
        self.assertNotIn(
            "api_4",
            actual_counts,
            "API ID outside NUM_EXTERNAL_APIS should not be a primary key unless handled explicitly",
        )
        # または、もしキーが必ず作られるなら self.assertEqual(actual_counts.get("api_4", 0), 0)

        # 処理されたリクエスト (u8以外) のうち、used_api_idがNoneでないものは6件 (u1,u2,u3,u4,u6,u7)
        # そのうち、NUM_EXTERNAL_APISの範囲内 (1,2,3) なのは5件 (u1,u2,u3,u4,u6)
        # よって、カウントの合計は 3+1+1 = 5
        self.assertEqual(sum(actual_counts.values()), 5)

        # settingsを元に戻す
        test_settings.NUM_EXTERNAL_APIS = original_num_apis
        importlib.reload(statistics)  # 元のsettings値を反映させる


if __name__ == "__main__":
    unittest.main()
