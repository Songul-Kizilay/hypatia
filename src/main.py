from brain.Brain import Brain
from core.Application import HypatiaApplication
from core.Logger import Logger


def main() -> None:
    app = HypatiaApplication.from_process_environment()
    app.start()

    container = app.bootstrap.container
    logger = container.resolve(Logger)
    brain = container.resolve(Brain)

    response = brain.process("Say hello from Hypatia.")
    logger.info(response.message)


if __name__ == "__main__":
    main()
