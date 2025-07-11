import datetime  # datetime をインポート
import os
import unittest

from src.csv_parser import parse_csv
from src.data_model import Request


class TestCSVParser(unittest.TestCase):
    def setUp(self):
        # テスト用のCSVファイルを作成
        self.test_csv_file = "test_requests.csv"
        with open(self.test_csv_file, mode="w", encoding="utf-8") as file:
            file.write("user_id,request_time,processing_time\n")
            # ISO 8601形式の時刻文字列を使用
            file.write("user1,2023-01-01T00:00:00.100000Z,1.0\n")
            file.write("user2,2023-01-01T00:00:00.200000Z,2.0\n")
            file.write("user3,2023-01-01T00:00:00.300000Z,0.5\n")

        self.empty_csv_file = "empty_requests.csv"
        with open(self.empty_csv_file, mode="w", encoding="utf-8") as file:
            file.write("user_id,request_time,processing_time\n")

        self.malformed_request_time_csv_file = "malformed_rt_requests.csv"
        with open(self.malformed_request_time_csv_file, mode="w", encoding="utf-8") as file:
            file.write("user_id,request_time,processing_time\n")
            # 不正なrequest_time (ISO 8601ではない)
            file.write("user1,not_a_datetime_string,1.0\n")

        self.malformed_processing_time_csv_file = "malformed_pt_requests.csv"
        with open(self.malformed_processing_time_csv_file, mode="w", encoding="utf-8") as file:
            file.write("user_id,request_time,processing_time\n")
            file.write("user1,2023-01-01T00:00:00.100000Z,not_a_float\n")

        self.missing_column_csv_file = "missing_column_requests.csv"
        with open(self.missing_column_csv_file, mode="w", encoding="utf-8") as file:
            file.write("user_id,request_time\n")  # カラム不足
            file.write("user1,2023-01-01T00:00:00.100000Z\n")

    def tearDown(self):
        # テストファイルを削除
        files_to_remove = [
            self.test_csv_file,
            self.empty_csv_file,
            self.malformed_request_time_csv_file,
            self.malformed_processing_time_csv_file,
            self.missing_column_csv_file,
        ]
        for f_path in files_to_remove:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_parse_valid_csv(self):
        requests = parse_csv(self.test_csv_file)
        self.assertEqual(len(requests), 3)
        self.assertIsInstance(requests[0], Request)
        self.assertEqual(requests[0].user_id, "user1")
        # datetimeオブジェクトとして比較
        expected_dt_user1 = datetime.datetime(2023, 1, 1, 0, 0, 0, 100000, tzinfo=datetime.UTC)
        self.assertEqual(requests[0].request_time, expected_dt_user1)
        self.assertEqual(requests[0].processing_time, 1.0)

        self.assertEqual(requests[1].user_id, "user2")
        expected_dt_user2 = datetime.datetime(2023, 1, 1, 0, 0, 0, 200000, tzinfo=datetime.UTC)
        self.assertEqual(requests[1].request_time, expected_dt_user2)

        self.assertEqual(requests[2].user_id, "user3")
        expected_dt_user3 = datetime.datetime(2023, 1, 1, 0, 0, 0, 300000, tzinfo=datetime.UTC)
        self.assertEqual(requests[2].request_time, expected_dt_user3)
        self.assertEqual(requests[2].processing_time, 0.5)

    def test_parse_sample_csv(self):
        # このテストは、事前に sample_requests.csv が新しい形式で生成されていることを前提とします。
        # scripts/generate_sample_data.py を実行して生成してください。
        sample_csv_path = "sample_requests.csv"
        if not os.path.exists(sample_csv_path):
            # スクリプトを実行して sample_requests.csv を生成
            try:
                import subprocess

                subprocess.run(["python", "scripts/generate_sample_data.py"], check=True)
                print(f"'{sample_csv_path}' generated for test.")
            except Exception as e:
                self.skipTest(f"Failed to generate '{sample_csv_path}' for testing. Error: {e}")
                return

        requests = parse_csv(sample_csv_path)
        self.assertTrue(len(requests) > 0, f"'{sample_csv_path}' should contain some requests.")
        if len(requests) > 0:
            self.assertIsInstance(requests[0], Request)
            self.assertIsInstance(requests[0].request_time, datetime.datetime)
            self.assertIsNotNone(requests[0].request_time.tzinfo, "Parsed datetime should be timezone-aware")
            self.assertEqual(requests[0].request_time.tzinfo, datetime.UTC, "Parsed datetime should be UTC")

    def test_parse_empty_csv(self):
        requests = parse_csv(self.empty_csv_file)
        self.assertEqual(len(requests), 0)

    def test_parse_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            parse_csv("non_existent_file.csv")

    def test_parse_malformed_request_time_csv(self):
        with self.assertRaises(ValueError) as context:
            parse_csv(self.malformed_request_time_csv_file)
        self.assertTrue(
            "型変換に失敗しました" in str(context.exception) or "time data" in str(context.exception).lower()
        )

    def test_parse_malformed_processing_time_csv(self):
        with self.assertRaises(ValueError) as context:
            parse_csv(self.malformed_processing_time_csv_file)
        self.assertTrue(
            "型変換に失敗しました" in str(context.exception)
            or "could not convert string to float" in str(context.exception).lower()
        )

    def test_parse_missing_column_csv(self):
        with self.assertRaises(KeyError) as context:
            parse_csv(self.missing_column_csv_file)
        self.assertTrue("期待されるカラム 'processing_time' が見つかりません" in str(context.exception))


if __name__ == "__main__":
    unittest.main()
