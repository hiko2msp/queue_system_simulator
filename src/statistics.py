from typing import List, Dict, Union
import numpy as np
from src.data_model import Request

def calculate_queuing_times(processed_requests: List[Request]) -> List[float]:
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
    queuing_times: List[float] = []
    for req in processed_requests:
        # start_processing_time_by_worker と arrival_time_in_queue が適切に記録されていることを確認
        if hasattr(req, 'start_processing_time_by_worker') and req.start_processing_time_by_worker >= 0 and \
           hasattr(req, 'arrival_time_in_queue') and req.arrival_time_in_queue >= 0:

            if req.start_processing_time_by_worker >= req.arrival_time_in_queue:
                queuing_time = req.start_processing_time_by_worker - req.arrival_time_in_queue
                queuing_times.append(queuing_time)
            else:
                # この状態は通常、シミュレーションロジックが正しければ発生しないはずです。
                # (処理開始がキュー到着より前になることはないため)
                # ログ出力やエラーハンドリングを検討することもできます。
                # print(f"Warning: Request {req.user_id} has start_processing_time {req.start_processing_time_by_worker} < arrival_time_in_queue {req.arrival_time_in_queue}")
                pass # このリクエストのキューイング時間は計算しない
    return queuing_times

def calculate_percentiles(data: List[float], percentiles_to_calculate: List[int]) -> Dict[str, float]:
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

    results: Dict[str, float] = {}
    for p_val in percentiles_to_calculate:
        if not (0 <= p_val <= 100):
            raise ValueError(f"Percentile value must be between 0 and 100, got {p_val}")
        # numpy.percentileは線形補間を使用します
        results[f"p{p_val}"] = float(np.percentile(np.array(data), p_val))
    return results

def calculate_simulation_statistics(completed_requests: List[Request]) -> Dict[str, Union[float, int]]:
    """
    シミュレーションの完了結果（処理済みおよびリジェクトされたリクエストを含む）から
    主要な統計情報を計算します。

    計算される統計情報:
    - total_requests_processed (int): 処理が正常に完了したリクエストの総数。
    - total_requests_rejected (int): キュー満杯などの理由でリジェクトされたリクエストの総数。
    - average_queuing_time (float): 処理されたリクエストの平均キューイング時間。処理済みリクエストがない場合は np.nan。
    - p50 (float): キューイング時間の50パーセンタイル（中央値）。処理済みリクエストがない場合は np.nan。
    - p75 (float): キューイング時間の75パーセンタイル。処理済みリクエストがない場合は np.nan。
    - p90 (float): キューイング時間の90パーセンタイル。処理済みリクエストがない場合は np.nan。
    - p99 (float): キューイング時間の99パーセンタイル。処理済みリクエストがない場合は np.nan。

    Args:
        completed_requests (List[Request]): シミュレーションで処理が完了した、
                                            またはリジェクトされた全てのRequestオブジェクトのリスト。

    Returns:
        Dict[str, Union[float, int]]: 計算された統計情報を含む辞書。
    """
    stats: Dict[str, Union[float, int]] = {}

    processed_requests = [req for req in completed_requests if req.finish_processing_time_by_worker != -1]
    rejected_requests = [req for req in completed_requests if req.finish_processing_time_by_worker == -1]

    stats["total_requests_processed"] = len(processed_requests)
    stats["total_requests_rejected"] = len(rejected_requests)

    queuing_times = calculate_queuing_times(processed_requests) # ここでは処理されたリクエストのみ渡す

    if queuing_times: # queuing_times が空でない場合
        stats["average_queuing_time"] = float(np.mean(queuing_times))
        percentile_values_to_calc = [50, 75, 90, 99]
        percentile_results = calculate_percentiles(queuing_times, percentile_values_to_calc)
        stats.update(percentile_results)
    else: # queuing_times が空の場合 (処理されたリクエストがないか、キューイング時間が計算できなかった場合)
        stats["average_queuing_time"] = np.nan
        percentile_values_to_calc = [50, 75, 90, 99]
        percentile_results = calculate_percentiles([], percentile_values_to_calc) # nanが入る
        stats.update(percentile_results)

    # NaNを文字列 "NaN" に変換するかどうかは出力時に検討。ここではfloatのまま。
    return stats
