from brain.Brain import Brain
from core.Application import HypatiaApplication
from core.Logger import Logger


def main() -> None:
    app = HypatiaApplication()
    app.start()

    container = app.bootstrap.container
    logger = container.resolve(Logger)
    brain = container.resolve(Brain)
    response = brain.process("hello")

    logger.info(f"Brain response: {response.message}")
    logger.info(f"Brain intent: {response.intent}")
    logger.info(f"Conversation memories: {response.memory_count + 1}")


if __name__ == "__main__":
    main()
