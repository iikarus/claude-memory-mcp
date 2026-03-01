"""Mutation-killing tests for ontology.py — DEFAULT_ONTOLOGY structure.

Split from test_mutant_schema_integrity.py per 300-line module cap.
"""

from __future__ import annotations

from claude_memory.ontology import DEFAULT_ONTOLOGY

_EXPECTED_ONTOLOGY_TYPES = {
    "Entity",
    "Concept",
    "Project",
    "Person",
    "Decision",
    "Session",
    "Breakthrough",
    "Analogy",
    "Observation",
    "Tool",
    "Issue",
    "Bottle",
    "Procedure",
}


class TestDefaultOntology:
    """Assert DEFAULT_ONTOLOGY types, descriptions, and structure."""

    def test_ontology_evil_mutated_type_names(self) -> None:
        """Evil: mutmut-mutated type names must not be present."""
        for t in _EXPECTED_ONTOLOGY_TYPES:
            assert f"XX{t}XX" not in DEFAULT_ONTOLOGY

    def test_ontology_evil_descriptions_not_empty(self) -> None:
        """Evil: every type must have a non-empty description string."""
        for _type_name, defn in DEFAULT_ONTOLOGY.items():
            assert isinstance(defn["description"], str)
            assert len(defn["description"]) > 0

    def test_ontology_evil_required_properties_is_list(self) -> None:
        """Evil: required_properties must be a list."""
        for _type_name, defn in DEFAULT_ONTOLOGY.items():
            assert isinstance(defn["required_properties"], list)

    def test_ontology_sad_missing_type_not_present(self) -> None:
        """Sad: 'Recipe' is not a default type."""
        assert "Recipe" not in DEFAULT_ONTOLOGY

    def test_ontology_happy_all_types_present(self) -> None:
        """Happy: all 13 expected types are present."""
        assert set(DEFAULT_ONTOLOGY.keys()) == _EXPECTED_ONTOLOGY_TYPES
        assert len(DEFAULT_ONTOLOGY) == 13

    # ── Specific description assertions to kill string mutations ═══

    def test_ontology_entity_description(self) -> None:
        assert "generic" in DEFAULT_ONTOLOGY["Entity"]["description"].lower()

    def test_ontology_concept_description(self) -> None:
        assert "idea" in DEFAULT_ONTOLOGY["Concept"]["description"].lower()

    def test_ontology_project_description(self) -> None:
        assert "project" in DEFAULT_ONTOLOGY["Project"]["description"].lower()

    def test_ontology_person_description(self) -> None:
        assert "human" in DEFAULT_ONTOLOGY["Person"]["description"].lower()

    def test_ontology_decision_description(self) -> None:
        assert "choice" in DEFAULT_ONTOLOGY["Decision"]["description"].lower()

    def test_ontology_session_description(self) -> None:
        assert "session" in DEFAULT_ONTOLOGY["Session"]["description"].lower()

    def test_ontology_breakthrough_description(self) -> None:
        assert "realization" in DEFAULT_ONTOLOGY["Breakthrough"]["description"].lower()

    def test_ontology_analogy_description(self) -> None:
        assert "comparison" in DEFAULT_ONTOLOGY["Analogy"]["description"].lower()

    def test_ontology_observation_description(self) -> None:
        assert "evidence" in DEFAULT_ONTOLOGY["Observation"]["description"].lower()

    def test_ontology_tool_description(self) -> None:
        assert "tool" in DEFAULT_ONTOLOGY["Tool"]["description"].lower()

    def test_ontology_issue_description(self) -> None:
        assert "problem" in DEFAULT_ONTOLOGY["Issue"]["description"].lower()

    def test_ontology_bottle_description(self) -> None:
        assert "bottle" in DEFAULT_ONTOLOGY["Bottle"]["description"].lower()

    def test_ontology_procedure_description(self) -> None:
        desc = DEFAULT_ONTOLOGY["Procedure"]["description"].lower()
        assert "process" in desc or "protocol" in desc
