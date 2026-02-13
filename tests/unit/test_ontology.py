import os
from collections.abc import Generator
from unittest.mock import patch

import pytest

from claude_memory.ontology import OntologyManager


@pytest.fixture
def clean_ontology_file() -> Generator[str, None, None]:
    filename = "test_ontology.json"
    if os.path.exists(filename):
        os.remove(filename)
    yield filename
    if os.path.exists(filename):
        os.remove(filename)


def test_defaults_loaded(clean_ontology_file):
    manager = OntologyManager(config_path=clean_ontology_file)
    assert manager.is_valid_type("Entity")
    assert manager.is_valid_type("Concept")
    assert not manager.is_valid_type("InvalidType")


def test_add_type(clean_ontology_file):
    manager = OntologyManager(config_path=clean_ontology_file)
    manager.add_type("Recipe", "A cooking recipe", ["ingredients"])

    assert manager.is_valid_type("Recipe")
    assert manager.get_type_definition("Recipe")["required_properties"] == ["ingredients"]


def test_persistence(clean_ontology_file):
    # 1. Create and save
    manager1 = OntologyManager(config_path=clean_ontology_file)
    manager1.add_type("Alien", "Extraterrestrial", [])

    # 2. Load in new instance
    manager2 = OntologyManager(config_path=clean_ontology_file)
    assert manager2.is_valid_type("Alien")
    assert manager2._ontology["Alien"]["description"] == "Extraterrestrial"


def test_overwrite_warning(clean_ontology_file, caplog):
    manager = OntologyManager(config_path=clean_ontology_file)
    with caplog.at_level("WARNING"):
        manager.add_type("Entity", "Overwriting default", [])
    assert "Overwriting memory type: Entity" in caplog.text


def test_invalid_load_fallback():
    # Test with a file that exists but is corrupt
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        manager = OntologyManager(config_path="readonly.json")
        # Should still have defaults
        assert manager.is_valid_type("Entity")


# ─── E-6: Procedural Memory ────────────────────────────────────────


def test_procedure_type_in_defaults(clean_ontology_file):
    """E-6: Procedure type should be a built-in default type."""
    manager = OntologyManager(config_path=clean_ontology_file)
    assert manager.is_valid_type("Procedure"), "Procedure not in DEFAULT_ONTOLOGY"
    defn = manager.get_type_definition("Procedure")
    assert defn is not None
    assert "process" in defn["description"].lower() or "protocol" in defn["description"].lower()


def test_procedure_entity_with_steps(clean_ontology_file):
    """E-6: Procedure type should support step-based observations."""
    manager = OntologyManager(config_path=clean_ontology_file)
    assert manager.is_valid_type("Procedure")
    # Verify the type definition has empty required_properties (steps are observations)
    defn = manager.get_type_definition("Procedure")
    assert defn["required_properties"] == []
