from dataclasses import dataclass

@dataclass
class Request:
    """
    シミュレーション内の単一のリクエストを表すデータクラス。

    Attributes:
        user_id (str): リクエストを発行したユーザーの識別子。
        request_time (float): リクエストがシステムに到着したシミュレーション時刻。
        processing_time (float): このリクエストの処理に要する時間。
        arrival_time_in_queue (float): リクエストがキューに到着したシミュレーション時刻。
                                      シミュレータによって設定される。
        start_processing_time_by_worker (float): ワーカーがこのリクエストの処理を開始したシミュレーション時刻。
                                                ワーカーによって設定される。
        finish_processing_time_by_worker (float): ワーカーがこのリクエストの処理を完了したシミュレーション時刻。
                                                 ワーカーによって設定される。リジェクトされた場合は -1 など特別な値が設定されることがある。
    """
    user_id: str
    request_time: float
    processing_time: float
    arrival_time_in_queue: float = 0.0
    start_processing_time_by_worker: float = 0.0
    finish_processing_time_by_worker: float = 0.0
