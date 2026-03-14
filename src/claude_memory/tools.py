"""Core business logic for the Claude Memory system.

MemoryService is the public facade — it composes four focused mixins
(CrudMixin, SearchMixin, TemporalMixin, AnalysisMixin) into a single
class that ``server.py`` and tests can import without knowing the split.

All actual method implementations live in their respective modules.
"""

import asyncio
import logging

from claude_memory.activation import ActivationEngine
from claude_memory.analysis import AnalysisMixin
from claude_memory.context_manager import ContextManager
from claude_memory.crud import CrudMixin
from claude_memory.crud_maintenance import CrudMaintenanceMixin
from claude_memory.interfaces import Embedder, VectorStore
from claude_memory.router import QueryRouter
from claude_memory.search import SearchMixin
from claude_memory.temporal import TemporalMixin

from .lock_manager import LockManager
from .ontology import OntologyManager
from .repository import MemoryRepository

# Re-export schema items for backward compatibility
from .schema import (  # noqa: F401
    BottleQueryParams,
    BreakthroughParams,
    EntityCommitReceipt,
    EntityCreateParams,
    EntityDeleteParams,
    EntityUpdateParams,
    GapDetectionParams,
    ObservationParams,
    RelationshipCreateParams,
    RelationshipDeleteParams,
    SearchResult,
    SessionEndParams,
    SessionStartParams,
    TemporalQueryParams,
)
from .vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)


class MemoryService(CrudMixin, CrudMaintenanceMixin, SearchMixin, TemporalMixin, AnalysisMixin):
    """Orchestrates graph, vector, and ontology operations for memory management.

    This is a thin facade — all method implementations are in:
      - crud.py            (entity / relationship CRUD)
      - crud_maintenance.py (observation CRUD, background salience)
      - search.py          (vector search, spreading activation, hologram)
      - temporal.py        (sessions, breakthroughs, timeline)
      - analysis.py        (graph health, gaps, stale, consolidation)
    """

    def __init__(
        self,
        embedding_service: Embedder,
        vector_store: VectorStore | None = None,
        host: str | None = None,
        port: int | None = None,
        password: str | None = None,
    ) -> None:
        """Wire up repository, embedder, vector store, ontology, and lock manager."""
        self.repo = MemoryRepository(host, port, password)
        self.embedder = embedding_service
        self.vector_store = vector_store or QdrantVectorStore()

        # Core Components
        self.ontology = OntologyManager()
        self.context_manager = ContextManager()
        # Share connection config
        self.lock_manager = LockManager(host, port)
        # Strategy objects (stateless — cached, not per-call)
        self.router = QueryRouter()
        self.activation_engine = ActivationEngine(repo=self.repo)
        # Background tasks for fire-and-forget operations
        self._background_tasks: set[asyncio.Task[None]] = set()
        # Search stats accumulator (DRIFT-002) — default ON, opt-out via env
        from claude_memory.stats import create_accumulator  # noqa: PLC0415

        self._stats = create_accumulator()
