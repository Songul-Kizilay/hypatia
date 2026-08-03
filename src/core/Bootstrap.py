from core.Config import Config
from core.Logger import Logger


class Bootstrap:

    def initialize(self):

        self.config = Config()

        self.logger = Logger()

        self.logger.info("Configuration Loaded")

        self.logger.info("Logger Initialized")

        self.logger.info("Bootstrap Finished")

    def shutdown(self):

        self.logger.info("Hypatia shutting down...")