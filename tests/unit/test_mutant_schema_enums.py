"""Mutation-killing tests for schema.py — EdgeType and CertaintyLevel enums.

Split from test_mutant_schema_integrity.py per 300-line module cap.
"""

from __future__ import annotations

from typing import get_args

# ═══════════════════════════════════════════════════════════════════
# EdgeType — All 24 relationship types (schema.py)
# ═══════════════════════════════════════════════════════════════════

_EXPECTED_EDGE_TYPES = {
    "DEPENDS_ON",
    "ENABLES",
    "BLOCKS",
    "CONTAINS",
    "PART_OF",
    "EVOLVED_FROM",
    "SUPERSEDES",
    "PRECEDED_BY",
    "CONCURRENT_WITH",
    "CONTRADICTS",
    "SUPPORTS",
    "REJECTED_FOR",
    "REVISITED_BECAUSE",
    "RHYMES_WITH",
    "ANALOGOUS_TO",
    "TAUGHT_THROUGH",
    "BREAKTHROUGH_IN",
    "UNLOCKED",
    "CREATED_BY",
    "DECIDED_IN",
    "MENTIONED_IN",
    "BELONGS_TO_PROJECT",
    "BRIDGES_TO",
    "RELATED_TO",
}


class TestEdgeType:
    """Assert exact membership of EdgeType Literal."""

    def test_edge_type_evil_extra_type_not_present(self) -> None:
        """Evil: a fake type like 'DESTROYS' must NOT be in EdgeType."""
        from claude_memory.schema import EdgeType

        allowed = set(get_args(EdgeType))
        assert "DESTROYS" not in allowed
        assert "XXENABLESXX" not in allowed

    def test_edge_type_evil_mutated_strings_rejected(self) -> None:
        """Evil: mutmut-style mutations must not match."""
        from claude_memory.schema import EdgeType

        allowed = set(get_args(EdgeType))
        for original in _EXPECTED_EDGE_TYPES:
            mutated = f"XX{original}XX"
            assert mutated not in allowed

    def test_edge_type_evil_count_exact(self) -> None:
        """Evil: adding or removing types changes the count."""
        from claude_memory.schema import EdgeType

        allowed = set(get_args(EdgeType))
        assert len(allowed) == 24

    def test_edge_type_sad_case_sensitive(self) -> None:
        """Sad: lowercase versions must not be present."""
        from claude_memory.schema import EdgeType

        allowed = set(get_args(EdgeType))
        assert "depends_on" not in allowed
        assert "enables" not in allowed

    def test_edge_type_happy_all_present(self) -> None:
        """Happy: every expected relationship type is in EdgeType."""
        from claude_memory.schema import EdgeType

        allowed = set(get_args(EdgeType))
        assert _EXPECTED_EDGE_TYPES == allowed


# ═══════════════════════════════════════════════════════════════════
# CertaintyLevel — 5 levels (schema.py)
# ═══════════════════════════════════════════════════════════════════

_EXPECTED_CERTAINTY = {"confirmed", "speculative", "spitballing", "rejected", "revisited"}


class TestCertaintyLevel:
    """Assert exact membership of CertaintyLevel Literal."""

    def test_certainty_evil_mutated_string(self) -> None:
        """Evil: mutmut-style mutations must not match."""
        from claude_memory.schema import CertaintyLevel

        allowed = set(get_args(CertaintyLevel))
        assert "XXconfirmedXX" not in allowed

    def test_certainty_evil_extra_level(self) -> None:
        """Evil: a fake level must NOT be in CertaintyLevel."""
        from claude_memory.schema import CertaintyLevel

        allowed = set(get_args(CertaintyLevel))
        assert "maybe" not in allowed

    def test_certainty_evil_count_exact(self) -> None:
        """Evil: exactly 5 certainty levels."""
        from claude_memory.schema import CertaintyLevel

        allowed = set(get_args(CertaintyLevel))
        assert len(allowed) == 5

    def test_certainty_sad_uppercase_rejected(self) -> None:
        """Sad: uppercase versions not valid."""
        from claude_memory.schema import CertaintyLevel

        allowed = set(get_args(CertaintyLevel))
        assert "Confirmed" not in allowed

    def test_certainty_happy_all_present(self) -> None:
        """Happy: every expected certainty level is present."""
        from claude_memory.schema import CertaintyLevel

        allowed = set(get_args(CertaintyLevel))
        assert _EXPECTED_CERTAINTY == allowed
