import argparse
import csv
import datetime
import random

# シミュレーションの基準となる開始時刻 (UTC)
SIMULATION_START_TIME = datetime.datetime(2023, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)


def generate_sample_data(output_file="sample_requests.csv", num_users=5, max_requests_per_user=5):
    """Generates sample request data and saves it to a CSV file."""
    records = []
    current_time = 0.0

    user_ids = [f"user_{chr(97 + i)}" for i in range(num_users)]  # user_a, user_b, ...

    for i in range(num_users * max_requests_per_user):
        user_id = random.choice(user_ids)
        # request_timeをシミュレーション開始からの経過秒数とする
        # 次のリクエスト時間は、前のリクエスト時間から少し進める
        current_time += random.uniform(0.1, 1.0)
        # ISO 8601 形式でrequest_timeを生成
        request_datetime = SIMULATION_START_TIME + datetime.timedelta(seconds=current_time)
        # マイクロ秒まで含め、末尾に 'Z' を追加
        request_time_iso = request_datetime.isoformat(timespec="microseconds").replace("+00:00", "Z")

        processing_time = round(random.uniform(1.0, 10.0), 1)  # 処理時間は1.0から10.0秒の範囲

        records.append({"user_id": user_id, "request_time": request_time_iso, "processing_time": processing_time})

    # request_timeでソート
    records.sort(key=lambda x: x["request_time"])

    with open(output_file, "w", newline="") as f:
        fieldnames = ["user_id", "request_time", "processing_time"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"Generated {len(records)} sample requests in '{output_file}'")


def main():
    parser = argparse.ArgumentParser(description="Generate sample request data.")
    parser.add_argument("--users", type=int, default=5, help="Number of unique users.")
    parser.add_argument(
        "--max_requests",
        type=int,
        default=5,
        help="Maximum number of requests per user (total requests will be users * max_requests).",
    )
    parser.add_argument("--output", type=str, default="sample_requests.csv", help="Output CSV file name.")
    args = parser.parse_args()

    generate_sample_data(output_file=args.output, num_users=args.users, max_requests_per_user=args.max_requests)


if __name__ == "__main__":
    main()
