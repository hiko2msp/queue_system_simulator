import argparse
import csv
import random
import datetime
import numpy as np

def generate_sample_data(user_id):
    """Generates sample data for a given user ID."""
    records = []
    num_records = random.randint(10, 40)
    base_date = datetime.date(2023, 10, 26)

    for _ in range(num_records):
        # Generate random time
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        timestamp = datetime.datetime(base_date.year, base_date.month, base_date.day, hour, minute, second)

        # Generate processing time from a normal distribution (mean 20)
        # Assuming a standard deviation of 5 for this example
        processing_time = max(1, int(np.random.normal(loc=20, scale=5)))  # Ensure processing time is at least 1

        records.append({
            "user_id": user_id,
            "request_time": timestamp.timestamp(),  # Use Unix timestamp for request_time
            "processing_time": processing_time # Renamed from processing_time_ms
        })
    return records

def main():
    parser = argparse.ArgumentParser(description="Generate sample data for a user.")
    parser.add_argument("user_id", help="The user ID for which to generate data.")
    args = parser.parse_args()

    user_id = args.user_id
    data = generate_sample_data(user_id)

    # Output as CSV to stdout
    if data:
        fieldnames = data[0].keys()
        writer = csv.DictWriter(open(f"sample_data_{user_id}.csv", "w", newline=""), fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        print(f"Generated {len(data)} records for user_id '{user_id}' in 'sample_data_{user_id}.csv'")

if __name__ == "__main__":
    main()
