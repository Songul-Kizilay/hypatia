import os
from math import isfinite
from pathlib import Path
from urllib.parse import urlparse

from brain.Brain import Brain
from cognition.CognitiveEngine import CognitiveEngine
from cognition.TrustedDeferredExecutionControlService import (
    TrustedDeferredExecutionControlService,
)
from core.Config import Config
from core.DependencyContainer import DependencyContainer
from core.ExclusiveStoreOwnership import claim, claim_directory
from core.Logger import Logger
from core.RuntimeOptIn import (
    background_research_enabled,
    curiosity_enabled,
    failure_memory_enabled,
    hypothesis_engine_enabled,
    plan_authorization_enabled,
    reflection_enabled,
    research_execution_persistence_enabled,
    vulnerability_graph_enabled,
)
from eventbus.EventBus import EventBus
from knowledge.JsonFileKnowledgeRelationStore import JsonFileKnowledgeRelationStore
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.HypatiaSystemPrompt import HYPATIA_DEFAULT_SYSTEM_PROMPT
from llm.LLMEndpointPolicy import is_loopback_llm_endpoint
from llm.LLMEnvironmentSettings import (
    load_llm_process_environment_settings,
    load_llm_process_history_max_turns,
    load_llm_process_system_prompt,
)
from llm.LLMProvider import LLMProvider
from llm.LLMRuntimeActivator import activate_llm
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.JsonFileSemanticEmbeddingCache import JsonFileSemanticEmbeddingCache
from memory.KeywordLearnedMemorySelector import KeywordLearnedMemorySelector
from memory.LearnedMemoryCandidateExtractor import LearnedMemoryCandidateExtractor
from memory.LearnedMemorySelector import LearnedMemorySelector
from memory.LLMLearnedMemoryCandidateExtractor import (
    LLMLearnedMemoryCandidateExtractor,
)
from memory.MemoryManager import MemoryManager
from memory.OllamaEmbeddingProvider import OllamaEmbeddingProvider
from memory.RankedKeywordLearnedMemorySelector import (
    RankedKeywordLearnedMemorySelector,
)
from memory.SemanticMemoryIndexBuilder import (
    DEFAULT_SEMANTIC_REBUILD_PROVIDER_CALLS,
    DEFAULT_SEMANTIC_REBUILD_TIMEOUT_SECONDS,
    MAX_SEMANTIC_REBUILD_PROVIDER_CALLS,
    MAX_SEMANTIC_REBUILD_TIMEOUT_SECONDS,
    SemanticMemoryIndexBuilder,
)
from memory.SemanticMemoryIndexRuntime import SemanticMemoryIndexRuntime
from memory.UrllibOllamaEmbeddingTransport import (
    DEFAULT_TIMEOUT_SECONDS,
    UrllibOllamaEmbeddingTransport,
)
from planner.Planner import Planner
from research.CrossrefResearchSourceDiscoveryProvider import (
    CrossrefResearchSourceDiscoveryProvider,
)
from research.HttpResearchSourceFetcher import HttpResearchSourceFetcher
from research.JsonFileBackgroundTaskStore import (
    JsonFileBackgroundTaskStore,
)
from research.JsonFileCuriosityQuestionStore import (
    JsonFileCuriosityQuestionStore,
)
from research.JsonFileDeferredExecutionGrantStore import (
    JsonFileDeferredExecutionGrantStore,
)
from research.JsonFileFailureLessonStore import (
    JsonFileFailureLessonStore,
)
from research.JsonFileHypothesisStore import (
    JsonFileHypothesisStore,
)
from research.JsonFileReflectionReportStore import (
    JsonFileReflectionReportStore,
)
from research.JsonFileResearchExecutionStore import (
    JsonFileResearchExecutionStore,
)
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.JsonFileResearchSourceContentStore import (
    JsonFileResearchSourceContentStore,
)
from research.LLMResearchClaimContradictionProposalProvider import (
    LLMResearchClaimContradictionProposalProvider,
)
from research.NvdResearchSourceDiscoveryProvider import (
    NvdResearchSourceDiscoveryProvider,
)
from research.NvdResearchSourceFetcher import NvdResearchSourceFetcher
from research.ResearchClaimContradictionProposalProvider import (
    ResearchClaimContradictionProposalProvider,
)
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEvidenceIntegrityAuditor import ResearchEvidenceIntegrityAuditor
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceContentRestorer import ResearchSourceContentRestorer
from research.ResearchSourceDiscoveryProvider import ResearchSourceDiscoveryProvider
from research.ResearchSourceFetcher import ResearchSourceFetcher
from research.RoutedResearchSourceFetcher import RoutedResearchSourceFetcher
from response.ResponseComposer import ResponseComposer
from security.JsonFileVulnerabilityGraphStore import (
    JsonFileVulnerabilityGraphStore,
)
from session.JsonFileSessionStore import JsonFileSessionStore
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

DEFAULT_LEARNED_MEMORY_SELECTOR_LIMIT = 8


class Bootstrap:
    def __init__(
        self,
        memory_path: Path | None = None,
        session_path: Path | None = None,
        knowledge_relation_path: Path | None = None,
        research_run_path: Path | None = None,
        llm_provider: LLMProvider | None = None,
        llm_config: LLMRuntimeConfig | None = None,
        llm_api_key: str | None = None,
        llm_system_prompt: str | None = None,
        llm_history_max_turns: int | None = None,
        learned_memory_candidate_extractor: (
            LearnedMemoryCandidateExtractor | None
        ) = None,
        learned_memory_context_limit: int | None = None,
        learned_memory_selector: LearnedMemorySelector | None = None,
        semantic_memory_index_runtime: SemanticMemoryIndexRuntime | None = None,
        chat_semantic_memory_enabled: bool = False,
        research_source_fetcher: ResearchSourceFetcher | None = None,
        research_source_discovery_provider: (
            ResearchSourceDiscoveryProvider | None
        ) = None,
        research_source_discovery_providers: (
            dict[ResearchDiscoveryProviderName, ResearchSourceDiscoveryProvider] | None
        ) = None,
        research_claim_contradiction_proposal_provider: (
            ResearchClaimContradictionProposalProvider | None
        ) = None,
        research_source_content_path: Path | None = None,
    ) -> None:
        self._memory_path = memory_path
        self._session_path = session_path
        self._knowledge_relation_path = knowledge_relation_path
        self._research_run_path = research_run_path
        self._research_source_content_path = research_source_content_path
        self._llm_provider = llm_provider
        self._llm_config = llm_config
        self._llm_api_key = llm_api_key
        self._llm_system_prompt = llm_system_prompt
        self._llm_history_max_turns = llm_history_max_turns
        self._learned_memory_candidate_extractor = learned_memory_candidate_extractor
        self._learned_memory_context_limit = learned_memory_context_limit
        self._learned_memory_selector = learned_memory_selector
        self._semantic_memory_index_runtime = semantic_memory_index_runtime
        self._chat_semantic_memory_enabled = chat_semantic_memory_enabled
        self._research_source_fetcher = research_source_fetcher
        self._research_source_discovery_provider = research_source_discovery_provider
        self._research_source_discovery_providers = (
            research_source_discovery_providers or {}
        )
        self._research_claim_contradiction_proposal_provider = (
            research_claim_contradiction_proposal_provider
        )

    @classmethod
    def from_process_environment(
        cls,
        memory_path: Path | None = None,
        session_path: Path | None = None,
        knowledge_relation_path: Path | None = None,
        research_run_path: Path | None = None,
        research_source_content_path: Path | None = None,
    ) -> Bootstrap:
        """Create Bootstrap with LLM settings loaded from the process environment."""
        llm_config, llm_api_key = load_llm_process_environment_settings()
        llm_system_prompt = load_llm_process_system_prompt()
        llm_history_max_turns = load_llm_process_history_max_turns()
        learned_memory_context_limit = cls._load_process_learned_memory_context_limit()
        learned_memory_selector = cls._load_process_learned_memory_selector()
        chat_semantic_memory_enabled = cls._load_process_chat_semantic_memory_enabled()
        semantic_memory_index_runtime = cls._load_process_semantic_memory_index_runtime(
            cls._semantic_embedding_cache_path(memory_path)
        )
        research_source_discovery_provider = (
            cls._load_process_research_source_discovery_provider()
        )
        if llm_system_prompt is None:
            llm_system_prompt = HYPATIA_DEFAULT_SYSTEM_PROMPT

        return cls(
            memory_path=memory_path,
            session_path=session_path,
            knowledge_relation_path=knowledge_relation_path,
            research_run_path=research_run_path,
            research_source_content_path=research_source_content_path,
            llm_config=llm_config,
            llm_api_key=llm_api_key,
            llm_system_prompt=llm_system_prompt,
            llm_history_max_turns=llm_history_max_turns,
            learned_memory_context_limit=learned_memory_context_limit,
            learned_memory_selector=learned_memory_selector,
            semantic_memory_index_runtime=semantic_memory_index_runtime,
            chat_semantic_memory_enabled=chat_semantic_memory_enabled,
            research_source_discovery_provider=research_source_discovery_provider,
            research_source_discovery_providers=(
                Bootstrap._load_process_research_source_discovery_providers()
            ),
        )

    @staticmethod
    def _load_process_research_source_discovery_provider() -> (
        ResearchSourceDiscoveryProvider | None
    ):
        """Return the provider a step uses when it names none of its own.

        Plans approved before providers were nameable meant this one, so it
        stays the default rather than becoming a second way to choose. Setting
        it to `disabled` removes discovery entirely, which also removes every
        provider: there is no arrangement where turning discovery off leaves one
        of them reachable.
        """
        provider_name = os.environ.get(
            "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER",
            "crossref",
        )
        if provider_name == "crossref":
            return CrossrefResearchSourceDiscoveryProvider()
        if provider_name == "nvd":
            return NvdResearchSourceDiscoveryProvider(
                api_key=Bootstrap._load_process_nvd_api_key()
            )
        if provider_name == "disabled":
            return None
        raise ValueError(
            "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER must be "
            "'crossref', 'nvd', or 'disabled'."
        )

    @staticmethod
    def _load_process_research_source_discovery_providers() -> (
        dict[ResearchDiscoveryProviderName, ResearchSourceDiscoveryProvider]
    ):
        """Return every provider an approved step may name.

        Both are constructed when discovery is enabled at all, because which one
        a step contacts is decided by the plan the operator approved rather than
        by process configuration. Registering only the default would mean an
        approval naming the other one failed for a reason that had nothing to do
        with what was authorized.
        """
        if (
            os.environ.get("HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER", "crossref")
            == "disabled"
        ):
            return {}
        return {
            ResearchDiscoveryProviderName.CROSSREF: (
                CrossrefResearchSourceDiscoveryProvider()
            ),
            ResearchDiscoveryProviderName.NVD: NvdResearchSourceDiscoveryProvider(
                api_key=Bootstrap._load_process_nvd_api_key()
            ),
        }

    @staticmethod
    def _load_process_nvd_api_key() -> str | None:
        """Read the optional NVD key from one place and nowhere else.

        A key is not a feature flag, so it does not live with the opt-ins. NVD
        answers unauthenticated requests at a lower allowance, so an absent key
        is a working configuration rather than a broken one — and the value is
        never stored, logged, displayed, or put in a URL.
        """
        raw_key = os.environ.get("HYPATIA_NVD_API_KEY")
        if raw_key is None or not raw_key.strip():
            return None
        return raw_key.strip()

    @staticmethod
    def _load_process_learned_memory_context_limit() -> int | None:
        raw_limit = os.environ.get("HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT")
        if raw_limit is None:
            return None
        if not raw_limit.isascii() or not raw_limit.isdecimal():
            raise ValueError(
                "HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT must be a "
                "non-negative integer."
            )
        return int(raw_limit)

    @staticmethod
    def _load_process_learned_memory_selector() -> LearnedMemorySelector | None:
        raw_selector = os.environ.get("HYPATIA_LEARNED_MEMORY_SELECTOR")
        if raw_selector is None:
            return RankedKeywordLearnedMemorySelector(
                limit=Bootstrap._resolve_ranked_learned_memory_selector_limit()
            )
        if raw_selector == "none":
            return None
        if raw_selector == "keyword":
            return KeywordLearnedMemorySelector()
        if raw_selector == "ranked":
            return RankedKeywordLearnedMemorySelector(
                limit=Bootstrap._load_process_ranked_learned_memory_selector_limit()
            )
        raise ValueError(
            "HYPATIA_LEARNED_MEMORY_SELECTOR must be 'keyword', 'ranked', or 'none'."
        )

    @staticmethod
    def _resolve_ranked_learned_memory_selector_limit() -> int:
        """Bound the default learned-memory context without discarding config."""
        configured_limit = (
            Bootstrap._load_process_ranked_learned_memory_selector_limit()
        )
        if configured_limit is None:
            return DEFAULT_LEARNED_MEMORY_SELECTOR_LIMIT
        return configured_limit

    @staticmethod
    def _load_process_ranked_learned_memory_selector_limit() -> int | None:
        raw_limit = os.environ.get("HYPATIA_RANKED_LEARNED_MEMORY_SELECTOR_LIMIT")
        if raw_limit is None:
            return None
        if not raw_limit.isascii() or not raw_limit.isdecimal():
            raise ValueError(
                "HYPATIA_RANKED_LEARNED_MEMORY_SELECTOR_LIMIT must be a "
                "non-negative integer."
            )
        return int(raw_limit)

    @staticmethod
    def _load_process_chat_semantic_memory_enabled() -> bool:
        """Keep semantic chat retrieval opt-in and off by default."""
        return os.environ.get("HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED") == "true"

    @staticmethod
    def _load_process_semantic_memory_index_runtime(
        embedding_cache_path: Path,
    ) -> SemanticMemoryIndexRuntime | None:
        if os.environ.get("HYPATIA_SEMANTIC_MEMORY_ENABLED") != "true":
            return None

        endpoint = os.environ.get(
            "HYPATIA_SEMANTIC_MEMORY_OLLAMA_ENDPOINT",
            "http://localhost:11434/api/embed",
        )
        model = os.environ.get(
            "HYPATIA_SEMANTIC_MEMORY_OLLAMA_MODEL",
            "embeddinggemma",
        )
        if not endpoint.strip():
            raise ValueError("HYPATIA_SEMANTIC_MEMORY_OLLAMA_ENDPOINT cannot be empty.")
        parsed_endpoint = urlparse(endpoint)
        if parsed_endpoint.scheme != "http" or parsed_endpoint.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError(
                "HYPATIA_SEMANTIC_MEMORY_OLLAMA_ENDPOINT must be a local HTTP "
                "endpoint."
            )
        if not model.strip():
            raise ValueError("HYPATIA_SEMANTIC_MEMORY_OLLAMA_MODEL cannot be empty.")
        timeout_seconds = Bootstrap._load_process_semantic_memory_timeout_seconds()
        max_rebuild_provider_calls = (
            Bootstrap._load_process_semantic_rebuild_provider_calls()
        )
        max_rebuild_seconds = Bootstrap._load_process_semantic_rebuild_timeout_seconds()

        provider = OllamaEmbeddingProvider(
            endpoint=endpoint,
            model=model,
            transport=UrllibOllamaEmbeddingTransport(timeout_seconds=timeout_seconds),
        )
        embedding_cache = None
        if os.environ.get("HYPATIA_SEMANTIC_MEMORY_PERSIST_EMBEDDINGS") == "true":
            embedding_cache = JsonFileSemanticEmbeddingCache(
                embedding_cache_path,
                provider_key=f"ollama:{endpoint}:{model}",
            )
        return SemanticMemoryIndexRuntime(
            SemanticMemoryIndexBuilder(
                provider,
                embedding_cache,
                max_rebuild_provider_calls=max_rebuild_provider_calls,
                max_rebuild_seconds=max_rebuild_seconds,
            )
        )

    @staticmethod
    def _load_process_semantic_memory_timeout_seconds() -> float:
        raw_timeout = os.environ.get("HYPATIA_SEMANTIC_MEMORY_OLLAMA_TIMEOUT_SECONDS")
        if raw_timeout is None:
            return DEFAULT_TIMEOUT_SECONDS
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError as error:
            raise ValueError(
                "HYPATIA_SEMANTIC_MEMORY_OLLAMA_TIMEOUT_SECONDS must be a "
                "positive finite number."
            ) from error
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError(
                "HYPATIA_SEMANTIC_MEMORY_OLLAMA_TIMEOUT_SECONDS must be a "
                "positive finite number."
            )
        return timeout_seconds

    @staticmethod
    def _load_process_semantic_rebuild_provider_calls() -> int:
        raw_budget = os.environ.get(
            "HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS"
        )
        if raw_budget is None:
            return DEFAULT_SEMANTIC_REBUILD_PROVIDER_CALLS
        if not raw_budget.isascii() or not raw_budget.isdecimal():
            raise ValueError(
                "HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS must be a "
                "non-negative integer."
            )
        budget = int(raw_budget)
        if budget > MAX_SEMANTIC_REBUILD_PROVIDER_CALLS:
            raise ValueError(
                "HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS cannot exceed "
                f"{MAX_SEMANTIC_REBUILD_PROVIDER_CALLS}."
            )
        return budget

    @staticmethod
    def _load_process_semantic_rebuild_timeout_seconds() -> float:
        raw_timeout = os.environ.get("HYPATIA_SEMANTIC_MEMORY_REBUILD_TIMEOUT_SECONDS")
        if raw_timeout is None:
            return DEFAULT_SEMANTIC_REBUILD_TIMEOUT_SECONDS
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError as error:
            raise ValueError(
                "HYPATIA_SEMANTIC_MEMORY_REBUILD_TIMEOUT_SECONDS must be a "
                "positive finite number."
            ) from error
        if (
            not isfinite(timeout_seconds)
            or timeout_seconds <= 0
            or timeout_seconds > MAX_SEMANTIC_REBUILD_TIMEOUT_SECONDS
        ):
            raise ValueError(
                "HYPATIA_SEMANTIC_MEMORY_REBUILD_TIMEOUT_SECONDS must be greater "
                f"than 0 and no greater than {MAX_SEMANTIC_REBUILD_TIMEOUT_SECONDS:g}."
            )
        return timeout_seconds

    def initialize(self) -> None:
        # Claimed before a single writable store is opened. A second process
        # must be refused while it can still do no harm, not after it has
        # already loaded sessions and memory and is one save away from
        # replacing somebody else's.
        self._claim_writable_directories()
        config = Config()
        logger = Logger()
        container = DependencyContainer()
        event_bus = EventBus()
        session_store = JsonFileSessionStore(
            self._session_path or self._default_session_path()
        )
        session_manager = SessionManager(event_bus, session_store)
        session_manager.load()
        memory_store = JsonFileMemoryStore(
            self._memory_path or self._default_memory_path()
        )
        memory_manager = MemoryManager(event_bus, memory_store)
        memory_manager.load()
        semantic_memory_index_runtime = self._semantic_memory_index_runtime
        if semantic_memory_index_runtime is not None:
            semantic_memory_index_runtime.attach(event_bus)
        session_rename_service = SessionRenameTransactionService(
            session_manager=session_manager,
            memory_manager=memory_manager,
            event_bus=event_bus,
        )
        relation_store = JsonFileKnowledgeRelationStore(
            self._knowledge_relation_path
            or self._knowledge_relation_store_path(self._memory_path)
        )
        knowledge_engine = KnowledgeEngine(relation_store=relation_store)
        research_run_store = JsonFileResearchRunStore(
            self._research_run_path or self._research_run_store_path(self._memory_path)
        )
        research_run_manager = ResearchRunManager(research_run_store)
        research_run_manager.load()
        research_execution_store = self._research_execution_store()
        background_task_store = self._background_task_store()
        deferred_execution_grant_store = self._deferred_execution_grant_store()
        curiosity_question_store = self._curiosity_question_store()
        reflection_report_store = self._reflection_report_store()
        failure_lesson_store = self._failure_lesson_store()
        hypothesis_store = self._hypothesis_store()
        plan_authorization_store = self._plan_authorization_store()
        vulnerability_graph_store = self._vulnerability_graph_store()
        research_source_content_store = JsonFileResearchSourceContentStore(
            self._research_source_content_path
            or self._research_source_content_store_path(
                self._memory_path,
                self._research_run_path,
            )
        )
        research_source_content_restorer = ResearchSourceContentRestorer(
            research_source_content_store,
            knowledge_engine,
        )
        research_source_content_restoration_status = (
            research_source_content_restorer.restore(research_run_manager.list())
        )
        research_evidence_integrity_auditor = ResearchEvidenceIntegrityAuditor(
            knowledge_engine
        )
        # An NVD record is named by a page that does not contain it, so the
        # accepted-source loader routes those to the API the record was
        # discovered through. Every other URL keeps the generic HTTPS path. An
        # injected fetcher is left exactly as given, so a test that supplies one
        # still gets that one and only that one.
        research_source_fetcher = self._research_source_fetcher or (
            RoutedResearchSourceFetcher(
                HttpResearchSourceFetcher(),
                NvdResearchSourceFetcher(
                    NvdResearchSourceDiscoveryProvider(
                        api_key=Bootstrap._load_process_nvd_api_key()
                    )
                ),
            )
        )
        planner = Planner()
        response_composer = ResponseComposer()
        llm_provider = self._configured_llm_provider()
        research_claim_contradiction_proposal_provider = (
            self._research_claim_contradiction_proposal_provider
        )
        if (
            research_claim_contradiction_proposal_provider is None
            and llm_provider is not None
        ):
            research_claim_contradiction_proposal_provider = (
                LLMResearchClaimContradictionProposalProvider(llm_provider)
            )
        learned_memory_candidate_extractor = self._learned_memory_candidate_extractor
        if (
            learned_memory_candidate_extractor is None
            and os.environ.get("HYPATIA_LEARNING_ENABLED") == "true"
            and llm_provider is not None
        ):
            learned_memory_candidate_extractor = LLMLearnedMemoryCandidateExtractor(
                llm_provider
            )
        cognitive_engine = CognitiveEngine(
            knowledge_engine,
            memory_manager,
            planner,
            event_bus,
            response_composer,
            session_manager,
            session_rename_service,
            llm_provider=llm_provider,
            llm_history_max_turns=self._llm_history_max_turns,
            learned_memory_candidate_extractor=learned_memory_candidate_extractor,
            learned_memory_context_limit=self._learned_memory_context_limit,
            learned_memory_selector=self._learned_memory_selector,
            semantic_memory_index_runtime=semantic_memory_index_runtime,
            chat_semantic_memory_enabled=self._chat_semantic_memory_enabled,
            research_source_fetcher=research_source_fetcher,
            research_run_manager=research_run_manager,
            research_execution_store=research_execution_store,
            background_task_store=background_task_store,
            deferred_execution_grant_store=deferred_execution_grant_store,
            curiosity_question_store=curiosity_question_store,
            reflection_report_store=reflection_report_store,
            failure_lesson_store=failure_lesson_store,
            hypothesis_store=hypothesis_store,
            plan_authorization_store=plan_authorization_store,
            vulnerability_graph_store=vulnerability_graph_store,
            research_source_discovery_provider=(
                self._research_source_discovery_provider
            ),
            research_source_discovery_providers=(
                self._research_source_discovery_providers
            ),
            research_claim_contradiction_proposal_provider=(
                research_claim_contradiction_proposal_provider
            ),
            research_source_content_store=research_source_content_store,
            research_source_content_restoration_status=(
                research_source_content_restoration_status
            ),
            research_evidence_integrity_auditor=(research_evidence_integrity_auditor),
        )
        brain = Brain(cognitive_engine, memory_manager, event_bus)
        deferred_execution_control = (
            TrustedDeferredExecutionControlService(
                cognitive_engine,
                deferred_execution_grant_store,
            )
            if deferred_execution_grant_store is not None
            else None
        )

        container.register(config)
        container.register(logger)
        container.register(event_bus)
        container.register(session_store)
        container.register(session_manager)
        container.register(memory_store)
        container.register(memory_manager)
        container.register(relation_store)
        if semantic_memory_index_runtime is not None:
            container.register(semantic_memory_index_runtime)
        container.register(session_rename_service)
        container.register(knowledge_engine)
        container.register(research_run_store)
        container.register(research_run_manager)
        container.register(research_source_content_store)
        container.register(research_source_content_restorer)
        container.register(research_source_content_restoration_status)
        container.register(research_evidence_integrity_auditor)
        container.register(research_source_fetcher)
        if self._research_source_discovery_provider is not None:
            container.register(self._research_source_discovery_provider)
        if research_claim_contradiction_proposal_provider is not None:
            container.register(research_claim_contradiction_proposal_provider)
        container.register(response_composer)
        container.register(cognitive_engine)
        container.register(brain)
        container.register(planner)
        if deferred_execution_control is not None:
            container.register(deferred_execution_control)

        self.container = container

        if semantic_memory_index_runtime is not None:
            start_result = semantic_memory_index_runtime.start_refresh(memory_manager)
            if start_result == "failed":
                logger.warning("Semantic Memory Runtime Unavailable")

        logger.info("Configuration Loaded")
        logger.info("Logger Initialized")
        logger.info("Dependency Container Ready")
        logger.info("Event Bus Ready")
        logger.info("Session Manager Ready")
        logger.info("Memory Manager Ready")
        logger.info("Session Rename Service Ready")
        logger.info("Knowledge Engine Ready")
        logger.info("Research Source Content Ready")
        logger.info("Response Composer Ready")
        logger.info("Cognitive Engine Ready")
        logger.info("Brain Ready")
        logger.info("Planner Ready")

        event_bus.emit(
            "system.bootstrap.completed",
            {"status": "ready"},
            source="bootstrap",
        )

    def _writable_directories(self) -> tuple[Path, ...]:
        """Return every directory this runtime will write canonical state into.

        Derived from the same path rules the stores themselves use, so the list
        cannot drift from what is actually opened. Research keeps its many
        stores beside the run snapshot, which is why one entry covers runs,
        executions, background tasks, curiosity, reflections, lessons,
        approvals, hypotheses and the vulnerability graph together.
        """
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        paths = (
            self._session_path or self._default_session_path(),
            self._memory_path or self._default_memory_path(),
            self._knowledge_relation_path
            or self._knowledge_relation_store_path(self._memory_path),
            run_path,
            self._research_source_content_store_path(
                self._memory_path,
                self._research_run_path,
            ),
        )
        directories: list[Path] = []
        for path in paths:
            parent = path.parent
            if parent not in directories:
                directories.append(parent)
        return tuple(directories)

    def _claim_writable_directories(self) -> None:
        """Own every directory this runtime writes, or refuse to start."""
        for directory in self._writable_directories():
            claim_directory(directory)

    @staticmethod
    def _default_memory_path() -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "data" / "memory" / "memory.json"

    @classmethod
    def _semantic_embedding_cache_path(cls, memory_path: Path | None) -> Path:
        """Keep optional derived embeddings beside the selected memory snapshot."""
        resolved_memory_path = memory_path or cls._default_memory_path()
        return resolved_memory_path.with_name("semantic_embeddings.json")

    @staticmethod
    def _default_session_path() -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "data" / "sessions" / "sessions.json"

    @staticmethod
    def _default_knowledge_relation_path() -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "data" / "knowledge" / "relations.json"

    def _research_execution_store(self) -> JsonFileResearchExecutionStore | None:
        """Create the execution store only when persistence is opted in.

        Default off, so an unset environment keeps execution state ephemeral and
        behavior identical to a runtime without this store.
        """
        if not research_execution_persistence_enabled(os.environ):
            return None
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        store_path = run_path.with_name("research_executions.json")
        # Claimed before the store is handed out, because two processes sharing
        # one execution store do not race over a field: each replaces the whole
        # document, so the later writer erases the other's executions.
        claim(store_path)
        return JsonFileResearchExecutionStore(store_path)

    def _background_task_store(self) -> JsonFileBackgroundTaskStore | None:
        """Create the task store only when background research is opted in.

        Default off, so an unset environment schedules nothing and behaves
        exactly like a runtime without a scheduler.
        """
        if not background_research_enabled(os.environ):
            return None
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        return JsonFileBackgroundTaskStore(
            run_path.with_name("research_background_tasks.json")
        )

    def _deferred_execution_grant_store(
        self,
    ) -> JsonFileDeferredExecutionGrantStore | None:
        """Keep deferred authority separate and opt-in with the scheduler."""
        if not background_research_enabled(os.environ):
            return None
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        return JsonFileDeferredExecutionGrantStore(
            run_path.with_name("research_deferred_execution_grants.json")
        )

    def _curiosity_question_store(self) -> JsonFileCuriosityQuestionStore | None:
        """Create the question store only when curiosity is opted in.

        Default off, so an unset environment proposes nothing durable and
        behaves exactly like a runtime without a curiosity engine.
        """
        if not curiosity_enabled(os.environ):
            return None
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        return JsonFileCuriosityQuestionStore(
            run_path.with_name("research_curiosity_questions.json")
        )

    def _reflection_report_store(self) -> JsonFileReflectionReportStore | None:
        """Create the reflection store only when reflection is opted in.

        Default off, so an unset environment keeps no reflection history and
        behaves exactly like a runtime without a reflection engine.
        """
        if not reflection_enabled(os.environ):
            return None
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        return JsonFileReflectionReportStore(
            run_path.with_name("research_reflections.json")
        )

    def _failure_lesson_store(self) -> JsonFileFailureLessonStore | None:
        """Create the lesson store only when failure memory is opted in.

        Default off, so an unset environment remembers nothing and behaves
        exactly like a runtime without a failure memory.
        """
        if not failure_memory_enabled(os.environ):
            return None
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        return JsonFileFailureLessonStore(
            run_path.with_name("research_failure_lessons.json")
        )

    def _plan_authorization_store(
        self,
    ) -> JsonFileResearchPlanAuthorizationStore | None:
        """Create the approval store only when plan authorization is opted in.

        Default off, so an unset environment records no approvals and behaves
        exactly like a runtime without an approval surface.
        """
        if not plan_authorization_enabled(os.environ):
            return None
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        return JsonFileResearchPlanAuthorizationStore(
            run_path.with_name("research_plan_authorizations.json")
        )

    def _hypothesis_store(self) -> JsonFileHypothesisStore | None:
        """Create the hypothesis store only when hypotheses are opted in.

        Default off, so an unset environment keeps no hypotheses and behaves
        exactly like a runtime without a hypothesis engine.
        """
        if not hypothesis_engine_enabled(os.environ):
            return None
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        return JsonFileHypothesisStore(run_path.with_name("research_hypotheses.json"))

    def _vulnerability_graph_store(self) -> JsonFileVulnerabilityGraphStore | None:
        """Create the taxonomy store only when the graph is opted in.

        Default off, so an unset environment knows no weakness taxonomy and
        behaves exactly like a runtime without one.
        """
        if not vulnerability_graph_enabled(os.environ):
            return None
        run_path = self._research_run_path or self._research_run_store_path(
            self._memory_path
        )
        return JsonFileVulnerabilityGraphStore(
            run_path.with_name("vulnerability_families.json")
        )

    @staticmethod
    def _default_research_run_path() -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "data" / "research" / "runs.json"

    @staticmethod
    def _default_research_source_content_path() -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "data" / "research" / "content.json"

    @classmethod
    def _knowledge_relation_store_path(cls, memory_path: Path | None) -> Path:
        if memory_path is None:
            return cls._default_knowledge_relation_path()
        return memory_path.with_name("knowledge_relations.json")

    @classmethod
    def _research_run_store_path(cls, memory_path: Path | None) -> Path:
        if memory_path is None:
            return cls._default_research_run_path()
        return memory_path.with_name("research_runs.json")

    @classmethod
    def _research_source_content_store_path(
        cls,
        memory_path: Path | None,
        research_run_path: Path | None,
    ) -> Path:
        if research_run_path is not None:
            return research_run_path.with_name("content.json")
        if memory_path is not None:
            return memory_path.with_name("research_source_content.json")
        return cls._default_research_source_content_path()

    def _configured_llm_provider(self) -> LLMProvider | None:
        if self._llm_provider is not None:
            return self._llm_provider
        if self._llm_config is None or self._llm_config.enabled is False:
            return None
        if not self._llm_config.base_url.strip():
            raise RuntimeError("LLM base URL is required when LLM is enabled.")
        if not self._llm_config.model.strip():
            raise RuntimeError("LLM model is required when LLM is enabled.")
        if (
            self._llm_api_key is None or not self._llm_api_key.strip()
        ) and not is_loopback_llm_endpoint(self._llm_config.base_url):
            raise RuntimeError("LLM API key is required when LLM is enabled.")
        return activate_llm(
            self._llm_config,
            self._llm_api_key,
            system_prompt=self._llm_system_prompt,
        )

    def shutdown(self) -> None:
        logger = self.container.resolve(Logger)
        event_bus = self.container.resolve(EventBus)

        if self._semantic_memory_index_runtime is not None:
            self._semantic_memory_index_runtime.shutdown()

        event_bus.emit(
            "system.shutdown.started",
            source="bootstrap",
        )
        logger.info("Hypatia shutting down...")
