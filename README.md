# システムアクセスシミュレーター

## 1. 概要

このプロジェクトは、特定のシステムへのアクセスをシミュレートし、その挙動を可視化するためのPython製シミュレーターです。
非同期APIを模しており、リクエストハンドラがタスクをキューに積み、ワーカーがそれを処理するモデルに基づいています。

シミュレーターは以下の機能を提供します:
- CSVファイルからリクエストデータ（ユーザーID、リクエスト時刻、処理時間）を読み込みます。
- 指定された数のワーカーとキューサイズでシステムの動作をシミュレートします。
- シミュレーション結果として、タスクのキューイング時間に関する統計量（平均、P50, P75, P90, P99パーセンタイルなど）を出力します。

## 2. 主要コンポーネント

### 2.1. `src/data_model.py`
-   **`Request`**: シミュレーション内の単一のリクエストを表すデータクラス。リクエストID、到着時刻、処理時間、およびシミュレーション中に記録される各種タイムスタンプ（キュー到着時刻、処理開始/終了時刻）を保持します。

### 2.2. `src/csv_parser.py`
-   **`parse_csv(file_path: str) -> List[Request]`**: 指定されたCSVファイルを読み込み、`Request`オブジェクトのリストに変換します。

### 2.3. `src/queue_manager.py`
-   **`FifoQueue[T]`**: FIFO（先入れ先出し）方式のジェネリックキュークラス。オプションで最大サイズを設定でき、アドミッションコントロールの基本的な機能（満杯ならエンキューしない）を提供します。

### 2.4. `src/worker.py`
-   **`Worker`**: タスクキューから`Request`を取得し、指定された処理時間だけ処理をシミュレートするクラス。各ワーカーは同時に1つのタスクのみを処理します。

### 2.5. `src/simulator.py`
-   **`Simulator`**: シミュレーション全体の制御を行うコアクラス。リクエストの到着イベント、ワーカーによるタスク処理イベントを管理し、イベントドリブンで時間を進めます。入力されたリクエストリスト、ワーカー数、キュー設定に基づいてシミュレーションを実行し、完了（またはリジェクト）したタスクのリストを返します。

### 2.6. `src/statistics.py`
-   **`calculate_queuing_times(processed_requests: List[Request]) -> List[float]`**: 処理済みリクエストのリストから、各リクエストのキューイング時間（キュー到着から処理開始までの時間）を計算します。
-   **`calculate_percentiles(data: List[float], percentiles_to_calculate: List[int]) -> Dict[str, float]`**: 数値データのリストから指定されたパーセンタイル値を計算します。
-   **`calculate_simulation_statistics(completed_requests: List[Request]) -> Dict[str, Union[float, int]]`**: シミュレーション結果（完了/リジェクトされた全タスク）から、総処理数、総リジェクト数、平均キューイング時間、およびキューイング時間の各パーセンタイル値などの統計情報を計算します。

### 2.7. `main.py`
-   コマンドラインインターフェースを提供するエントリーポイントスクリプト。
-   CSVファイルのパス、ワーカー数、キューサイズを引数として受け取ります。
-   各コンポーネントを呼び出してシミュレーションを実行し、結果の統計情報を標準出力に表示します。

## 3. 基本的な使い方

### 3.1. 必要なライブラリのインストール
`numpy`ライブラリが必要です。`requirements.txt` を使ってインストールできます。
```bash
pip install -r requirements.txt
```

### 3.2. サンプルデータの生成 (オプション)
テストやデモンストレーション用にサンプルデータを生成するスクリプトが用意されています。

```bash
python scripts/generate_sample_data.py <user_id>
```
**引数:**
- `<user_id>`: 生成されるデータのユーザーID (例: `test_user`, `user123`)。

**実行例:**
```bash
python scripts/generate_sample_data.py my_test_user
```
これにより、カレントディレクトリに `sample_data_my_test_user.csv` という名前のCSVファイルが生成されます。
このファイルには、指定されたユーザーIDで、ランダムなリクエスト時刻（特定の日付内で時間はランダム）と正規分布に従う処理時間を持つ10〜40件のリクエストデータが含まれます。

**生成されるCSVのフォーマット例:**
```csv
user_id,request_time,processing_time
my_test_user,1698278400.0,18
my_test_user,1698307200.0,22
...
```
ここで `request_time` はUnixタイムスタンプ (float)、`processing_time` はミリ秒単位の処理時間 (int) です。

### 3.3. シミュレーションの実行
ルートディレクトリにある `main.py` を使用してシミュレーションを実行します。

```bash
python main.py <csv_file_path> [options]
```

**引数:**
-   `csv_file_path`: リクエストデータが含まれるCSVファイルへのパス (必須)。
    CSVファイルは以下のヘッダーとデータ形式である必要があります:
    ```csv
    user_id,request_time,processing_time
    user_a,0.0,5.0
    user_b,0.5,3.0
    ...
    ```
-   `-w <num_workers>`, `--num_workers <num_workers>`: ワーカーの数 (オプション, デフォルト: 1)。
-   `-q <queue_size>`, `--queue_size <queue_size>`: キューの最大サイズ (オプション, デフォルト: 無制限)。

**実行例:**
```bash
# サンプルCSVをワーカー2台、キューサイズ10で実行
python main.py sample_requests.csv -w 2 -q 10

# サンプルCSVをワーカー1台、キュー無制限で実行
python main.py sample_requests.csv -w 1

# 生成したサンプルデータで実行
python scripts/generate_sample_data.py example_user
python main.py sample_data_example_user.csv -w 1
```

**期待される出力例 (統計情報):**
```
シミュレーション開始: sample_data_example_user.csv
ワーカー数: 1, キュー最大サイズ: 無制限

--- シミュレーション統計 ---
  総リクエスト数 (入力): XX
  処理完了リクエスト数: XX
  リジェクトリクエスト数: X
  平均キューイング時間: X.XXXX
  キューイング時間 P50: X.XXXX
  キューイング時間 P75: X.XXXX
  キューイング時間 P90: X.XXXX
  キューイング時間 P99: X.XXXX
--------------------------
```
(XX は実際の実行結果によって変わります)


## 4. ディレクトリ構造

```
.
├── main.py                 # メイン実行スクリプト
├── sample_requests.csv     # サンプル入力データ
├── requirements.txt        # 依存ライブラリ
├── scripts/                # スクリプトディレクトリ
│   └── generate_sample_data.py # サンプルデータ生成スクリプト
├── src/                    # ソースコードディレクトリ
│   ├── __init__.py
│   ├── csv_parser.py       # CSVパース処理
│   ├── data_model.py       # Requestデータクラス定義
│   ├── queue_manager.py    # FifoQueueクラス定義
│   ├── simulator.py        # Simulatorコアロジック
│   ├── statistics.py       # 統計計算処理
│   └── worker.py           # Workerクラス定義
└── tests/                  # テストコードディレクトリ
    ├── __init__.py
    ├── test_csv_parser.py
    ├── test_data_model.py
    ├── test_queue_manager.py
    ├── test_simulator.py
    ├── test_statistics.py
    └── test_worker.py
```

## 5. 将来の拡張（TODOコメントより）
-   複数のキュータイプ（例: 優先度キュー）のサポート。
-   より高度なアドミッションコントロール戦略のパラメータ化と実装。
```
