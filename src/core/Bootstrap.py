from pathlib import Path

from brain.Brain import Brain
from cognition.CognitiveEngine import CognitiveEngine
from core.Config import Config
from core.DependencyContainer import DependencyContainer
from core.Logger import Logger
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer


class Bootstrap:
    def __init__(self, memory_path: Path | None = None) -> None:
        self._memory_path = memory_path

    def initialize(self) -> None:
        config = Config()
        logger = Logger()
        container = DependencyContainer()
        event_bus = EventBus()
        memory_store = JsonFileMemoryStore(
            self._memory_path or self._default_memory_path()
        )
        memory_manager = MemoryManager(event_bus, memory_store)
        memory_manager.load()
        knowledge_engine = KnowledgeEngine()
        planner = Planner()
        response_composer = ResponseComposer()
        cognitive_engine = CognitiveEngine(
            knowledge_engine,
            memory_manager,
            planner,
            event_bus,
            response_composer,
        )
        brain = Brain(cognitive_engine, memory_manager, event_bus)

        container.register(config)
        container.register(logger)
        container.register(event_bus)
        container.register(memory_store)
        container.register(memory_manager)
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
        logger.info("Memory Manager Ready")
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

    def shutdown(self) -> None:
        logger = self.container.resolve(Logger)
        event_bus = self.container.resolve(EventBus)

        event_bus.emit(
            "system.shutdown.started",
            source="bootstrap",
        )
        logger.info("Hypatia shutting down...")
