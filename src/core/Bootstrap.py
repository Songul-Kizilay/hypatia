from brain.Brain import Brain
from cognition.CognitiveEngine import CognitiveEngine
from core.Config import Config
from core.DependencyContainer import DependencyContainer
from core.Logger import Logger
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer


class Bootstrap:
    def initialize(self) -> None:
        config = Config()
        logger = Logger()
        self.container = DependencyContainer()
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
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

        self.container.register(config)
        self.container.register(logger)
        self.container.register(event_bus)
        self.container.register(memory_manager)
        self.container.register(knowledge_engine)
        self.container.register(response_composer)
        self.container.register(cognitive_engine)
        self.container.register(brain)
        self.container.register(planner)

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

    def shutdown(self) -> None:
        logger = self.container.resolve(Logger)
        event_bus = self.container.resolve(EventBus)

        event_bus.emit(
            "system.shutdown.started",
            source="bootstrap",
        )
        logger.info("Hypatia shutting down...")
