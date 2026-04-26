from neo4j import GraphDatabase


class Interface:

    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)
        self._driver.verify_connectivity()

    def close(self):
        self._driver.close()

    def bfs(self, start_node, last_node):
        """
        Find the shortest path from start_node to one or more target nodes
        using Breadth-First Search via Neo4j's shortestPath.

        Args:
            start_node (int): Location ID of the starting node
            last_node (int | list[int]): Target location ID(s)

        Returns:
            list: [{"path": [{"name": int}, ...]}] or [] if no path found
        """
        with self._driver.session() as session:
            targets = last_node if isinstance(last_node, list) else [last_node]

            result = session.run("""
                MATCH (s:Location {name: $start})
                UNWIND $targets AS tgt
                MATCH (t:Location {name: tgt})
                MATCH p = shortestPath((s)-[:TRIP*]-(t))
                WITH p
                RETURN [n IN nodes(p) | n.name] AS names
                ORDER BY size(names) ASC
                LIMIT 1
            """, start=start_node, targets=targets)

            rec = result.single()
            names = rec["names"] if rec else []
            path = [{"name": int(n)} for n in names]
            return [{"path": path}] if path else []

    def pagerank(self, max_iterations, weight_property):
        """
        Run PageRank on the Location graph using the GDS library.

        Args:
            max_iterations (int): Maximum number of PageRank iterations
            weight_property (str): Relationship property to use as edge weight

        Returns:
            tuple: (max_node, min_node) each as {"name": int, "score": float}
        """
        with self._driver.session() as session:
            # Drop graph projection if it already exists
            session.run("CALL gds.graph.drop('pageRankGraph', false) YIELD graphName")

            # Project the graph
            session.run("""
                CALL gds.graph.project(
                    'pageRankGraph',
                    'Location',
                    { TRIP: { properties: $props } }
                )
            """, props=[weight_property])

            # Run PageRank and collect results
            result = session.run("""
                CALL gds.pageRank.stream('pageRankGraph', {
                    maxIterations: $mi,
                    relationshipWeightProperty: $wprop
                })
                YIELD nodeId, score
                RETURN gds.util.asNode(nodeId).name AS name, score
                ORDER BY score DESC
            """, mi=max_iterations, wprop=weight_property)

            rows = result.data()

            # Clean up graph projection
            session.run("CALL gds.graph.drop('pageRankGraph', false) YIELD graphName")

            if not rows:
                return []

            max_node = {"name": int(rows[0]["name"]),  "score": float(rows[0]["score"])}
            min_node = {"name": int(rows[-1]["name"]), "score": float(rows[-1]["score"])}

            return (max_node, min_node)
