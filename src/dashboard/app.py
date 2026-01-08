import asyncio
import os
import sys
from typing import Any, Tuple

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from claude_memory.embedding import EmbeddingService  # noqa: E402
from claude_memory.tools import MemoryService  # noqa: E402

st.set_page_config(layout="wide", page_title="Memory Explorer")


@st.cache_resource  # type: ignore
def get_service() -> MemoryService:
    embedder = EmbeddingService()
    return MemoryService(embedding_service=embedder)


async def get_graph_data(limit: int = 100) -> Any:
    service = get_service()
    # Direct cypher for graph viz
    q = f"""
    MATCH (n:Entity)-[r]->(m:Entity)
    RETURN n, r, m LIMIT {limit}
    """
    return service.repo.execute_cypher(q)


async def get_stats() -> Tuple[int, int]:
    service = get_service()
    nodes = service.repo.execute_cypher("MATCH (n:Entity) RETURN count(n)").result_set[0][0]
    edges = service.repo.execute_cypher("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    return nodes, edges


def main() -> None:
    st.title("🧠 Memory System Visual Explorer")

    service = get_service()

    # Sidebar Stats
    nodes, edges = asyncio.run(get_stats())
    st.sidebar.metric("Entities", nodes)
    st.sidebar.metric("Relationships", edges)

    menu = st.sidebar.radio("Mode", ["Explorer", "Search", "Maintenance"])

    if menu == "Explorer":
        st.header("Graph View")
        limit = st.slider("Max Nodes", 10, 500, 100)

        if st.button("Refresh Graph"):
            res = asyncio.run(get_graph_data(limit))

            net = Network(height="600px", width="100%", bgcolor="#222222", font_color="white")

            for row in res.result_set:
                n = row[0]
                r = row[1]
                m = row[2]

                net.add_node(
                    n.properties["id"],
                    label=n.properties.get("name", "Unknown"),
                    title=str(n.properties),
                )
                net.add_node(
                    m.properties["id"],
                    label=m.properties.get("name", "Unknown"),
                    title=str(m.properties),
                )
                net.add_edge(n.properties["id"], m.properties["id"], title=r.relation)

            net.repulsion()
            net.save_graph("graph.html")

            with open("graph.html", "r", encoding="utf-8") as f:
                source_code = f.read()
            components.html(source_code, height=600)

    elif menu == "Search":
        st.header("Semantic Search")
        query = st.text_input("Query")
        if query:
            results = asyncio.run(service.search(query))
            for res in results:
                with st.expander(f"{res['name']} (Score: {res['similarity']:.2f})"):
                    st.json(res)

    elif menu == "Maintenance":
        st.header("Maintenance Tools")

        st.subheader("Stale Entities")
        days = st.number_input("Days Inactive", value=30)
        if st.button("Scan"):
            stale = asyncio.run(service.get_stale_entities(days))
            st.write(f"Found {len(stale)} stale entities.")
            st.dataframe(stale)


if __name__ == "__main__":
    main()
