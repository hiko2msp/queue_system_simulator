import unittest
import os
from src.csv_parser import parse_csv
from src.data_model import Request

class TestCSVParser(unittest.TestCase):
    def setUp(self):
        # テスト用のCSVファイルを作成
        self.test_csv_file = "test_requests.csv"
        with open(self.test_csv_file, mode='w', encoding='utf-8') as file:
            file.write("user_id,request_time,processing_time\n")
            file.write("user1,0.1,1.0\n")
            file.write("user2,0.2,2.0\n")
            file.write("user3,0.3,0.5\n")

        self.empty_csv_file = "empty_requests.csv"
        with open(self.empty_csv_file, mode='w', encoding='utf-8') as file:
            file.write("user_id,request_time,processing_time\n")

        self.malformed_csv_file = "malformed_requests.csv"
        with open(self.malformed_csv_file, mode='w', encoding='utf-8') as file:
            file.write("user_id,request_time,processing_time\n")
            file.write("user1,0.1,not_a_float\n") # 不正なデータ

        self.missing_column_csv_file = "missing_column_requests.csv"
        with open(self.missing_column_csv_file, mode='w', encoding='utf-8') as file:
            file.write("user_id,request_time\n") # カラム不足
            file.write("user1,0.1\n")


    def tearDown(self):
        # テストファイルを削除
        if os.path.exists(self.test_csv_file):
            os.remove(self.test_csv_file)
        if os.path.exists(self.empty_csv_file):
            os.remove(self.empty_csv_file)
        if os.path.exists(self.malformed_csv_file):
            os.remove(self.malformed_csv_file)
        if os.path.exists(self.missing_column_csv_file):
            os.remove(self.missing_column_csv_file)


    def test_parse_valid_csv(self):
        requests = parse_csv(self.test_csv_file)
        self.assertEqual(len(requests), 3)
        self.assertIsInstance(requests[0], Request)
        self.assertEqual(requests[0].user_id, "user1")
        self.assertEqual(requests[0].request_time, 0.1)
        self.assertEqual(requests[0].processing_time, 1.0)
        self.assertEqual(requests[1].user_id, "user2")
        self.assertEqual(requests[2].processing_time, 0.5)

    def test_parse_sample_csv(self):
        # 既存のサンプルCSVファイルでテスト
        requests = parse_csv("sample_requests.csv")
        self.assertEqual(len(requests), 5)
        self.assertEqual(requests[0].user_id, "user_a")
        self.assertEqual(requests[0].request_time, 0.0)
        self.assertEqual(requests[0].processing_time, 5.0)
        self.assertEqual(requests[4].user_id, "user_e")
        self.assertEqual(requests[4].request_time, 2.0)
        self.assertEqual(requests[4].processing_time, 1.0)


    def test_parse_empty_csv(self):
        requests = parse_csv(self.empty_csv_file)
        self.assertEqual(len(requests), 0)

    def test_parse_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            parse_csv("non_existent_file.csv")

    def test_parse_malformed_csv(self):
        with self.assertRaises(ValueError): # 内部でValueErrorが発生し、それが伝播する
            parse_csv(self.malformed_csv_file)

    def test_parse_missing_column_csv(self):
        with self.assertRaises(KeyError): # 内部でKeyErrorが発生し、それが伝播する
            parse_csv(self.missing_column_csv_file)


if __name__ == '__main__':
    unittest.main()
