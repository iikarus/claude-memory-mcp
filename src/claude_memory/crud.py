"""CRUD operations for the Exocortex memory system.

Provides entity, relationship, and observation create/update/delete logic.
"""

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

# When True (default), Qdrant write failures crash the operation instead of
# being silently swallowed.  This prevents split-brain scenarios where an
# entity exists in FalkorDB but is invisible to semantic search.
STRICT_CONSISTENCY = os.getenv("EXOCORTEX_STRICT_CONSISTENCY", "true").lower() == "true"

if TYPE_CHECKING:  # pragma: no cover
    from .interfaces import Embedder, VectorStore
    from .lock_manager import LockManager
    from .ontology import OntologyManager
    from .repository import MemoryRepository
    from .schema import (
        EntityCommitReceipt,
        EntityCreateParams,
        EntityDeleteParams,
        EntityUpdateParams,
        RelationshipCreateParams,
        RelationshipDeleteParams,
    )

logger = logging.getLogger(__name__)


class CrudMixin:
    """Entity/Relationship/Observation CRUD — mixed into MemoryService."""

    # Inherited attributes (set by MemoryService.__init__)
    repo: "MemoryRepository"
    embedder: "Embedder"
    vector_store: "VectorStore"
    ontology: "OntologyManager"
    lock_manager: "LockManager"

    async def create_entity(self, params: "EntityCreateParams") -> "EntityCommitReceipt":
        """Creates an entity node in the graph."""
        from .schema import EntityCommitReceipt  # noqa: PLC0415

        project_id = params.project_id

        async with self.lock_manager.lock(project_id):
            # Validate Dynamic Type
            if not self.ontology.is_valid_type(params.node_type):
                raise ValueError(
                    f"Invalid memory type: '{params.node_type}'. "
                    f"Allowed types: {self.ontology.list_types()}"
                )

            start_time = datetime.now()
            logger.info(f"Creating entity: {params.name} ({params.node_type})")

            props = params.properties.copy()
            props["id"] = params.properties.get("id") or str(uuid.uuid4())
            props.update(
                {
                    "name": params.name,
                    "node_type": params.node_type,
                    "project_id": params.project_id,
                    "certainty": params.certainty,
                    "evidence": params.evidence,
                    "salience_score": 1.0,
                    "retrieval_count": 0,
                    "occurred_at": params.properties.get(
                        "occurred_at", datetime.now(UTC).isoformat()
                    ),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )

            # Compute embedding (AI Layer)
            desc = props.get("description", "")
            text_to_embed = f"{params.name} {params.node_type} {desc}"
            embedding = self.embedder.encode(text_to_embed)

            # 1. Write to Graph (FalkorDB) - Source of Truth for Structure
            node_props = self.repo.create_node(params.node_type, props)

            # 2. Write to Vector Engine (Qdrant) - Source of Truth for Search
            node_id = str(node_props["id"])
            warnings: list[str] = []

            payload = {
                "name": params.name,
                "node_type": params.node_type,
                "project_id": params.project_id,
            }
            try:
                await self.vector_store.upsert(id=node_id, vector=embedding, payload=payload)
            except Exception as e:
                msg = f"vector_upsert_failed: {e}"
                logger.error(msg)
                if STRICT_CONSISTENCY:
                    raise
                warnings.append(msg)

            # 3. Link to most recent entity in same project via PRECEDED_BY
            try:
                prev = self.repo.get_most_recent_entity(project_id)
                if prev and prev.get("id") != node_id:
                    self.repo.create_edge(
                        prev["id"],
                        node_id,
                        "PRECEDED_BY",
                        {"created_at": datetime.now(UTC).isoformat()},
                    )
            except Exception:
                logger.warning("PRECEDED_BY link failed — entity created without temporal link")

            result = node_props

            final_id = str(result["id"])
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            status = "created"

            # Get total count (for receipt)
            total_count = self.repo.get_total_node_count()

            return EntityCommitReceipt(
                id=final_id,
                name=params.name,
                status="committed",
                operation_time_ms=duration,
                total_memory_count=total_count,
                message=f"Successfully {status} '{params.name}' in the Infinite Graph.",
                warnings=warnings,
            )

    async def create_relationship(self, params: "RelationshipCreateParams") -> dict[str, Any]:
        """Creates a typed relationship between two entities."""

        source_node = self.repo.get_node(params.from_entity)

        if source_node and "project_id" in source_node:
            pass

        project_id = source_node.get("project_id") if source_node else None

        async def _do_create() -> dict[str, Any]:
            """Execute relationship creation inside the optional lock."""
            logger.info(
                f"Creating relationship: {params.from_entity} "
                f"-[{params.relationship_type}]-> {params.to_entity}"
            )

            props = params.properties.copy()
            props["confidence"] = params.confidence
            props["weight"] = params.weight
            props["created_at"] = datetime.now(UTC).isoformat()
            if "id" not in props:
                props["id"] = str(uuid.uuid4())

            res = self.repo.create_edge(
                params.from_entity, params.to_entity, params.relationship_type, props
            )
            if not res:
                return {"error": "Could not create relationship. Check entity IDs."}
            return res

        if project_id:
            async with self.lock_manager.lock(project_id):
                return await _do_create()
        else:
            return await _do_create()

    async def update_entity(self, params: "EntityUpdateParams") -> dict[str, Any]:
        """Updates properties of an existing entity."""

        existing_node = self.repo.get_node(params.entity_id)
        if not existing_node:
            return {"error": "Entity not found"}

        project_id = existing_node.get("project_id")

        async def _do_update() -> dict[str, Any]:
            """Execute entity update inside the optional lock."""
            logger.info(f"Updating entity: {params.entity_id}")

            props = params.properties.copy()
            timestamp = datetime.now(UTC).isoformat()
            props["updated_at"] = timestamp

            embedding = None
            merged_props = existing_node.copy()
            merged_props.update(props)

            desc = merged_props.get("description", "")
            name = merged_props.get("name", "")
            node_type = merged_props.get("node_type", "Entity")

            text_to_embed = f"{name} {node_type} {desc}"
            embedding = self.embedder.encode(text_to_embed)

            # 1. Update Graph
            updated_node = self.repo.update_node(params.entity_id, props)

            # 2. Update Vector Store
            payload = {
                "name": name,
                "node_type": node_type,
                "project_id": project_id,
            }
            try:
                await self.vector_store.upsert(
                    id=params.entity_id,
                    vector=embedding,
                    payload=payload,
                )
            except Exception as e:
                msg = f"vector_upsert_failed: {e}"
                logger.error(msg)
                if STRICT_CONSISTENCY:
                    raise
                updated_node["warnings"] = [msg]

            return updated_node  # type: ignore[no-any-return]

        if project_id:
            async with self.lock_manager.lock(project_id):
                return await _do_update()
        else:
            return await _do_update()

    async def _safe_vector_delete(self, entity_id: str) -> list[str]:
        """Delete vector and return warnings list (empty on success)."""
        warnings: list[str] = []
        try:
            await self.vector_store.delete(entity_id)
        except Exception as e:
            logger.error(f"vector_delete_failed: {entity_id}: {e}")
            if STRICT_CONSISTENCY:
                raise
            warnings.append(f"vector_delete_failed: {e}")
        return warnings

    async def delete_entity(self, params: "EntityDeleteParams") -> dict[str, Any]:
        """Deletes an entity."""

        existing_node = self.repo.get_node(params.entity_id)
        if not existing_node:
            return {"error": "Entity not found"}

        project_id = existing_node.get("project_id")

        async def _do_delete() -> dict[str, Any]:
            """Execute entity deletion inside the optional lock."""
            logger.info(f"Deleting entity: {params.entity_id} ({params.reason})")

            if params.soft_delete:
                self.repo.update_node(
                    params.entity_id,
                    {"status": "archived", "archived_at": datetime.now(UTC).isoformat()},
                )
                warnings = await self._safe_vector_delete(params.entity_id)
                result_dict: dict[str, Any] = {
                    "status": "archived",
                    "id": params.entity_id,
                }
                if warnings:
                    result_dict["warnings"] = warnings
                return result_dict
            else:
                self.repo.delete_node(params.entity_id)
                warnings = await self._safe_vector_delete(params.entity_id)
                result: dict[str, Any] = {"status": "deleted", "id": params.entity_id}
                if warnings:
                    result["warnings"] = warnings
                return result

        if project_id:
            async with self.lock_manager.lock(project_id):
                return await _do_delete()
        else:
            return await _do_delete()

    async def delete_relationship(self, params: "RelationshipDeleteParams") -> dict[str, Any]:
        """Deletes a relationship."""
        self.repo.delete_edge(params.relationship_id)
        return {"status": "deleted", "id": params.relationship_id}
