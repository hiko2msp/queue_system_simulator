import datetime
from dataclasses import dataclass


@dataclass
class Request:
    """
    シミュレーション内の単一のリクエストを表すデータクラス。

    Attributes:
        user_id (str): リクエストを発行したユーザーの識別子。
        request_time (datetime.datetime): リクエストがシステムに到着した絶対時刻 (aware datetime object)。
                                         CSVからISO 8601形式で読み込まれる。
        processing_time (float): このリクエストの処理に要する時間（秒単位）。

        sim_arrival_time (float): シミュレーション開始時刻を0とした場合の、リクエスト到着相対時刻（秒）。
                                  main.pyで request_time から計算されて設定される。
                                  シミュレータ内部ではこの時刻を使用する。

        # 以下の時刻フィールドも、シミュレーション内部での相対時間やイベント発生時刻を示すために
        # float (シミュレーション開始からの経過秒数など) で表現される。
        arrival_time_in_queue (float): リクエストがキューに到着したシミュレーション相対時刻。
                                      シミュレータによって設定される。
        start_processing_time_by_worker (float): ワーカーがこのリクエストの処理を開始したシミュレーション相対時刻。
                                                ワーカーによって設定される。
        finish_processing_time_by_worker (float): ワーカーがこのリクエストの処理を完了したシミュレーション相対時刻。
                                                 ワーカーによって設定される。
        used_api_id (Optional[int]): 処理に使用されたAPIのID (1からN)。
    """

    user_id: str
    request_time: datetime.datetime  # ISO8601からパースされた aware datetime
    processing_time: float  # 単位は秒

    # シミュレーション内部で使用する相対時刻 (シミュレーション開始からの経過秒数)
    # main.py で request_time から計算して設定する
    sim_arrival_time: float = 0.0

    arrival_time_in_queue: float = 0.0
    start_processing_time_by_worker: float = 0.0
    finish_processing_time_by_worker: float = 0.0
    used_api_id: int | None = None
