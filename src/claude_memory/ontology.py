"""Dynamic ontology management — defines and persists memory node type schemas."""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default Types that are always present
DEFAULT_ONTOLOGY = {
    "Entity": {
        "description": "A generic entity in the graph (default).",
        "required_properties": [],
    },
    "Concept": {"description": "A high-level idea or abstraction.", "required_properties": []},
    "Project": {"description": "A specific project or initiative.", "required_properties": []},
    "Person": {"description": "A human individual.", "required_properties": []},
    "Decision": {
        "description": "A specialized node recording a choice made.",
        "required_properties": [],
    },
    "Session": {"description": "A working session event.", "required_properties": []},
    "Breakthrough": {
        "description": "A key realization or moment of insight.",
        "required_properties": [],
    },
    "Analogy": {
        "description": "A comparison used to explain a concept.",
        "required_properties": [],
    },
    "Observation": {
        "description": "A piece of empirical evidence or note.",
        "required_properties": [],
    },
    "Tool": {"description": "A software tool or utility.", "required_properties": []},
    "Issue": {"description": "A problem or bug report.", "required_properties": []},
    "Bottle": {
        "description": "A timestamped note to your future self (Message in a Bottle).",
        "required_properties": [],
    },
}


class OntologyManager:
    """
    Manages the dynamic schema of memory types.
    Persists definitions to ontology.json.
    """

    # Default: project root / ontology.json (3 parents up from this file)
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    _DEFAULT_PATH = str(Path(os.getenv("ONTOLOGY_PATH", str(_PROJECT_ROOT / "ontology.json"))))

    def __init__(self, config_path: str = ""):
        """Load or initialize the ontology from disk."""
        self.config_path = config_path or self._DEFAULT_PATH
        self._ontology: dict[str, dict[str, Any]] = DEFAULT_ONTOLOGY.copy()
        self._load()

    def _load(self) -> None:
        """Load ontology from disk if exists."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    saved = json.load(f)
                    # Merge with defaults (defaults always exist)
                    self._ontology.update(saved)
                logger.info("Loaded %d memory types from %s", len(self._ontology), self.config_path)
            except Exception as e:
                logger.error("Failed to load ontology: %s. Using defaults.", e)
        else:
            self._save()

    def _save(self) -> None:
        """Save ontology to disk."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._ontology, f, indent=2)
        except Exception as e:
            logger.error("Failed to save ontology: %s", e)

    def is_valid_type(self, node_type: str) -> bool:
        """Check if a node type is defined."""
        return node_type in self._ontology

    def add_type(
        self, name: str, description: str, required_properties: list[str] | None = None
    ) -> None:
        """Register a new memory type."""
        if required_properties is None:
            required_properties = []
        if name in self._ontology:
            logger.warning("Overwriting memory type: %s", name)

        self._ontology[name] = {
            "description": description,
            "required_properties": required_properties,
        }
        self._save()
        logger.info("Registered memory type: %s", name)

    def get_type_definition(self, name: str) -> dict[str, Any] | None:
        """Return the schema definition for a given type name, or None.

        DEAD CODE — no production callers (audit 2026-02-12).
        Kept for API completeness and future use.
        """
        return self._ontology.get(name)

    def list_types(self) -> list[str]:
        """Return all registered memory type names."""
        return list(self._ontology.keys())
