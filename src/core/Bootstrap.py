from pathlib import Path

from brain.Brain import Brain
from cognition.CognitiveEngine import CognitiveEngine
from core.Config import Config
from core.DependencyContainer import DependencyContainer
from core.Logger import Logger
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMProvider import LLMProvider
from llm.LLMRuntimeActivator import activate_llm
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.JsonFileSessionStore import JsonFileSessionStore
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class Bootstrap:
    def __init__(
        self,
        memory_path: Path | None = None,
        session_path: Path | None = None,
        llm_provider: LLMProvider | None = None,
        llm_config: LLMRuntimeConfig | None = None,
        llm_api_key: str | None = None,
    ) -> None:
        self._memory_path = memory_path
        self._session_path = session_path
        self._llm_provider = llm_provider
        self._llm_config = llm_config
        self._llm_api_key = llm_api_key

    def initialize(self) -> None:
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
        session_rename_service = SessionRenameTransactionService(
            session_manager=session_manager,
            memory_manager=memory_manager,
            event_bus=event_bus,
        )
        knowledge_engine = KnowledgeEngine()
        planner = Planner()
        response_composer = ResponseComposer()
        cognitive_engine = CognitiveEngine(
            knowledge_engine,
            memory_manager,
            planner,
            event_bus,
            response_composer,
            session_manager,
            session_rename_service,
            llm_provider=self._configured_llm_provider(),
        )
        brain = Brain(cognitive_engine, memory_manager, event_bus)

        container.register(config)
        container.register(logger)
        container.register(event_bus)
        container.register(session_store)
        container.register(session_manager)
        container.register(memory_store)
        container.register(memory_manager)
        container.register(session_rename_service)
        container.register(knowledge_engine)
        container.register(response_composer)
        container.register(cognitive_engine)
        container.register(brain)
        container.register(planner)

        self.container = container

        logger.info("Configuration Loaded")
        logger.info("Logger Initialized")
        logger.info("Dependency Container Ready")
        logger.info("Event Bus Ready")
        logger.info("Session Manager Ready")
        logger.info("Memory Manager Ready")
        logger.info("Session Rename Service Ready")
        logger.info("Knowledge Engine Ready")
        logger.info("Response Composer Ready")
        logger.info("Cognitive Engine Ready")
        logger.info("Brain Ready")
        logger.info("Planner Ready")

        event_bus.emit(
            "system.bootstrap.completed",
            {"status": "ready"},
            source="bootstrap",
        )

    @staticmethod
    def _default_memory_path() -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "data" / "memory" / "memory.json"

    @staticmethod
    def _default_session_path() -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "data" / "sessions" / "sessions.json"

    def _configured_llm_provider(self) -> LLMProvider | None:
        if self._llm_provider is not None:
            return self._llm_provider
        if self._llm_config is None or self._llm_config.enabled is False:
            return None
        if self._llm_api_key is None or not self._llm_api_key.strip():
            raise RuntimeError("LLM API key is required when LLM is enabled.")
        if self._llm_config.base_url == "":
            raise RuntimeError("LLM base URL is required when LLM is enabled.")
        return activate_llm(self._llm_config, self._llm_api_key)

    def shutdown(self) -> None:
        logger = self.container.resolve(Logger)
        event_bus = self.container.resolve(EventBus)

        event_bus.emit(
            "system.shutdown.started",
            source="bootstrap",
        )
        logger.info("Hypatia shutting down...")
