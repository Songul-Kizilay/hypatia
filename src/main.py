from brain.Brain import Brain
from core.Application import HypatiaApplication
from core.Logger import Logger


def main() -> None:
    app = HypatiaApplication.from_process_environment()
    app.start()

    container = app.bootstrap.container
    logger = container.resolve(Logger)
    brain = container.resolve(Brain)

    while True:
        message = input("You: ")
        if message == "exit":
            break

        response = brain.process(message)
        logger.info(response.message)

    app.stop()


if __name__ == "__main__":
    main()
