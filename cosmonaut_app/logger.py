"""Logging configuration for COSMONAUT App."""

import datetime
import logging
import sys

from psycopg2 import pool

from cosmonaut_app.config import (
    POSTGRES_NAME,
    POSTGRES_HOST_NAME,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
)

format_string = (
    "[%(asctime)s] [PID:%(process)d] %(levelname)s in %(module)s: %(message)s"
)
postgres_params = {
    "dbname": POSTGRES_NAME,
    "user": POSTGRES_USER,
    "password": POSTGRES_PASSWORD,
    "host": POSTGRES_HOST_NAME,
    "port": POSTGRES_PORT,
}


class PostgreSQLHandler(logging.Handler):
    """A log handler that writes log records to a PostgreSQL database.

    This handler writes all log records to the database with connection pooling
    for better performance and reliability.
    """

    def __init__(self, connection_params):
        """Initialize the handler with PostgreSQL connection parameters.

        Args:
            connection_params (dict): Connection parameters for PostgreSQL
                                     (dbname, user, password, host, port)
        """
        super().__init__()
        self.connection_params = connection_params
        # Create a connection pool for better performance
        # Add keepalive settings to prevent connections from going stale
        pool_params = {
            **connection_params,
            "keepalives": 1,
            "keepalives_idle": 30,  # Start keepalive after 30s idle
            "keepalives_interval": 10,  # Send keepalive every 10s
            "keepalives_count": 5,  # 5 failed keepalives = dead connection
        }
        self.connection_pool = pool.SimpleConnectionPool(
            1,
            10,  # min and max connections
            **pool_params,
        )

    def emit(self, record):
        """Write the log record to the database.

        Args:
            record: The log record to write.
        """
        import psycopg2

        # Get a connection from the pool
        connection = self.connection_pool.getconn()
        connection_is_bad = False

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO logs
                    (timestamp, pid, level, module, message)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        datetime.datetime.fromtimestamp(record.created),
                        record.process,
                        record.levelname,
                        record.module,
                        self.format(record),
                    ),
                )
                connection.commit()
        except psycopg2.OperationalError as e:
            # Connection is bad (timeout, network issue, etc.)
            # Mark it as bad so it's not returned to the pool
            connection_is_bad = True
            print(f"Database connection error (will retry with new connection): {e}")

            # Try once more with a fresh connection
            try:
                new_connection = self.connection_pool.getconn()
                try:
                    with new_connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO logs
                            (timestamp, pid, level, module, message)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                datetime.datetime.fromtimestamp(record.created),
                                record.process,
                                record.levelname,
                                record.module,
                                self.format(record),
                            ),
                        )
                        new_connection.commit()
                finally:
                    self.connection_pool.putconn(new_connection)
            except Exception as retry_error:  # noqa
                print(
                    f"FATAL: Database logging failed after retry. "
                    f"Worker cannot continue without logging capability: {retry_error}"
                )
                # Re-raise to fail the worker - logging is critical
                raise
        except Exception as e:  # noqa
            # Any other database error is also fatal
            print(f"FATAL: Error writing to PostgreSQL: {e}")
            # Re-raise to fail the worker
            raise
        finally:
            # Return the connection to the pool, or close it if it's bad
            if connection_is_bad:
                try:
                    connection.close()
                except Exception:  # noqa
                    pass
                # putconn with close=True tells the pool this connection is bad
                self.connection_pool.putconn(connection, close=True)
            else:
                self.connection_pool.putconn(connection)

    def close(self):
        """Close all database connections when the handler is closed."""
        if hasattr(self, "connection_pool") and self.connection_pool:
            self.connection_pool.closeall()
        super().close()


class ExcludeSubmodulesFilter(logging.Filter):
    """Exclude submodules."""

    def filter(self, record):
        """Filter."""
        # print("NAME:", record.name, "MODULE:", record.module)
        excluded_packages = [
            "matplotlib",
            "PIL",
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
    """Get the config dic for the computation logger.

    This configures logging to write to a file in the job's working directory
    during background task execution.

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


def get_logger_config_web(debug):
    """Get the logging configuration dictionary for the webservice logger.

    This is the standard web/worker logging configuration that logs to console
    and PostgreSQL database.

    Args:
        debug (bool): Whether to enable debug mode logging

    Returns:
        dict: Logging configuration dictionary for use with dictConfig()
    """
    return get_logger_config(debug)


def get_logger_config(debug):
    """Get the logging configuration dictionary for the logger.

    This configuration sets up both console and database logging.

    Args:
        debug (bool): Whether to enable debug mode logging

    Returns:
        dict: Logging configuration dictionary for use with dictConfig()
    """
    # Detect if we're in test environment
    in_tests = "pytest" in sys.modules

    # Base handlers - always include console
    handler_configs = {
        "wsgi": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "default",
            "filters": ["exclude_submodules"],
            "level": "DEBUG",
        },
    }

    # Try to add postgres handler, but skip if connection fails (e.g., during tests)
    try:
        # Test database connection before adding handler
        import psycopg2

        test_conn = psycopg2.connect(**postgres_params, connect_timeout=2)
        test_conn.close()

        # Connection works, add postgres handler
        handler_configs["postgres"] = {
            "class": __name__ + ".PostgreSQLHandler",
            "level": "DEBUG",
            "formatter": "message_only",
            "filters": ["exclude_submodules"],
            "connection_params": postgres_params,
        }
    except Exception as e:
        # Database not available, skip postgres handler
        print(f"Warning: Skipping PostgreSQL logging handler: {e}")

    logging_config = {
        "version": 1,
        "disable_existing_loggers": not in_tests,  # Preserve test loggers
        "formatters": {
            "default": {"format": format_string},
            "message_only": {
                "format": "%(message)s",
            },
        },
        "filters": {"exclude_submodules": {"()": ExcludeSubmodulesFilter}},
        "handlers": handler_configs,
        "root": {
            "handlers": handler_configs.keys(),
            "level": "DEBUG",
            "filters": ["exclude_submodules"],
        },
    }

    return logging_config
