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


async def get_graph_data(limit: int = 100, focus: str = "") -> Any:
    service = get_service()

    if focus:
        # Focused Query (Neighborhood)
        # Try to find node by ID or Name
        # We use OPTIONAL MATCH to get connections
        q = f"""
        MATCH (n:Entity)
        WHERE n.id = '{focus}' OR n.name CONTAINS '{focus}'
        OPTIONAL MATCH (n)-[r]-(m:Entity)
        RETURN n, r, m LIMIT {limit}
        """
    else:
        # Global Query
        q = f"""
        MATCH (n:Entity)
        OPTIONAL MATCH (n)-[r]->(m:Entity)
        RETURN n, r, m LIMIT {limit}
        """
    return service.repo.execute_cypher(q)


async def get_stats() -> Tuple[int, int]:
    service = get_service()
    nodes = service.repo.execute_cypher("MATCH (n) RETURN count(n)").result_set[0][0]
    edges = service.repo.execute_cypher("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    return nodes, edges


def main() -> None:
    st.title("🧠 Memory System Visual Explorer")

    service = get_service()

    # Sidebar Stats
    nodes, edges = asyncio.run(get_stats())
    st.sidebar.metric("Total Nodes", nodes)
    st.sidebar.metric("Relationships", edges)

    menu = st.sidebar.radio("Mode", ["Explorer", "Search", "Maintenance"])

    if menu == "Explorer":
        st.header("Graph View")
        col1, col2 = st.columns([1, 2])
        with col1:
            limit = st.slider("Max Nodes", 10, 500, 100)
        with col2:
            focus = st.text_input("Focus Node (ID or Name)", help="Leave empty for global view")

        if st.button("Refresh Graph"):
            res = asyncio.run(get_graph_data(limit, focus))

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

                if r is not None and m is not None:
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

    # === SHUTDOWN CONTROLS ===
    st.sidebar.markdown("---")
    st.sidebar.subheader("System Control")
    if st.sidebar.button("⛔ Safe Shutdown"):
        with st.sidebar.status("Initiating Shutdown Sequence...") as status:

            # 1. Perform Backup
            status.write("💾 Performing Backup...")
            import datetime
            import subprocess

            tag = f"shutdown_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Run script (assuming cwd is /app, so scripts/ is available)
            # We must use 'python' to run it.
            try:
                # We need to ensure we capture Output to debug if it fails
                res = subprocess.run(
                    ["python", "scripts/backup_restore.py", "save", "--tag", tag],
                    capture_output=True,
                    text=True,
                )
                if res.returncode == 0:
                    status.write(f"✅ Backup Successful: {tag}")
                else:
                    status.write("❌ Backup Failed!")
                    status.write(res.stderr)
                    # We might want to abort or ask user?
                    # For safety, we proceed only if backup success?
                    # User said "perform a backup first". Implies prerequisite.
                    st.error("Shutdown functions halted. Backup failed.")
                    st.code(res.stderr)
                    return
            except Exception as e:
                st.error(f"Backup Error: {e}")
                return

            # 2. Stop Containers
            status.write("🛑 Stopping Exocortex...")

            # We use docker CLI to find and stop siblings
            # Filter by compose project: claude-memory-mcp
            # We exclude our own container ID? Or just kill all.
            # If we kill all, we die. That's fine.

            try:
                # Get all container IDs for this project
                # We assume standard project name 'claude-memory-mcp'.
                # Ideally, we inspect our own labels to find project name.
                # But hardcoding is safer v0.

                cmd = "docker ps -q --filter label=com.docker.compose.project=claude-memory-mcp"
                ids_res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                ids = ids_res.stdout.strip().split()

                if not ids:
                    status.write("System already stopped? (No containers found)")
                else:
                    # Stop them
                    subprocess.run(["docker", "stop"] + ids)
                    status.write("✅ System Shutdown Complete.")
                    st.stop()  # Stop the streamlit script

            except Exception as e:
                status.write(f"❌ Shutdown Failed: {e}")


if __name__ == "__main__":
    main()
