from core.Application import HypatiaApplication
from core.Logger import Logger
from planner.Planner import Planner


def main() -> None:
    app = HypatiaApplication.from_process_environment()
    app.start()

    container = app.bootstrap.container
    logger = container.resolve(Logger)
    planner = container.resolve(Planner)

    plan = planner.create_plan("Read a PDF and summarize it")
    logger.info(f"Generated plan with {plan.task_count()} tasks.")


if __name__ == "__main__":
    main()
