# Base image: ubuntu:22.04
FROM ubuntu:22.04

ARG TARGETPLATFORM=linux/amd64,linux/arm64
ARG DEBIAN_FRONTEND=noninteractive

# Install Neo4j and base dependencies
RUN apt-get update && \
    apt-get install -y wget gnupg software-properties-common && \
    wget -O - https://debian.neo4j.com/neotechnology.gpg.key | apt-key add - && \
    echo 'deb https://debian.neo4j.com stable latest' > /etc/apt/sources.list.d/neo4j.list && \
    add-apt-repository universe && \
    apt-get update && \
    apt-get install -y nano unzip neo4j=1:2025.08.0 python3-pip && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Java 21
RUN apt-get update && apt-get install -y openjdk-21-jdk wget && \
    rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

# ARM64 compatibility: symlink arm64 JDK path to expected amd64 path
RUN if [ -d /usr/lib/jvm/java-21-openjdk-arm64 ]; then \
      ln -s /usr/lib/jvm/java-21-openjdk-arm64 /usr/lib/jvm/java-21-openjdk-amd64; \
    fi

# Set Neo4j password and install Python dependencies
RUN neo4j-admin dbms set-initial-password graphprocessing
ENV NEO4J_AUTH=neo4j/graphprocessing
RUN pip install --upgrade pip && pip install neo4j pandas pyarrow

# Install Neo4j Graph Data Science plugin v2.21.0
RUN mkdir -p /var/lib/neo4j/plugins && \
    wget -q https://github.com/neo4j/graph-data-science/releases/download/2.21.0/neo4j-graph-data-science-2.21.0.jar \
      -O /var/lib/neo4j/plugins/neo4j-graph-data-science-2.21.0.jar

# Set up working directory and copy data loader script
WORKDIR /cse511/
COPY data_loader.py /cse511/

# Download the NYC Taxi dataset
RUN wget -q https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2022-03.parquet \
    -O /cse511/yellow_tripdata_2022-03.parquet

# Configure Neo4j: network access, GDS/APOC permissions, CSV import
RUN echo "dbms.security.procedures.unrestricted=apoc.*,gds.*" >> /etc/neo4j/neo4j.conf && \
    echo "dbms.security.procedures.allowlist=apoc.*,gds.*" >> /etc/neo4j/neo4j.conf && \
    echo "server.default_advertised_address=localhost" >> /etc/neo4j/neo4j.conf && \
    echo "server.default_listen_address=0.0.0.0" >> /etc/neo4j/neo4j.conf && \
    echo "dbms.security.allow_csv_import_from_file_urls=true" >> /etc/neo4j/neo4j.conf

# Start Neo4j, load data, then stop (data is baked into the image)
RUN chmod +x /cse511/data_loader.py && \
    neo4j start && \
    echo "Waiting for Neo4j to start..." && sleep 30 && \
    python3 /cse511/data_loader.py && \
    neo4j stop

# Expose Neo4j browser (7474) and Bolt protocol (7687)
EXPOSE 7474 7687

# Start Neo4j on container run
CMD ["/bin/bash", "-c", "neo4j start && tail -f /dev/null"]
