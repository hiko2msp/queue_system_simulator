from collections import defaultdict  # defaultdict をインポート

import numpy as np

from config.settings import NUM_EXTERNAL_APIS  # NUM_EXTERNAL_APIS をインポート
from src.data_model import Request


def calculate_queuing_times(processed_requests: list[Request]) -> list[float]:
    """
    処理済みリクエストのリストから、各リクエストのキューイング時間を計算します。

    キューイング時間は、リクエストがキューに到着してからワーカーによって処理が開始されるまでの時間です。
    この関数は、`finish_processing_time_by_worker` が -1 でない（つまりリジェクトされていない）
    リクエストのみを対象とすることを前提としています。

    Args:
        processed_requests (List[Request]): 処理が完了したRequestオブジェクトのリスト。
                                            リジェクトされたリクエストは含まない想定。

    Returns:
        List[float]: 各処理済みリクエストのキューイング時間のリスト。
                     キューイング時間が計算できないリクエストは除外されます。
    """
    queuing_times: list[float] = []
    for req in processed_requests:
        # start_processing_time_by_worker と arrival_time_in_queue が適切に記録されていることを確認
        if (
            hasattr(req, "start_processing_time_by_worker")
            and req.start_processing_time_by_worker >= 0
            and hasattr(req, "arrival_time_in_queue")
            and req.arrival_time_in_queue >= 0
        ):
            if req.start_processing_time_by_worker >= req.arrival_time_in_queue:
                queuing_time = req.start_processing_time_by_worker - req.arrival_time_in_queue
                queuing_times.append(queuing_time)
            else:
                # この状態は通常、シミュレーションロジックが正しければ発生しないはずです。
                # (処理開始がキュー到着より前になることはないため)
                # ログ出力やエラーハンドリングを検討することもできます。
                # print(f"Warning: Request {req.user_id} has start_processing_time {req.start_processing_time_by_worker} < arrival_time_in_queue {req.arrival_time_in_queue}")
                pass  # このリクエストのキューイング時間は計算しない
    return queuing_times


def calculate_percentiles(data: list[float], percentiles_to_calculate: list[int]) -> dict[str, float]:
    """
    数値データのリストから、指定されたパーセンタイルの値を計算します。

    Args:
        data (List[float]): パーセンタイル計算の対象となる数値データのリスト。
        percentiles_to_calculate (List[int]): 計算するパーセンタイルの値のリスト (例: [50, 75, 90])。
                                             各値は0から100の間である必要があります。

    Returns:
        Dict[str, float]: 計算されたパーセンタイル値を格納した辞書。
                          キーは "pXX" (例: "p50")、値は対応するパーセンタイル値。
                          入力データが空の場合、全ての値は np.nan になります。

    Raises:
        ValueError: `percentiles_to_calculate` に0-100の範囲外の値が含まれている場合。
    """
    if not data:
        return {f"p{p}": np.nan for p in percentiles_to_calculate}

    results: dict[str, float] = {}
    for p_val in percentiles_to_calculate:
        if not (0 <= p_val <= 100):
            raise ValueError(f"Percentile value must be between 0 and 100, got {p_val}")
        # numpy.percentileは線形補間を使用します
        results[f"p{p_val}"] = float(np.percentile(np.array(data), p_val))
    return results


from typing import Any, Dict # Dict をインポート

def calculate_simulation_statistics(
    completed_requests: list[Request],
    queue_counts: dict[str, int] | None = None # 新しい引数
) -> dict[str, Any]:
    """
    シミュレーションの完了結果（処理済みおよびリジェクトされたリクエストを含む）と
    キューの統計情報から主要な統計情報を計算します。

    計算される統計情報:
    - total_requests_processed (int): 処理が正常に完了したリクエストの総数。
    - total_requests_rejected (int): キュー満杯などの理由でリジェクトされたリクエストの総数。
    - average_queuing_time (float): 処理されたリクエストの平均キューイング時間。
    - p50, p75, p90, p99 (float): キューイング時間の各パーセンタイル。
    - api_usage_counts (Dict[str, int]): 各APIの使用回数。
    - priority_queue_enqueued_total (int): 優先キューにエンキューされたリクエスト総数。
    - normal_queue_enqueued_total (int): 通常キューにエンキューされたリクエスト総数。

    Args:
        completed_requests (List[Request]): 処理完了またはリジェクトされたリクエストのリスト。
        queue_counts (Optional[Dict[str, int]]): キューに関するカウント情報。
            例: {"priority_enqueued": count1, "normal_enqueued": count2}

    Returns:
        Dict[str, Any]: 計算された統計情報を含む辞書。
    """
    stats: dict[str, Any] = {}

    processed_requests = [req for req in completed_requests if req.finish_processing_time_by_worker != -1]
    rejected_requests = [req for req in completed_requests if req.finish_processing_time_by_worker == -1]

    stats["total_requests_processed"] = len(processed_requests)
    stats["total_requests_rejected"] = len(rejected_requests)

    queuing_times = calculate_queuing_times(processed_requests)  # ここでは処理されたリクエストのみ渡す

    if queuing_times:  # queuing_times が空でない場合
        stats["average_queuing_time"] = float(np.mean(queuing_times))
        percentile_values_to_calc = [50, 75, 90, 99]
        percentile_results = calculate_percentiles(queuing_times, percentile_values_to_calc)
        stats.update(percentile_results)
    else:  # queuing_times が空の場合 (処理されたリクエストがないか、キューイング時間が計算できなかった場合)
        stats["average_queuing_time"] = np.nan
        percentile_values_to_calc = [50, 75, 90, 99]
        percentile_results = calculate_percentiles([], percentile_values_to_calc)  # nanが入る
        stats.update(percentile_results)

    # NaNを文字列 "NaN" に変換するかどうかは出力時に検討。ここではfloatのまま。

    # API使用回数の集計
    api_usage_counts: dict[str, int] = defaultdict(int)
    for i in range(1, NUM_EXTERNAL_APIS + 1):  # 存在しうる全てのAPI IDをキーとして初期化
        api_usage_counts[f"api_{i}"] = 0

    for req in processed_requests:
        if req.used_api_id is not None:
            api_key = f"api_{req.used_api_id}"
            if api_key in api_usage_counts:  # settingsで定義された範囲内のIDか確認
                api_usage_counts[api_key] += 1
            else:
                # settingsで定義された範囲外のIDが記録されている場合 (通常は起こりえない)
                print(f"Warning: Request {req.user_id} used an unexpected API ID: {req.used_api_id}")
                # 未知のAPI IDとしてカウントすることも可能
                # api_usage_counts[f"api_unknown_{req.used_api_id}"] = api_usage_counts.get(f"api_unknown_{req.used_api_id}", 0) + 1

    stats["api_usage_counts"] = dict(api_usage_counts)  # defaultdictを通常のdictに変換して返す

    # キュー関連の統計情報を追加
    if queue_counts:
        stats["priority_queue_enqueued_total"] = queue_counts.get("priority_enqueued", 0)
        stats["normal_queue_enqueued_total"] = queue_counts.get("normal_enqueued", 0)
    else: # queue_counts が None の場合や、キーが存在しない場合のデフォルト値
        stats["priority_queue_enqueued_total"] = 0
        stats["normal_queue_enqueued_total"] = 0
        # もし simulator が PriorityQueueStrategy を使っていない場合、
        # これらの統計は意味を持たないかもしれないので、0 または np.nan とするかは要検討。
        # ここでは、渡されなければ0とする。

    return stats
