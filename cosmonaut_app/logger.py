"""Logging configuration for COSMONAUT App.

``PostgreSQLHandler``, ``postgres_params`` and ``format_string`` come from
``cosmo_suite.logger``.

The filter and the three ``get_logger_config_*`` builders stay local, because
``cosmo_suite.logger.ExcludeSubmodulesFilter`` hard-codes its excluded-package list
(``watchdog``, ``selenium``) with no way to extend it, and cosmonaut has to silence
four more (matplotlib, PIL, pyogrio, rasterio) or every raster/plot operation floods
the Postgres log table. The framework's ``_build_stream_config`` references its own
filter class, so the builders have to be local too. The seam to push into the
framework is an excluded-packages parameter; until then this is duplication with a
reason, not drift.

Also deliberate: ``get_logger_config_web()`` takes no argument here. The framework's
signature takes ``debug`` and ignores it.
"""

import logging

from cosmo_suite.logger import format_string, postgres_params


class ExcludeSubmodulesFilter(logging.Filter):
    """Exclude submodules."""

    def filter(self, record):
        """Filter."""
        excluded_packages = [
            "matplotlib",
            "PIL",
            "pyogrio",
            "rasterio",
            "watchdog",
            "selenium",
        ]
        excluded_modules = [
            "_internal",
        ]
        return (
            not any(record.name.startswith(package) for package in excluded_packages)
            and record.module not in excluded_modules
        )


def get_logger_config_computation(log_file_path):
    """Get the config dict for the computation logger.

    This configures logging to write to a file in the job's working directory
    during background task execution. No postgres handler — computation logs
    go to the job-specific log file only.

    Args:
        log_file_path: Path to the log file to write to

    Returns:
        dict: Logging configuration dictionary for use with dictConfig()
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"exclude_submodules": {"()": ExcludeSubmodulesFilter}},
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": log_file_path,
                "mode": "w",
                "filters": ["exclude_submodules"],
            },
        },
        "formatters": {
            "detailed": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            },
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["file"],
            "filters": ["exclude_submodules"],
        },
    }


def _build_stream_config(stream, disable_existing_loggers):
    """Build a logging config that writes to a stream and PostgreSQL.

    Args:
        stream: The stream ext:// URI for the StreamHandler
            (e.g. "ext://sys.stderr" or "ext://sys.__stderr__")
        disable_existing_loggers: Whether to disable loggers not in the config.
            False preserves Celery's own handlers; True is the default for the
            web process in production.

    Returns:
        dict: Logging configuration dictionary for use with dictConfig()
    """
    return {
        "version": 1,
        "disable_existing_loggers": disable_existing_loggers,
        "formatters": {
            "default": {"format": format_string},
            "message_only": {"format": "%(message)s"},
        },
        "filters": {"exclude_submodules": {"()": ExcludeSubmodulesFilter}},
        "handlers": {
            "stream": {
                "class": "logging.StreamHandler",
                "stream": stream,
                "formatter": "default",
                "filters": ["exclude_submodules"],
                "level": "DEBUG",
            },
            "postgres": {
                "class": "cosmo_suite.logger.PostgreSQLHandler",
                "level": "DEBUG",
                "formatter": "message_only",
                "filters": ["exclude_submodules"],
                "connection_params": postgres_params,
            },
        },
        "root": {
            "handlers": ["stream", "postgres"],
            "level": "DEBUG",
            "filters": ["exclude_submodules"],
        },
    }


def get_logger_config_web():
    """Get the logging configuration for the web process (Dash/Flask).

    Writes to sys.stderr and PostgreSQL.

    Returns:
        dict: Logging configuration dictionary for use with dictConfig()
    """
    return _build_stream_config(
        stream="ext://sys.stderr",
        disable_existing_loggers=False,
    )


def get_logger_config_worker():
    """Get the logging configuration for use inside a Celery worker task.

    Writes to sys.__stderr__ (the real stderr fd) instead of sys.stderr.
    This is necessary because Celery's prefork pool replaces sys.stderr
    with a LoggingProxy, and writing to it from a StreamHandler causes
    circular recursion.

    disable_existing_loggers is always False to preserve Celery's own
    logging handlers.

    Returns:
        dict: Logging configuration dictionary for use with dictConfig()
    """
    return _build_stream_config(
        stream="ext://sys.__stderr__",
        disable_existing_loggers=False,
    )
