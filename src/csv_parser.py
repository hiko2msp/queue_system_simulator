import csv
from src.data_model import Request
from typing import List

def parse_csv(file_path: str) -> List[Request]:
    """
    指定されたパスのCSVファイルをパースし、Requestオブジェクトのリストを返します。

    CSVファイルは以下のヘッダーを持つことを期待します:
    - user_id (str): ユーザー識別子
    - request_time (float): リクエスト到着時刻
    - processing_time (float): リクエスト処理時間

    Args:
        file_path (str): パースするCSVファイルのパス。

    Returns:
        List[Request]: パースされたRequestオブジェクトのリスト。

    Raises:
        FileNotFoundError: 指定されたファイルパスが見つからない場合。
        KeyError: CSVヘッダーに必要なカラム（user_id, request_time, processing_time）が
                  見つからない場合。
        ValueError: request_time または processing_time をfloatに変換できない場合。
        Exception: その他の予期せぬ読み込みエラーが発生した場合。
    """
    requests: List[Request] = []
    try:
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames: # 空のCSVファイルやヘッダーのみのファイルの場合
                return requests # 空のリストを返す

            # 期待されるカラムの存在チェック
            expected_columns = ['user_id', 'request_time', 'processing_time']
            for col in expected_columns:
                if col not in reader.fieldnames:
                    # print(f"エラー: CSVファイルに期待されるカラム '{col}' が見つかりません。ヘッダー: {reader.fieldnames}")
                    raise KeyError(f"CSVファイルに期待されるカラム '{col}' が見つかりません。")

            for row_number, row in enumerate(reader, start=2): # start=2 (ヘッダー行の次から)
                try:
                    request = Request(
                        user_id=row['user_id'],
                        request_time=float(row['request_time']),
                        processing_time=float(row['processing_time'])
                    )
                    requests.append(request)
                except KeyError as e: # これは通常、上記のヘッダーチェックで捕捉されるはず
                    # print(f"エラー: CSVファイル(行 {row_number})に期待されるカラム {e} が見つかりません。")
                    raise
                except ValueError as e:
                    # print(f"エラー: CSVデータ(行 {row_number})の型変換に失敗しました。行: {row}, エラー: {e}")
                    raise ValueError(f"CSVデータ(行 {row_number})の型変換に失敗しました: {e}. 行データ: {row}")
    except FileNotFoundError:
        # print(f"エラー: ファイル '{file_path}' が見つかりません。")
        raise
    except Exception as e: # KeyError, ValueError 以外で、openやDictReaderで発生しうるエラー
        # print(f"エラー: CSVファイルの読み込み中に予期せぬエラーが発生しました。エラー: {e}")
        raise
    return requests
