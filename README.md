# NYC Taxi Graph Pipeline

A two-phase data engineering project that models NYC taxi trip data as a graph and runs graph analytics on it — starting from a single Dockerized Neo4j instance, then scaling it into a fully distributed streaming pipeline using Kubernetes and Kafka.

---

## Architecture Overview

```
Phase 1 (Single Node)
┌─────────────────────────────────────────┐
│  Docker Container                       │
│  ┌─────────────┐    ┌────────────────┐  │
│  │ Parquet File│───▶│ Neo4j (Graph)  │  │
│  │ (NYC Trips) │    │ PageRank / BFS │  │
│  └─────────────┘    └────────────────┘  │
└─────────────────────────────────────────┘

Phase 2 (Distributed)
┌──────────────────────────────────────────────────────────┐
│  Kubernetes (Minikube)                                   │
│                                                          │
│  data_producer.py ──▶ Kafka ──▶ Kafka-Neo4j-Connector   │
│                                        │                 │
│                                        ▼                 │
│                                   Neo4j (GDS)            │
│                                  PageRank / BFS          │
└──────────────────────────────────────────────────────────┘
```

---

## Dataset

Download the **March 2022 NYC TLC Yellow Taxi Trip Records** and place it in `phase1-docker-neo4j/` before building:

🔗 https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

The pipeline filters trips to the **Bronx** only (42 location zones, ~1,530 trip relationships).

---

## Phase 1 — Dockerized Neo4j + Graph Algorithms

### What it does

- Builds a self-contained Docker image with Neo4j, Java 21, and the GDS plugin pre-installed
- Downloads and loads the NYC taxi dataset automatically at build time
- Models trips as a **directed graph**: `(Location)-[:TRIP]->(Location)`
- Exposes two graph algorithm implementations via `interface.py`

### Graph Schema

```
Node:         Location { name: int }       ← one per unique pickup/dropoff zone
Relationship: TRIP { distance, fare,
                     pickup_dt, dropoff_dt } ← one per taxi trip
```

### Setup & Run

```bash
cd phase1-docker-neo4j

# Build (downloads dataset + loads data — takes ~5 mins)
docker build -t nyc-taxi-graph .

# Run
docker run -d -p 7474:7474 -p 7687:7687 --name taxi-graph nyc-taxi-graph

# Wait 2-4 minutes for Neo4j to start, then open:
# http://localhost:7474  (browser UI)
```

### Graph Algorithms

Both are implemented in `interface.py` using the Neo4j GDS library.

**PageRank** — Ranks taxi zones by their importance in the trip network (i.e., which zones are most central/connected):

```python
from interface import Interface

db = Interface("neo4j://localhost:7687", "neo4j", "graphprocessing")
max_node, min_node = db.pagerank(max_iterations=20, weight_property="distance")
print(max_node)  # {"name": 212, "score": 2.87}
print(min_node)  # {"name": 3,   "score": 0.15}
```

**BFS (Breadth-First Search)** — Finds the shortest path between taxi zones:

```python
path = db.bfs(start_node=159, last_node=[212])
print(path)  # [{"path": [{"name": 159}, {"name": 212}]}]
```

### Verify Data Loaded

```cypher
-- In Neo4j browser (localhost:7474):
CALL db.schema.visualization();
MATCH (n) RETURN n LIMIT 25;
```

---

## Phase 2 — Kubernetes + Kafka Streaming Pipeline

### What it does

- Deploys **Zookeeper + Kafka** inside Minikube for real-time message streaming
- Deploys **Neo4j** via Helm with the GDS plugin enabled
- Connects Kafka → Neo4j using the **Kafka Connect Neo4j Sink Connector**
- Streams NYC taxi trip records into the graph in near real-time via `data_producer.py`
- Runs the same PageRank and BFS algorithms on the live graph via `interface.py`

### Prerequisites

- [Minikube](https://minikube.sigs.k8s.io/docs/start/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- Python packages: `confluent-kafka`, `pyarrow`, `pandas`, `neo4j`

### Setup

```bash
cd phase2-kubernetes-kafka

# 1. Start Minikube with enough resources
minikube start --cpus=4 --memory=8192

# 2. Deploy Zookeeper
kubectl apply -f zookeeper-setup.yaml

# 3. Deploy Kafka
kubectl apply -f kafka-setup.yaml

# 4. Deploy Neo4j via Helm
helm repo add neo4j https://helm.neo4j.com/neo4j
helm install neo4j neo4j/neo4j -f neo4j-values.yaml

# 5. Apply Neo4j service
kubectl apply -f neo4j-service.yaml  # (if using custom service config)

# 6. Deploy Kafka-Neo4j Connector
kubectl apply -f kafka-neo4j-connector.yaml

# 7. Expose ports (in a separate terminal)
kubectl port-forward svc/kafka-service 9092:9092 &
kubectl port-forward svc/neo4j-service 7474:7474 7687:7687 &
```

### Stream Data

```bash
# Streams NYC trip records into Kafka → Neo4j in real time
python3 data_producer.py
```

### Run Graph Analytics

```bash
# Same interface.py as Phase 1, now connected to the Kubernetes Neo4j
python3 -c "
from interface import Interface
db = Interface('neo4j://localhost:7687', 'neo4j', 'processingpipeline')
print(db.pagerank(20, 'distance'))
"
```

---

## Project Structure

```
nyc-taxi-graph-pipeline/
├── phase1-docker-neo4j/
│   ├── Dockerfile           # Builds Neo4j + loads data automatically
│   ├── data_loader.py       # Parquet → Neo4j graph loader
│   └── interface.py         # PageRank + BFS implementations
│
├── phase2-kubernetes-kafka/
│   ├── zookeeper-setup.yaml         # Zookeeper Service + Deployment
│   ├── kafka-setup.yaml             # Kafka Service + Deployment
│   ├── neo4j-values.yaml            # Helm values for Neo4j on K8s
│   ├── kafka-neo4j-connector.yaml   # Kafka Connect sink connector
│   ├── sink_neo4j.json              # Connector config (Cypher mapping)
│   └── data_producer.py             # Streams trip data into Kafka
│
├── .gitignore
└── README.md
```

---

## Tech Stack

| Technology | Role |
|---|---|
| **Neo4j** | Graph database storing locations and trips |
| **Neo4j GDS** | Graph Data Science library (PageRank, BFS) |
| **Docker** | Containerized single-node setup (Phase 1) |
| **Kubernetes / Minikube** | Container orchestration (Phase 2) |
| **Apache Kafka** | Real-time data streaming (Phase 2) |
| **Kafka Connect** | Kafka → Neo4j sink pipeline (Phase 2) |
| **Python** | Data loading, streaming, graph queries |
| **Helm** | Kubernetes package manager for Neo4j |
