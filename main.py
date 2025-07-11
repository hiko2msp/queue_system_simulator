import argparse
import datetime  # datetime をインポート

# import json # 結果をJSON形式で出力するため (今回は標準出力のみ)
import numpy as np  # main関数内で statistics をインポートするために必要

from src.csv_parser import parse_csv
from src.simulator import Simulator
from src.statistics import calculate_simulation_statistics

# scripts/generate_sample_data.py と同じ基準時刻を使用
SIMULATION_START_TIME = datetime.datetime(2023, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)


def main():
    parser = argparse.ArgumentParser(description="システムアクセスシミュレーター")
    parser.add_argument("csv_file", help="リクエストデータが含まれるCSVファイルへのパス")
    parser.add_argument("-w", "--num_workers", type=int, default=1, help="ワーカーの数 (デフォルト: 1)")
    parser.add_argument("-q", "--queue_size", type=int, default=None, help="キューの最大サイズ (デフォルト: 無制限)")
    # TODO: 将来の拡張: アドミッションコントロール戦略を選択する引数を追加
    # parser.add_argument("-s", "--admission_strategy", type=str, default="simple_rejection", choices=["simple_rejection", "drop_oldest"], help="アドミッションコントロール戦略")
    # TODO: 将来の拡張: 複数のキュータイプや設定を引数で指定できるようにする (例: --queues "priority:high_q_size=10,normal:low_q_size=100")

    args = parser.parse_args()

    print(f"シミュレーション開始: {args.csv_file}")
    print(
        f"ワーカー数: {args.num_workers}, キュー最大サイズ: {args.queue_size if args.queue_size is not None else '無制限'}"
    )
    # if hasattr(args, "admission_strategy"): # 将来的に追加された場合
    #     print(f"アドミッション戦略: {args.admission_strategy}")

    try:
        # csv_parser は request.request_time に datetime オブジェクトを設定する
        parsed_requests = parse_csv(args.csv_file)
    except FileNotFoundError:
        print(f"エラー: CSVファイル '{args.csv_file}' が見つかりません。")
        return
    except (KeyError, ValueError) as e:
        print(f"エラー: CSVファイルのフォーマットが正しくありません。詳細: {e}")
        return

    if not parsed_requests:
        print("CSVファイルにリクエストデータが含まれていません。シミュレーションを終了します。")
        # statistics が numpy を使うので、ここで import しておく
        # (実際には calculate_simulation_statistics が呼ばれる際に statistics モジュール内で import される)
        return

    # Requestオブジェクトのリストを準備し、sim_arrival_time を計算して設定
    requests_for_simulator = []
    for req_data in parsed_requests:
        if req_data.request_time < SIMULATION_START_TIME:
            # このケースは通常発生しないはず (generate_sample_data.py が SIMULATION_START_TIME 以降の時刻を生成するため)
            # 念のため警告
            print(
                f"警告: リクエスト {req_data.user_id} の request_time ({req_data.request_time}) "
                f"がシミュレーション開始時刻 ({SIMULATION_START_TIME}) より前です。相対時間は負になります。"
            )

        # sim_arrival_time を計算 (SIMULATION_START_TIME からの経過秒数)
        # req_data は Request 型のインスタンスなので、直接属性を設定できる
        req_data.sim_arrival_time = (req_data.request_time - SIMULATION_START_TIME).total_seconds()
        requests_for_simulator.append(req_data)

    # デバッグ用: sim_arrival_time が正しく設定されているか確認 (必要であればコメント解除)
    # for r_idx, r_val in enumerate(requests_for_simulator):
    #     if r_idx < 5: # 最初の5件だけ表示
    #         print(f"Debug: User: {r_val.user_id}, ISO: {r_val.request_time}, SimArrival: {r_val.sim_arrival_time:.6f}, ProcTime: {r_val.processing_time}")

    simulator = Simulator(
        requests=requests_for_simulator,  # sim_arrival_time が設定されたリストを渡す
        num_workers=args.num_workers,
        queue_max_size=args.queue_size,
    )

    completed_tasks = simulator.run()

    # デバッグ用の出力はコメントアウト
    # print("\n--- 全完了タスク (デバッグ用) ---")
    # for task in completed_tasks:
    #     status = "Processed" if task.finish_processing_time_by_worker != -1 else "Rejected"
    #     q_time_val = np.nan
    #     if status == "Processed" and hasattr(task, 'start_processing_time_by_worker') and hasattr(task, 'arrival_time_in_queue'):
    #         if task.start_processing_time_by_worker >= task.arrival_time_in_queue:
    #             q_time_val = task.start_processing_time_by_worker - task.arrival_time_in_queue

    #     q_time_str = f"{q_time_val:.2f}" if not np.isnan(q_time_val) else "N/A"

    #     print(
    #         f"ID: {task.user_id}, ReqTime: {task.request_time:.2f}, "
    #         f"ArrTimeQ: {task.arrival_time_in_queue:.2f}, StartProc: {task.start_processing_time_by_worker:.2f}, "
    #         f"FinishProc: {task.finish_processing_time_by_worker:.2f}, ProcTime: {task.processing_time:.2f}, "
    #         f"QTime: {q_time_str}, Status: {status}"
    #     )
    # print("-----------------------------\n")

    statistics = calculate_simulation_statistics(completed_tasks)

    print("\n--- シミュレーション統計 ---")

    print(f"  総リクエスト数 (入力): {len(parsed_requests)}")  # 変更: requests -> parsed_requests
    print(f"  処理完了リクエスト数: {statistics['total_requests_processed']}")
    print(f"  リジェクトリクエスト数: {statistics['total_requests_rejected']}")

    avg_q_time = statistics["average_queuing_time"]
    print(f"  平均キューイング時間: {avg_q_time:.4f}" if not np.isnan(avg_q_time) else "  平均キューイング時間: N/A")

    p50 = statistics["p50"]
    print(f"  キューイング時間 P50: {p50:.4f}" if not np.isnan(p50) else "  キューイング時間 P50: N/A")

    p75 = statistics["p75"]
    print(f"  キューイング時間 P75: {p75:.4f}" if not np.isnan(p75) else "  キューイング時間 P75: N/A")

    p90 = statistics["p90"]
    print(f"  キューイング時間 P90: {p90:.4f}" if not np.isnan(p90) else "  キューイング時間 P90: N/A")

    p99 = statistics["p99"]
    print(f"  キューイング時間 P99: {p99:.4f}" if not np.isnan(p99) else "  キューイング時間 P99: N/A")

    if "api_usage_counts" in statistics:
        print("\n  --- API使用回数 ---")
        api_counts = statistics["api_usage_counts"]
        if isinstance(api_counts, dict):  # 型チェック
            if not api_counts:
                print("    API使用実績なし")
            else:
                for api_id_key, count in sorted(api_counts.items()):  # キーでソートして表示
                    # api_id_key は "api_X" の形式を想定
                    print(f"    {api_id_key}: {count} 回")
        else:
            print(f"    API使用回数データ形式エラー: {type(api_counts)}")

    print("--------------------------\n")


if __name__ == "__main__":
    main()
