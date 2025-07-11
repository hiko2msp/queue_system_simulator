import pandas as pd
import matplotlib.pyplot as plt
import os

# ログファイル名と出力ディレクトリ
LOG_FILE = "simulator_log.csv"
OUTPUT_DIR = "graphs"
DEFAULT_QUEUE_NAMES = ["priority", "normal"] # ログに出力されるキュー名に合わせてください

def plot_graphs(log_file: str = LOG_FILE, output_dir: str = OUTPUT_DIR, queue_names: list[str] = None):
    """
    シミュレーターのログファイルを読み込み、各種メトリクスの時系列グラフを生成して保存します。

    Args:
        log_file (str): 入力となるCSVログファイルのパス。
        output_dir (str): 生成されたグラフ画像を保存するディレクトリ。
        queue_names (list[str], optional): グラフを生成するキュー名のリスト。
                                           Noneの場合は DEFAULT_QUEUE_NAMES を使用。
    """
    if queue_names is None:
        queue_names = DEFAULT_QUEUE_NAMES

    try:
        df = pd.read_csv(log_file)
    except FileNotFoundError:
        print(f"エラー: ログファイル '{log_file}' が見つかりません。")
        return
    except Exception as e:
        print(f"エラー: ログファイル '{log_file}' の読み込み中にエラーが発生しました: {e}")
        return

    if df.empty:
        print(f"ログファイル '{log_file}' は空です。グラフは生成されません。")
        return

    # 出力ディレクトリが存在しない場合は作成
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 描画するメトリクスとY軸ラベルのマッピング
    metrics_to_plot = {
        "TasksInQueue": "Queue Length (Tasks)",
        "CumulativeRejected": "Cumulative Rejected Tasks",
        "CumulativeSucceeded": "Cumulative Succeeded Tasks",
        "CumulativeApiErrors": "Cumulative API Errors",
        "ApiThroughput (req/min)": "API Throughput (requests/min)",
    }

    # Timestamp (min) を数値型に変換 (エラーがあればNaNにし、その後削除)
    df["Timestamp (min)"] = pd.to_numeric(df["Timestamp (min)"], errors='coerce')
    df.dropna(subset=["Timestamp (min)"], inplace=True)


    for metric_col, y_label in metrics_to_plot.items():
        plt.figure(figsize=(12, 6))
        for queue_name in queue_names:
            queue_df = df[df["QueueName"] == queue_name]
            if not queue_df.empty:
                # タイムスタンプでソートしてからプロット
                queue_df = queue_df.sort_values(by="Timestamp (min)")
                plt.plot(queue_df["Timestamp (min)"], queue_df[metric_col], label=f"{queue_name} Queue")
            else:
                print(f"警告: キュー名 '{queue_name}' のデータがログファイルに存在しません。")

        plt.xlabel("Time (minutes)")
        plt.ylabel(y_label)
        plt.title(f"{y_label} Over Time")
        plt.legend()
        plt.grid(True)

        # ファイル名に使えない文字を置換
        safe_metric_name = metric_col.replace("/", "_").replace("(", "").replace(")", "").replace(" ", "")
        plot_filename = os.path.join(output_dir, f"{safe_metric_name}_vs_time.png")
        try:
            plt.savefig(plot_filename)
            print(f"グラフを保存しました: {plot_filename}")
        except Exception as e:
            print(f"エラー: グラフ '{plot_filename}' の保存中にエラーが発生しました: {e}")
        plt.close()

if __name__ == "__main__":
    # Simulatorが simulator_log.csv を出力した後、このスクリプトを実行
    plot_graphs()
    print(f"グラフ生成が完了しました。'{OUTPUT_DIR}' ディレクトリを確認してください。")
