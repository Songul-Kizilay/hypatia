from brain.Brain import Brain
from core.Application import HypatiaApplication
from core.Logger import Logger


def main() -> None:
    app = HypatiaApplication.from_process_environment()
    app.start()

    try:
        container = app.bootstrap.container
        logger = container.resolve(Logger)
        brain = container.resolve(Brain)

        while True:
            try:
                message = input("You: ")
            except KeyboardInterrupt, EOFError:
                break

            if message == "exit":
                break

            response = brain.process(message)
            logger.info(response.message)
    finally:
        app.stop()


if __name__ == "__main__":
    main()
