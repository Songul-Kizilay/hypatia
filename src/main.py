from brain.Brain import Brain
from core.Application import HypatiaApplication


def main() -> None:
    app = HypatiaApplication.from_process_environment()
    app.start()

    try:
        container = app.bootstrap.container
        brain = container.resolve(Brain)

        while True:
            try:
                message = input("You: ")
            except KeyboardInterrupt, EOFError:
                break

            if not message.strip():
                continue

            if message == "exit":
                break

            response = brain.process(message)
            print(f"Hypatia: {response.message}")
    finally:
        app.stop()


if __name__ == "__main__":
    main()
