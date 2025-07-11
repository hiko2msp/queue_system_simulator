import csv
import datetime  # datetime をインポート

from src.data_model import Request  # RequestData に変更予定だが、ひとまずそのまま


def parse_csv(file_path: str) -> list[Request]:
    """
    指定されたパスのCSVファイルをパースし、Requestオブジェクトのリストを返します。

    CSVファイルは以下のヘッダーを持つことを期待します:
    - user_id (str): ユーザー識別子
    - request_time (str): リクエスト到着時刻 (ISO 8601形式)
    - processing_time (float): リクエスト処理時間

    Args:
        file_path (str): パースするCSVファイルのパス。

    Returns:
        List[Request]: パースされたRequestオブジェクトのリスト。

    Raises:
        FileNotFoundError: 指定されたファイルパスが見つからない場合。
        KeyError: CSVヘッダーに必要なカラム（user_id, request_time, processing_time）が
                  見つからない場合。
        ValueError: request_time をdatetimeに、または processing_time をfloatに変換できない場合。
        Exception: その他の予期せぬ読み込みエラーが発生した場合。
    """
    requests: list[Request] = []
    try:
        with open(file_path, encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:  # 空のCSVファイルやヘッダーのみのファイルの場合
                return requests  # 空のリストを返す

            # 期待されるカラムの存在チェック
            expected_columns = ["user_id", "request_time", "processing_time"]
            for col in expected_columns:
                if col not in reader.fieldnames:
                    raise KeyError(f"CSVファイルに期待されるカラム '{col}' が見つかりません。")

            for row_number, row in enumerate(reader, start=2):  # start=2 (ヘッダー行の次から)
                try:
                    # request_time を datetime オブジェクトに変換
                    request_time_str = row["request_time"]
                    # fromisoformat は Python 3.11+ で 'Z' を直接扱える
                    # それ以前のバージョンでは 'Z' を '+00:00' に置換するか、
                    # 'Z' を取り除いて naive datetime とし、あとで localize する必要がある。
                    # generate_sample_data.py が 'Z' を付加するため、それに対応。
                    if request_time_str.endswith("Z"):
                        # Python 3.7+ で 'Z' を扱うため、置換する
                        dt_obj_naive = datetime.datetime.fromisoformat(request_time_str.replace("Z", ""))
                        request_time_dt = dt_obj_naive.replace(tzinfo=datetime.UTC)
                    else:
                        # 'Z' がない場合、タイムゾーン情報なしのISOフォーマットとしてパース
                        # 必要に応じてエラーとするか、デフォルトタイムゾーンを割り当てる
                        # ここでは、そのままパースし、naive datetime とする
                        # 実際には入力フォーマットの仕様に依存
                        request_time_dt = datetime.datetime.fromisoformat(request_time_str)

                    request = Request(
                        user_id=row["user_id"],
                        request_time=request_time_dt,  # datetimeオブジェクトを渡す
                        processing_time=float(row["processing_time"]),
                    )
                    requests.append(request)
                except KeyError:
                    raise
                except ValueError as e:
                    raise ValueError(f"CSVデータ(行 {row_number})の型変換に失敗しました: {e}. 行データ: {row}")
    except FileNotFoundError:
        raise
    except Exception:
        raise
    return requests
