"""Setup tests with conditional fixture loading."""

import hashlib
import http.server
import importlib.resources
import logging
import os
import pathlib
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.request

import pytest
import redis
from cosmo_suite.object_storage_manager import create_bucket, setup_remote
from playwright.sync_api import ConsoleMessage, Page
from playwright.sync_api import Error as PlaywrightError
from slugify import slugify
from sqlalchemy.exc import OperationalError
from werkzeug.serving import make_server

from cosmonaut_app.config import (
    PORT,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.error_handling import ObjectStorageError


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

_worker_log_path: pathlib.Path | None = None


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
        time.sleep(4)

        # Check PostgreSQL connectivity
        try:
            result = DataBaseManager.check_existence("test")
            log.info(f"Database connection successful. Test query result: {result}")
        except OperationalError as e:
            log.error(f"Database connection failed: {e}")
            pytest.exit(f"PostgreSQL not available: {e}")

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
            log.info("Redis connection successful")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            log.error(f"Redis connection failed: {e}")
            pytest.exit(f"Redis not available: {e}")

        # Check rclone can connect to MinIO via S3 protocol
        try:
            setup_remote()
            create_bucket()
            log.info("rclone MinIO connectivity check passed")
        except ObjectStorageError as e:
            log.error(f"rclone MinIO connectivity check failed: {e}")
            pytest.exit(f"MinIO S3 connectivity check failed: {e}")
    else:
        log.info("Skipping service health checks (--no-services flag set)")


@pytest.fixture
def logger():
    """Create a logger with suppressed external sources.

    This fixture is always available regardless of --no-services flag.
    """
    return create_logger()


def _find_sensor_routing_test_file(substr):
    """Find a test data file from the sensor_routing package by substring."""
    test_data_dir = importlib.resources.files("sensor_routing") / "test_data"
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


def _truncate_file_name(file_name: str) -> str:
    if len(file_name) < 256:
        return file_name
    return f"{file_name[:100]}-{hashlib.sha256(file_name.encode()).hexdigest()[:7]}-{file_name[-100:]}"


class _LogCollector(logging.Handler):
    """Handler that collects formatted log records in memory."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []
        self.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(self.format(record))


@pytest.fixture
def page(
    page: Page, request: pytest.FixtureRequest, pytestconfig: pytest.Config
) -> Page:
    console_messages: list[str] = []

    def _on_console(msg: ConsoleMessage) -> None:
        console_messages.append(f"[{msg.type}] {msg.text}")

    page.on("console", _on_console)

    log_collector = _LogCollector()
    root_logger = logging.getLogger()
    root_logger.addHandler(log_collector)

    yield page

    root_logger.removeHandler(log_collector)

    failed = request.node.rep_call.failed if hasattr(request.node, "rep_call") else True
    if not failed:
        return

    output_dir = pathlib.Path(pytestconfig.getoption("--output")).absolute()
    test_dir = output_dir / _truncate_file_name(slugify(request.node.nodeid))
    test_dir.mkdir(parents=True, exist_ok=True)

    try:
        html_content = page.content()
        (test_dir / "page.html").write_text(html_content, encoding="utf-8")
    except PlaywrightError:
        pass  # Page may have already closed

    if console_messages:
        (test_dir / "console.log").write_text(
            "\n".join(console_messages), encoding="utf-8"
        )

    if log_collector.records:
        (test_dir / "server.log").write_text(
            "\n".join(log_collector.records), encoding="utf-8"
        )

    if _worker_log_path and _worker_log_path.stat().st_size > 0:
        shutil.copy2(_worker_log_path, test_dir / "worker.log")


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

    # Inline import: app.py boots Dash, MinIO, Beat scheduler — must stay deferred
    from cosmonaut_app.app import app

    port = int(PORT)
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
def overpass_stub():
    """Serve the committed Overpass response instead of querying the live API.

    The OSM download runs inside ``process_upload_task``, i.e. in the **Celery
    worker subprocess** that ``celery_worker`` starts with ``subprocess.Popen``.
    A ``monkeypatch`` lives in the pytest process and cannot cross that boundary,
    which is why ``osm_cache_patch`` never protected this path: every integration
    run so far went to the public Overpass API and inherited its flakiness (a
    timeout leaves the street-selection "Next" button disabled and the test burns
    its full timeout — it does not look like a network problem).

    The seam that *does* cross the boundary is the production environment
    variable ``OVERPASS_URL``, read in ``cosmonaut_app.osm.source`` at import
    time. This fixture serves ``test/fixtures/overpass_test_aoi.json`` — a real
    ``out geom`` response for the committed test AOI — and hands back its URL so
    ``celery_worker`` can point the worker at it. No production code knows it
    exists, and the real streaming parse and transform still run.
    """
    payload = (
        pathlib.Path(__file__).parent / "fixtures" / "overpass_test_aoi.json"
    ).read_bytes()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 — BaseHTTPRequestHandler's naming
            """Answer any query with the fixture; the AOI is fixed anyway."""
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            """Silence per-request stderr noise."""

    # Port 0: the OS picks a free one, so the stub cannot collide with the other
    # suites (see docs/conventions/framework_integration.md, port allocation).
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/api/interpreter"
    log.info(f"Overpass stub serving {len(payload)} bytes at {url}")

    yield url

    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def celery_worker(request, overpass_stub):
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

    global _worker_log_path  # noqa: PLW0603

    log.info("Starting Celery worker for testing...")

    # Redirect worker stderr to a temp file so it can be captured as a test artifact
    worker_log_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="worker_", suffix=".log", delete=False
    )
    _worker_log_path = pathlib.Path(worker_log_file.name)

    # Start Celery worker process
    # Command adapted from cosmopolitan reference but using uv instead of poetry
    # Both stdout and stderr go to the log file: Celery's own logging uses stderr,
    # but the routing task switches logging to stdout via dictConfig.
    # OVERPASS_URL is the only seam that reaches the worker subprocess — see the
    # overpass_stub fixture for why a monkeypatch cannot.
    worker_env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "OVERPASS_URL": overpass_stub,
    }
    worker_process = subprocess.Popen(
        [
            "uv",
            "run",
            "celery",
            "-A",
            "cosmonaut_app.celery_app.celery",
            "worker",
            "--loglevel=debug",
            "--concurrency=1",
            "--pool=prefork",  # Use prefork pool for proper task termination
            "--queues=routing,test,upload",  # Listen to routing, test, and upload queues
            "--hostname=worker@test",  # Give worker a name for identification
            "-E",  # Enable task events for inspect() API to work
        ],
        stdout=worker_log_file,
        stderr=worker_log_file,
        text=True,
        env=worker_env,
        preexec_fn=os.setsid,  # Create new process group for clean termination
    )

    # Give worker time to start and connect to broker
    time.sleep(3)

    # Check if worker process is still running (not crashed)
    if worker_process.poll() is not None:
        worker_log_file.close()
        stderr = _worker_log_path.read_text()
        pytest.exit(f"Celery worker failed to start. stderr: {stderr}")

    log.info("Celery worker started successfully")

    yield worker_process

    # Close the log file so all output is flushed
    worker_log_file.close()

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


@pytest.fixture(scope="session")
def worker_log_path(celery_worker):
    """Expose the Celery worker log file path for test assertions."""
    return _worker_log_path


@pytest.fixture
def osm_cache_patch(monkeypatch):
    """Monkeypatch OsmDownloader.run_osm_query to use cached test fixtures.

    Instead of querying the live Overpass API (slow, flaky on CI), an in-process
    caller gets precomputed OSM data cached in test/fixtures/osm_cache/. The cache
    contains the three outputs for the fixed test AOI (test/memberships.csv, EPSG:25832).
    It is regenerated only when the test AOI changes (via
    test/fixtures/regenerate_osm_cache.py).

    **This covers in-process callers only.** The download the integration tests
    actually trigger runs in ``process_upload_task``, inside the Celery worker
    *subprocess*, which a monkeypatch cannot reach — so this fixture never
    protected that path, and every integration run went to the public Overpass
    API. The worker is covered by the ``overpass_stub`` fixture instead, via the
    ``OVERPASS_URL`` environment variable. Keep both: they guard different
    processes.

    In production (real users), the live Overpass query runs and may retry on
    transient errors (Tier 2 of the fix plan).

    The fixture is skipped if SKIP_OSM_CACHE=1 (set by the nightly test-integration-live-osm
    job in .gitlab-ci.yml to test the live Overpass contract).
    """
    if os.getenv("SKIP_OSM_CACHE") == "1":
        log.info("OSM cache patch skipped (SKIP_OSM_CACHE=1) — using live Overpass API")
        return

    cache_dir = os.path.join(
        os.path.dirname(__file__), "fixtures", "osm_cache"
    )

    def _cached_run_osm_query(self, download_folder):
        """Copy cached OSM files instead of querying Overpass."""
        for file_name in [
            "osm_data_download.geojson",
            "osm_data_edited.geojson",
            "osm_data_transformed.geojson",
        ]:
            src = os.path.join(cache_dir, file_name)
            dst = os.path.join(download_folder, file_name)
            if not os.path.exists(src):
                raise FileNotFoundError(
                    f"OSM cache missing: {file_name}. "
                    f"Regenerate with: python test/fixtures/regenerate_osm_cache.py"
                )
            shutil.copy2(src, dst)

    from cosmonaut_app.osm import OsmDownloader
    monkeypatch.setattr(OsmDownloader, "run_osm_query", _cached_run_osm_query)
