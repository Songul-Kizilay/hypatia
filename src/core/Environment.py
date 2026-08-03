"""
Operating system detection.
"""

import platform


class Environment:

    @staticmethod
    def os() -> str:

        return platform.system()

    @staticmethod
    def python() -> str:

        return platform.python_version()

    @staticmethod
    def hostname() -> str:

        return platform.node()

    @staticmethod
    def machine() -> str:

        return platform.machine()
