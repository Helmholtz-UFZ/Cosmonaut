# COSMONAUT Documentation

### COSmic ray based soil MOisture Prediction NAvigation and UTility Tool

*Last updated: 2026-07-07 22:37:55*

## Table of Contents
1. [Introduction](#introduction)
2. [User Workflow](#user-workflow)
3. [Administration](#administration)

---

<h2 id="introduction">Introduction</h2>

COSMONAUT is a web application for creating optimized navigation routes based on
regional classification for remote sensing measurements specifically designed for cosmic
ray neutron sensor (CRNS). The service helps researchers plan efficient field sampling
routes by:

- Uploading membership data (sample locations)
- Selecting relevant street networks from OpenStreetMap
- Configuring routing parameters
- Generating downloadable GPX navigation files

### How It Works

The application uses a distributed architecture to handle routing jobs efficiently:

- **Background Processing**: Routing calculations are processed asynchronously by Celery
  workers, allowing you to submit jobs and check back later for results. You can navigate
  away while processing continues and return anytime to view your results.

- **Database**: Job data, street network selections, and system logs are stored in PostgreSQL
  with PostGIS extension for spatial data queries. This enables efficient geographic
  operations and spatial analysis.

- **Object Storage**: Large route files, GPX outputs, and intermediate results are stored
  in MinIO object storage for efficient retrieval and long-term archival.

- **Web Interface**: Built with the Dash framework for interactive data visualization,
  providing real-time map updates, responsive controls, and seamless navigation through
  the workflow.

---

<h2 id="user-workflow">User Workflow</h2>

This section describes the typical user journey for creating a navigation route,
from initial job creation through final GPX file download.

### 1. Home Page

Landing page for creating new routing jobs.



Welcome to COSMONAUT - the starting point for creating optimized navigation routes
based on cosmic ray neutron sensor measurement locations. This page allows you to
begin a new routing job by clicking the "Create new job" button.

Each job is assigned a unique identifier that tracks your data, route selections,
and final navigation output through the entire workflow. You can also continue
work on a previous routing project by opening it from the Job manager in the
navigation header.

From here, you'll proceed through the workflow to provide job information, upload
membership data, select streets from OpenStreetMap, configure routing parameters,
and download your final GPX navigation file for use in the field.

<img src="/assets/docs/screenshots/home.png" alt="Home Page" class="mw-100" />

**Next Step**: User Information →

### 2. User Information

Collect user email for job notifications.



This page allows you to provide an email address to receive notifications about
your routing job. Email notifications will be sent when:

- Your job has been successfully submitted for processing
- Your routing calculation has completed
- Any errors occur during processing

The email field includes live validation to ensure proper formatting before you can
proceed. Providing an email is optional but recommended for tracking long-running
jobs that process in the background.

Once you enter a valid email address (or skip this step by proceeding without one),
click "Next" to continue to the data upload page where you'll provide your
membership locations for route planning.

<img src="/assets/docs/screenshots/user_info.png" alt="User Information" class="mw-100" />

**Next Step**: Data Upload →

### 3. Data Upload

Upload membership and predictor data and configure coordinate reference system.



This page is where you upload your cosmic ray neutron sensor measurement locations
or sampling points that will be used to plan the navigation route. The workflow
on this page involves three key steps:

1. **Specify EPSG Code**: Enter the coordinate reference system (CRS) of your data.
   The application validates the EPSG code.

2. **Upload Membership File**: Drag and drop or select a CSV/TXT file containing your
   membership data with coordinate columns. The system will parse your file,
   transform coordinates to WGS84 (EPSG:4326) for map display, and visualize
   your locations on the interactive map. After uploading, the road network is
   downloaded from OpenStreetMap **in the background** — you can continue with
   the predictor upload while it runs. A status indicator shows the progress.

3. **Upload Predictor File**: Upload a CSV file containing the predictor data
   (e.g. environmental covariates) used by the routing algorithm. The predictor
   file must be consistent with the membership file. Hover over the upload
   button to see the exact format requirements in the tooltip.

**Membership File Requirements:**
- Format: CSV or TXT with delimiter-separated values
- Must include coordinate columns (latitude/longitude or projected coordinates)
- Coordinates should match the specified EPSG code
- Files are stored securely in your job's work directory

**Predictor File Requirements:**
- Format: CSV with delimiter-separated values
- Must be consistent with the uploaded membership file

Once both files are uploaded and validated, proceed to the street selection page
to choose which roads to include in your route.

<img src="/assets/docs/screenshots/data_upload.png" alt="Data Upload" class="mw-100" />

**Next Step**: Street Selection →

### 4. Street Selection

Select and refine street networks for route planning.



This interactive page allows you to choose which OpenStreetMap roads should be
included in your navigation route. Every change you make is **immediately
persisted** — if you leave the page and come back, your selections are
preserved exactly as you left them.

**Selection Features:**

- **Tag Filtering**: Toggle road types on or off using the switches. Roads of
  a disabled type are removed from the working network and will not appear on
  any other page or in the final route. Re-enabling a type brings those roads
  back from the original OSM download. Available classifications:

  - Motorway (highways and ramps)
  - Trunk road (expressways)
  - Primary road (major routes)
  - Secondary road (regional routes)
  - Tertiary road (local connectors)
  - Unclassified, Residential, Living street, Track

  Use "Select All" / "Select None" buttons for quick bulk operations.

- **Track Grades**: While the Track type is enabled, an additional filter
  selects which OSM ``tracktype`` grades are included. The scale describes
  surface firmness from grade 1 (solid — paved or heavily compacted) to
  grade 5 (soft — uncompacted, subtle on the landscape) and makes track
  selection much more reliable — but many tracks in OSM are unfortunately
  untagged. Grades 4 and 5 are rarely traversable by survey vehicles;
  they and untagged tracks (unknown condition) are excluded by default, so
  only grades 1-3 are active initially. Enable "No grade tag" to include
  untagged tracks as well.

- **Interactive Clicking**: Click individual road segments on the map to mark
  them for removal. Marked roads are highlighted in a distinct color for
  visual feedback. Press "Remove selected" to permanently delete them.

- **Network Tools**:
  - **Keep Largest**: Retain only the largest connected road network
    component, removing isolated segments. This acts as a toggle — any
    subsequent edit (tag change, road removal) automatically resets it so
    that previously disconnected roads reappear for further editing.
  - **Reset**: Clear all selections, deletions, and filters, restoring the
    full original OSM download.

The map displays the current working network with real-time visual feedback.
Your goal is to create a connected network of streets that efficiently covers
your measurement locations while being traversable by your vehicle.

**Tips for Effective Selection:**

- Start by disabling road types that are unsuitable for your vehicle
- Remove individual problematic segments by clicking and removing
- Use "Keep Largest" as a final check to ensure network connectivity
- Verify all measurement points are reachable from your selected network

When satisfied with your street selection, proceed to configure routing
parameters for the final route calculation.

<img src="/assets/docs/screenshots/street_selection.png" alt="Street Selection" class="mw-100" />

**Next Step**: Routing Parameters →

### 5. Routing Parameters

Configure routing algorithm parameters before calculation.



Fine-tune the routing calculation by adjusting advanced parameters that control
how your navigation route is optimized. This page presents a dynamically generated
form with configuration options from the sensor-routing pipeline.

**Available Parameters:**

The form includes various routing optimization settings such as:
- Route optimization weights and penalties
- Distance calculation methods and thresholds
- Network traversal and pathfinding settings
- Algorithmic tuning options for the routing algorithm

The form is automatically generated from the FullPipelineConfig Pydantic model,
ensuring all parameters are properly validated and have sensible defaults. Each
field includes its data type, default value, and valid ranges where applicable.

**Using This Page:**

Most users can proceed with the default values, which are optimized for typical
CRNS field sampling scenarios. The defaults provide a good balance between route
efficiency, coverage of measurement points, and practical navigability.

Advanced users can customize parameters for specific use cases:
- Different vehicle types (car, bicycle, on-foot)
- Varying terrain requirements
- Specific measurement density patterns
- Custom optimization objectives

Simply review the default settings and modify any parameters you wish to customize.
When satisfied, click "Next" to proceed to the final page where you'll start the
route calculation and download your GPX navigation file.

<img src="/assets/docs/screenshots/routing_params.png" alt="Routing Parameters" class="mw-100" />

**Next Step**: Route Computation →

### 6. Route Computation

Start and monitor the routing computation process.



This page gives you full control over the routing calculation for your job.
Unlike the other workflow steps, the actual route computation happens here as a
background task, allowing you to monitor its progress and manage the process.

**Starting the Computation:**

Click the green "Start Computation" button to begin calculating your optimized route.
The computation runs as a background task using Celery workers, so it continues even
if you close your browser or navigate away. You can return to this page at any time
to check the status.

**Job Status:**

The status badge shows the current state of your computation:
- **PENDING** (Gray): Job created but not yet started
- **RUNNING** (Blue): Computation is actively running
- **COMPLETED** (Green): Route successfully calculated, ready to download
- **FAILED** (Red): Computation encountered an error

The status badge, logs, and button visibility automatically update every 3 seconds
while a job is running, and immediately after any action (start/cancel/restart).

**Managing the Computation:**

Depending on the current status, you'll see different control buttons:
- **Start Computation**: Begins the route calculation (shown when PENDING)
- **Cancel Computation**: Stops the running task immediately (shown when RUNNING)
- **Restart Computation**: Resets and restarts the job (shown when COMPLETED or FAILED)

Button visibility updates automatically as the job status changes.

**Worker Information:**

The Celery Worker Information panel shows details about the computation infrastructure:
- **Worker Availability**: Number of background workers available to process your job
- **Task Celery Status**: Internal task state from the Celery task queue
- **Worker Name**: Hostname of the specific worker processing your job

This information is fetched on page load and after starting/restarting a computation.
It helps diagnose issues if your job stays in PENDING state (no workers available)
or if you need to report problems to system administrators.

**Computation Logs:**

The logs section displays worker output as it becomes available. During RUNNING state,
logs update every 3 seconds via polling. Once the computation completes (COMPLETED or
FAILED status), the full worker logs are displayed, containing:
- Algorithm execution steps and progress
- Parameters used for the optimization
- Statistics about the generated route
- Any warnings or errors encountered

The logs are synced from the worker container after the job finishes.

<img src="/assets/docs/screenshots/route_computation.png" alt="Route Computation" class="mw-100" />

**Next Step**: Route & Download →

### 7. Route & Download

Calculate route and download GPX navigation file.



This is the final page of the workflow where you initiate the routing calculation
and download your optimized navigation route as a GPX file for use with GPS devices
or navigation applications.

**Page Features:**

- **Start Route Button**: Initiates the background routing calculation using
  your selected streets and configured parameters. The calculation runs as a
  Celery background task, so you can close your browser and check back later
  for results.

- **QR Code**: After the calculation completes successfully, a QR code is
  displayed that links directly to the GPX file download. This provides a
  convenient way to transfer the route to mobile devices - simply scan the
  code with your smartphone camera.

- **GPX Download**: Download the complete navigation route as a standard GPX
  (GPS Exchange Format) file compatible with most GPS devices, smartphone
  navigation apps, and mapping software.

- **Reverse Direction**: A switch flips the start and end of the route. The
  GPX file, the QR code and the on-map direction arrows update together.
  Only the order of the track points is reversed — the route itself does not
  change, and one-way restrictions are not re-validated for the opposite
  direction, so double-check the reversed route is legal to drive.

- **Route Visualization**: View the calculated route overlaid on the interactive
  map with all waypoints, turn-by-turn segments, and your original measurement
  locations. This allows you to preview the route before using it in the field.

**Processing Time:**

The routing calculation duration depends on several factors:
- Complexity and size of the selected street network
- Number of measurement points to visit
- Configured routing parameters and optimization settings
- Current system load and available worker capacity

You can monitor the job status and return to this page at any time to check
for completion and download your results.

**Using Your GPX File:**

The generated GPX file can be used in multiple ways:
- Transfer to a dedicated GPS device for field navigation
- Import into smartphone navigation apps (OsmAnd, Maps.me, etc.)
- Load into mapping software for route preview and analysis
- Share with field team members for coordinated sampling

The QR code provides the quickest way to get the route onto your mobile device
for immediate field use.

<img src="/assets/docs/screenshots/route_download.png" alt="Route & Download" class="mw-100" />

---

<h2 id="administration">Administration</h2>

Administrative pages for system management, monitoring, and debugging.

### Application Logs

View and filter application logs for debugging and monitoring.



This page provides access to the application's logging system, allowing you to track
system activity, debug issues, and monitor operations. You can:

- Filter logs by date and time range
- Select specific log levels (Debug, Info, Warning, Error, Critical)
- Filter by process ID to track specific server processes
- Exclude specific modules from the output
- Enable live mode for automatic 10-second polling
- View logs in a formatted, readable table
- Refresh logs on demand to see latest entries

Logs are stored in the database and include timestamps, log levels, logger names,
and messages. This is the primary tool for understanding system behavior, diagnosing
problems, and monitoring application execution.

<img src="/assets/docs/screenshots/logs.png" alt="Application Logs" class="mw-100" />

### Worker Management

Worker Management Page for COSMONAUT App.



Monitor and manage background workers and tasks.

This administrative page provides real-time visibility into the Celery background task
system that processes prediction jobs and maintenance operations. Features include:

**Worker Status:**
- View active worker processes and their configuration
- See worker pool types, concurrency settings, and queue assignments
- Check worker availability and health

**Task Monitoring:**
- View currently executing tasks (active tasks)
- See tasks waiting in worker queues (reserved tasks)
- Monitor scheduled tasks waiting for their run time
- Track revoked (cancelled) tasks
- Display task details including name, arguments, and execution time

**Task Control:**
- Kill actively running tasks (forcefully terminate)
- Cancel scheduled tasks before they execute
- Confirmation dialogs prevent accidental terminations

**Status Updates:**
- Manual refresh to get latest worker and task information
- Timestamp showing when data was last refreshed

This page is essential for monitoring system load, debugging stuck tasks, and managing
resource usage during peak periods.

<img src="/assets/docs/screenshots/worker_management.png" alt="Worker Management" class="mw-100" />

### Job Manager

Manage all jobs from a central dashboard.



This administrative page provides a comprehensive overview of all jobs in the system.
You can:
- View all jobs in a table with status, start date, and submission details
- See job status at a glance with color coding (PENDING=orange, RUNNING=green,
  COMPLETED=blue, FAILED=red)
- Select and delete individual jobs or multiple jobs at once
- Trigger cleanup operations to remove old jobs automatically
- Access individual job pages directly from the table by clicking Job ID

The table uses color coding to quickly identify job statuses. You can select rows to
perform bulk operations like deletion. Use the cleanup function to automatically remove
jobs that exceed retention periods (2 days for unsubmitted, 60 days for submitted jobs).

<img src="/assets/docs/screenshots/job_manager.png" alt="Job Manager" class="mw-100" />

---

*Generated automatically from module docstrings*
