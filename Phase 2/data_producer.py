from confluent_kafka import Producer
import pyarrow.parquet as pq
import pandas as pd
import time

TOPIC_NAME = "nyc_taxicab_data"
DATASET_PATH = "yellow_tripdata_2022-03.parquet"
BRONX_LOCATION_IDS = [
    3, 18, 20, 31, 32, 46, 47, 51, 58, 59, 60, 69, 78, 81, 94,
    119, 126, 136, 147, 159, 167, 168, 169, 174, 182, 183, 184,
    185, 199, 200, 208, 212, 213, 220, 235, 240, 241, 242, 247,
    248, 250, 254, 259
]


def load_trips(file_path):
    """Load and filter the NYC taxi parquet dataset to Bronx trips only."""
    trips = pq.read_table(file_path).to_pandas()

    trips = trips[[
        'tpep_pickup_datetime', 'tpep_dropoff_datetime',
        'PULocationID', 'DOLocationID',
        'trip_distance', 'fare_amount'
    ]]

    trips = trips[
        trips['PULocationID'].isin(BRONX_LOCATION_IDS) &
        trips['DOLocationID'].isin(BRONX_LOCATION_IDS)
    ]
    trips = trips[trips['trip_distance'] > 0.1]
    trips = trips[trips['fare_amount'] > 2.5]

    trips['tpep_pickup_datetime'] = pd.to_datetime(
        trips['tpep_pickup_datetime'], format='%Y-%m-%d %H:%M:%S'
    )
    trips['tpep_dropoff_datetime'] = pd.to_datetime(
        trips['tpep_dropoff_datetime'], format='%Y-%m-%d %H:%M:%S'
    )

    return trips


def main():
    producer = Producer({'bootstrap.servers': 'localhost:9092'})

    print("Connected to Kafka. Topics:", producer.list_topics().topics)
    print("-" * 40)

    trips = load_trips(DATASET_PATH)
    print(f"Loaded {trips.shape[0]} Bronx trips. Streaming to Kafka...")

    for counter, (_, row) in enumerate(trips.iterrows(), start=1):
        message = row[['trip_distance', 'PULocationID', 'DOLocationID', 'fare_amount']]\
            .to_json()\
            .encode('utf-8')

        producer.produce(TOPIC_NAME, value=message)
        producer.flush()

        print(f"[{counter}] Sent: {message}")
        time.sleep(0.25)

    print("All trips streamed successfully.")


if __name__ == "__main__":
    main()
