import os
import pyarrow.parquet as pq
import pandas as pd
from neo4j import GraphDatabase
import time


class DataLoader:

    def __init__(self, uri, user, password):
        """
        Connect to the Neo4j database.

        Args:
            uri (str): URI of the Neo4j database
            user (str): Username of the Neo4j database
            password (str): Password of the Neo4j database
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)
        self.driver.verify_connectivity()

    def close(self):
        """Close the connection to the Neo4j database."""
        self.driver.close()

    def load_transform_file(self, file_path):
        """
        Load the parquet file, filter it to Bronx trips only,
        and write the data into Neo4j as a graph.

        Args:
            file_path (str): Path to the parquet file to be loaded
        """
        # Read the parquet file
        trips = pq.read_table(file_path).to_pandas()

        # Select relevant columns
        trips = trips[[
            'tpep_pickup_datetime', 'tpep_dropoff_datetime',
            'PULocationID', 'DOLocationID',
            'trip_distance', 'fare_amount'
        ]]

        # Filter to Bronx location IDs only
        bronx = [
            3, 18, 20, 31, 32, 46, 47, 51, 58, 59, 60, 69, 78, 81, 94,
            119, 126, 136, 147, 159, 167, 168, 169, 174, 182, 183, 184,
            185, 199, 200, 208, 212, 213, 220, 235, 240, 241, 242, 247,
            248, 250, 254, 259
        ]
        trips = trips[trips['PULocationID'].isin(bronx) & trips['DOLocationID'].isin(bronx)]
        trips = trips[trips['trip_distance'] > 0.1]
        trips = trips[trips['fare_amount'] > 2.5]

        # Parse datetime columns
        trips['tpep_pickup_datetime'] = pd.to_datetime(
            trips['tpep_pickup_datetime'], format='%Y-%m-%d %H:%M:%S'
        )
        trips['tpep_dropoff_datetime'] = pd.to_datetime(
            trips['tpep_dropoff_datetime'], format='%Y-%m-%d %H:%M:%S'
        )

        # Save CSV to Neo4j import directory
        save_loc = "/var/lib/neo4j/import/" + os.path.splitext(os.path.basename(file_path))[0] + '.csv'
        trips.to_csv(save_loc, index=False)

        # Load into Neo4j graph
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE"
            )

            trip_data = [
                {
                    "start": int(row["PULocationID"]),
                    "end": int(row["DOLocationID"]),
                    "distance": float(row["trip_distance"]),
                    "fare": float(row["fare_amount"]),
                    "pickup_dt": row["tpep_pickup_datetime"].to_pydatetime(),
                    "dropoff_dt": row["tpep_dropoff_datetime"].to_pydatetime(),
                }
                for _, row in trips.iterrows()
            ]

            result = session.run("""
                UNWIND $trips AS trip
                MERGE (from:Location {name: trip.start})
                MERGE (to:Location {name: trip.end})
                CREATE (from)-[:TRIP {
                    distance: trip.distance,
                    fare: trip.fare,
                    pickup_dt: trip.pickup_dt,
                    dropoff_dt: trip.dropoff_dt
                }]->(to)
            """, parameters={"trips": trip_data})

            result.consume()


def main():
    total_attempts = 10

    for attempt in range(total_attempts):
        try:
            data_loader = DataLoader("neo4j://localhost:7687", "neo4j", "graphprocessing")
            data_loader.load_transform_file("yellow_tripdata_2022-03.parquet")
            data_loader.close()
            print("Data loaded successfully.")
            break
        except Exception as e:
            print(f"(Attempt {attempt + 1}/{total_attempts}) Error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
