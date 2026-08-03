from brain.Brain import Brain
from core.Config import Config
from core.DependencyContainer import DependencyContainer
from core.Logger import Logger
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner


class Bootstrap:
    def initialize(self) -> None:
        self.container = DependencyContainer()

        config = Config()
        logger = Logger()
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        planner = Planner()

        self.container.register(config)
        self.container.register(logger)
        self.container.register(event_bus)
        self.container.register(memory_manager)
        self.container.register(planner)
        brain = Brain(self.container)
        self.container.register(brain)

        logger.info("Configuration Loaded")
        logger.info("Logger Initialized")
        logger.info("Dependency Container Ready")
        logger.info("Event Bus Ready")
        logger.info("Memory Manager Ready")
        logger.info("Planner Ready")
        logger.info("Brain Ready")

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
