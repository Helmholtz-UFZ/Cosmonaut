"""Setup tests with conditional fixture loading."""

import importlib.resources
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
import urllib.request

import pytest
import redis
from sqlalchemy.exc import OperationalError
from werkzeug.serving import make_server

from cosmonaut_app.config import (
    FLASK_PORT,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)
from cosmonaut_app.db_manager import DataBaseManager


def create_logger():
    """Create a logger with debug level."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logging.getLogger("matplotlib").setLevel(logging.CRITICAL)
    logging.getLogger("PIL").setLevel(logging.CRITICAL)
    logging.getLogger("osgeo").setLevel(logging.ERROR)
    logging.getLogger("rasterio").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("wcs201").setLevel(logging.ERROR)
    return logger


log = create_logger()


def pytest_addoption(parser):
    """Add custom command-line options to pytest.

    This hook registers the --no-services flag which controls
    whether service-dependent fixtures (dash_app, celery_worker) are loaded.
    """
    parser.addoption(
        "--no-services",
        action="store_true",
        default=False,
        help="Skip service-dependent fixtures (assumes services not available)",
    )


def pytest_configure(config):
    """Perform early configuration and service health checks.

    This runs once at the start of the test session, before any tests.
    If --no-services is NOT set, we verify database and Redis connectivity.
    """
    skip_services = config.getoption("--no-services")

    if not skip_services:
        # Give services a moment to fully initialize after health checks
        time.sleep(2)

        # Check PostgreSQL connectivity
        try:
            result = DataBaseManager.check_existence("test")
            logging.info(f"Database connection successful. Test query result: {result}")
        except OperationalError as e:
            logging.error(f"Database connection failed with OperationalError: {e}")
            pytest.exit(f"PostgreSQL not available: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during database check: {e}")
            pytest.exit(f"Database check failed: {e}")

        # Check Redis connectivity
        try:
            # Parse Redis port (handle GitLab CI format: tcp://redis:6379)
            redis_port = REDIS_PORT
            if redis_port and str(redis_port).startswith("tcp://"):
                redis_port = redis_port.split(":")[-1]

            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=int(redis_port),
                db=int(REDIS_DB),
                password=REDIS_PASSWORD if REDIS_PASSWORD else None,
                socket_connect_timeout=5,
            )
            redis_client.ping()
            logging.info("Redis connection successful")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logging.error(f"Redis connection failed: {e}")
            pytest.exit(f"Redis not available: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during Redis check: {e}")
            pytest.exit(f"Redis check failed: {e}")

        # Check rclone can connect to MinIO via S3 protocol
        try:
            from cosmonaut_app.object_storage_manager import setup_remote, create_bucket

            # Configure rclone remote
            setup_remote()

            # Try to create/verify bucket (this uses S3 protocol)
            create_bucket()

            logging.info("rclone MinIO connectivity check passed")
        except Exception as e:
            logging.error(f"rclone MinIO connectivity check failed: {e}")
            pytest.exit(f"MinIO S3 connectivity check failed: {e}")
    else:
        logging.info("Skipping service health checks (--no-services flag set)")


@pytest.fixture
def logger():
    """Create a logger with suppressed external sources.

    This fixture is always available regardless of --no-services flag.
    """
    return create_logger()


def _find_sensor_routing_test_file(substr):
    """Find a test data file from the sensor_routing package by substring."""
    test_data_dir = importlib.resources.files("sensor_routing") / "test_data" / "input"
    for file_path in test_data_dir.iterdir():
        if substr in file_path.name:
            return file_path
    raise FileNotFoundError(
        f"No test data file found containing substring '{substr}' in the name."
    )


@pytest.fixture(scope="session")
def membership_file_path(tmp_path_factory):
    """Fixture that creates a local copy of the membership test data file."""
    original_file = _find_sensor_routing_test_file("membership")
    local_path = tmp_path_factory.mktemp("test_data") / "memberships.csv"
    shutil.copy2(original_file, local_path)
    return local_path


@pytest.fixture(scope="session")
def predictor_file_path(tmp_path_factory):
    """Fixture that creates a local copy of the predictor test data file."""
    original_file = _find_sensor_routing_test_file("predictor")
    local_path = tmp_path_factory.mktemp("test_data") / "predictors.csv"
    shutil.copy2(original_file, local_path)
    return local_path


@pytest.fixture(scope="session")
def dash_app(request):
    """Start the Dash app in a background thread with graceful shutdown.

    Uses werkzeug.serving.make_server() directly to retain a server handle
    for clean shutdown, preventing 'Address already in use' errors.

    This fixture is skipped if --no-services flag is set.
    """
    skip_services = request.config.getoption("--no-services")

    if skip_services:
        pytest.skip("Skipping dash_app fixture (--no-services flag set)")

    # Import app here to avoid module-level import triggering service connections
    from cosmonaut_app.app import app

    port = int(FLASK_PORT)
    srv = make_server("localhost", port, app.server)
    thread = threading.Thread(target=srv.serve_forever)
    thread.start()

    # Poll until the server responds instead of a blind sleep
    url = f"http://localhost:{port}/"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    else:
        pytest.exit("Dash app failed to start within 10 seconds")

    log.info("Dash app started on port %s", port)

    yield app

    # Graceful shutdown: stop accepting requests, then join thread
    log.info("Shutting down Dash app...")
    srv.shutdown()
    thread.join(timeout=10)
    log.info("Dash app shut down")


@pytest.fixture(scope="session")
def celery_worker(request):
    """Start a Celery worker for testing background job processing.

    This fixture spawns a Celery worker subprocess that:
    - Listens to both "routing" and "celery" (default) queues
    - Uses concurrency=1 for deterministic testing
    - Uses prefork pool for proper task termination
    - Enables task events for inspect() API functionality

    This fixture is skipped if --no-services flag is set.
    """
    skip_services = request.config.getoption("--no-services")

    if skip_services:
        pytest.skip("Skipping celery_worker fixture (--no-services flag set)")

    log.info("Starting Celery worker for testing...")

    # Start Celery worker process
    # Command adapted from cosmopolitan reference but using uv instead of poetry
    worker_process = subprocess.Popen(
        [
            "uv",
            "run",
            "celery",
            "-A",
            "cosmonaut_app.background_job_manager.celery",
            "worker",
            "--loglevel=debug",
            "--concurrency=1",
            "--pool=prefork",  # Use prefork pool for proper task termination
            "--queues=routing,test",  # Listen to both queues (routing for routing tasks, test for test tasks)
            "--hostname=worker@test",  # Give worker a name for identification
            "-E",  # Enable task events for inspect() API to work
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=os.setsid,  # Create new process group for clean termination
    )

    # Give worker time to start and connect to broker
    time.sleep(3)

    # Check if worker process is still running (not crashed)
    if worker_process.poll() is not None:
        stdout, stderr = worker_process.communicate()
        pytest.exit(
            f"Celery worker failed to start. stdout: {stdout}, stderr: {stderr}"
        )

    log.info("Celery worker started successfully")

    yield worker_process

    # Cleanup: terminate worker process and all child processes
    log.info("Terminating Celery worker...")
    try:
        # Send SIGTERM to the process group
        os.killpg(os.getpgid(worker_process.pid), signal.SIGTERM)

        # Wait for graceful shutdown
        try:
            worker_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't terminate gracefully
            os.killpg(os.getpgid(worker_process.pid), signal.SIGKILL)
            worker_process.wait()

        log.info("Celery worker terminated")
    except ProcessLookupError:
        # Process already terminated
        pass
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning(f"Error during worker cleanup: {e}")
        # Try one more time with SIGKILL
        try:
            os.killpg(os.getpgid(worker_process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
