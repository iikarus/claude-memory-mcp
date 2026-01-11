import json
import logging
import os
from typing import Any, Dict, List, Optional

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
}


class OntologyManager:
    """
    Manages the dynamic schema of memory types.
    Persists definitions to ontology.json.
    """

    def __init__(self, config_path: str = "ontology.json"):
        self.config_path = config_path
        self._ontology: Dict[str, Dict[str, Any]] = DEFAULT_ONTOLOGY.copy()
        self._load()

    def _load(self) -> None:
        """Load ontology from disk if exists."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    saved = json.load(f)
                    # Merge with defaults (defaults always exist)
                    self._ontology.update(saved)
                logger.info(f"Loaded {len(self._ontology)} memory types from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load ontology: {e}. Using defaults.")
        else:
            self._save()

    def _save(self) -> None:
        """Save ontology to disk."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._ontology, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save ontology: {e}")

    def is_valid_type(self, node_type: str) -> bool:
        """Check if a node type is defined."""
        return node_type in self._ontology

    def add_type(self, name: str, description: str, required_properties: List[str] = []) -> None:
        """Register a new memory type."""
        if name in self._ontology:
            logger.warning(f"Overwriting memory type: {name}")

        self._ontology[name] = {
            "description": description,
            "required_properties": required_properties,
        }
        self._save()
        logger.info(f"Registered memory type: {name}")

    def get_type_definition(self, name: str) -> Optional[Dict[str, Any]]:
        return self._ontology.get(name)

    def list_types(self) -> List[str]:
        return list(self._ontology.keys())
