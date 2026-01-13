"""Documentation generator for COSMONAUT webservice.

This module dynamically generates user-facing documentation by extracting docstrings
from page modules and formatting them as markdown with embedded screenshots.
"""

import argparse
import ast
import logging
import sys
import tomllib
from datetime import datetime
from pathlib import Path

from cosmonaut_app.doc_pages_config import (
    USER_WORKFLOW_PAGES,
    ADMIN_PAGES,
    EXCLUDED_PAGES,
)
from cosmonaut_app.screenshot_generator import ScreenshotGenerator

INTRO_TEMPLATE = """# COSMONAUT Documentation

### COSmic ray based soil MOisture Prediction NAvigation and UTility Tool

*Last updated: {timestamp}*

## Table of Contents
1. [Introduction](#introduction)
2. [User Workflow](#user-workflow)
3. [Administration](#administration)

---

<h2 id="introduction">Introduction</h2>

COSMONAUT is a web application for creating optimized navigation routes based on
cosmic ray neutron sensor (CRNS) measurement locations. The service helps researchers
plan efficient field sampling routes by:

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

"""

WORKFLOW_TEMPLATE = """<h2 id="user-workflow">User Workflow</h2>

This section describes the typical user journey for creating a navigation route,
from initial job creation through final GPX file download.

"""

ADMIN_TEMPLATE = """<h2 id="administration">Administration</h2>

Administrative pages for system management, monitoring, and debugging.

"""

FOOTER_TEMPLATE = "*Generated automatically from module docstrings*"


def get_app_version() -> str:
    """Read application version from pyproject.toml using tomllib.

    Returns:
        Version string (e.g., "0.1.0")
    """
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    return pyproject["project"]["version"]


class DocumentationGenerator:
    """Generate documentation from page module docstrings."""

    def __init__(self):
        """Initialize the documentation generator."""
        self.user_workflow_pages = USER_WORKFLOW_PAGES
        self.admin_pages = ADMIN_PAGES
        self.excluded_pages = EXCLUDED_PAGES
        logging.info("Documentation generator initialized", extra={"tag": "frontend"})

    def extract_docstring(self, module_name: str) -> tuple[str, str]:
        """Extract docstring from a page module by parsing the file.

        Args:
            module_name: Name of the module (e.g., 'home', 'user_info')

        Returns:
            tuple: (module_name, docstring)
        """
        # Get the file path
        pages_dir = Path(__file__).parent / "pages"
        module_file = pages_dir / f"{module_name}.py"

        # Read and parse the file to extract docstring
        with open(module_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        # Get module docstring
        docstring = ast.get_docstring(tree)

        if docstring:
            return module_name, docstring.strip()
        else:
            logging.warning(
                f"No docstring found in {module_name}.py", extra={"tag": "frontend"}
            )
            return module_name, f"*Documentation pending for {module_name} page.*"

    def generate_introduction_section(self) -> str:
        """Generate introduction section with service overview and architecture.

        Returns:
            str: Markdown formatted introduction section
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return INTRO_TEMPLATE.format(timestamp=timestamp)

    def generate_user_workflow_section(self) -> str:
        """Generate user workflow section with sequential pages.

        Returns:
            str: Markdown formatted user workflow section
        """
        workflow = WORKFLOW_TEMPLATE

        for i, (module_name, page_title) in enumerate(self.user_workflow_pages, 1):
            _, docstring = self.extract_docstring(module_name)

            # Create section header
            workflow += f"### {i}. {page_title}\n\n"

            # Add docstring content (remove the NOTE lines for cleaner display)
            doc_lines = docstring.split("\n")
            filtered_lines = [
                line for line in doc_lines if not line.strip().startswith("NOTE:")
            ]
            workflow += "\n".join(filtered_lines).strip() + "\n\n"

            # Add screenshot image with max-width styling
            workflow += (
                f'<img src="/assets/docs/screenshots/{module_name}.png" '
                f'alt="{page_title}" style="max-width: 100%; height: auto;" />\n\n'
            )

            # Add specific next step name
            if i < len(self.user_workflow_pages):
                next_page_title = self.user_workflow_pages[i][1]
                workflow += f"**Next Step**: {next_page_title} →\n\n"

        workflow += "---\n\n"
        return workflow

    def generate_admin_section(self) -> str:
        """Generate administration section with admin pages.

        Returns:
            str: Markdown formatted administration section
        """
        admin = ADMIN_TEMPLATE

        for module_name, page_title in self.admin_pages:
            _, docstring = self.extract_docstring(module_name)

            # Create section header
            admin += f"### {page_title}\n\n"

            # Add docstring content (remove the NOTE lines)
            doc_lines = docstring.split("\n")
            filtered_lines = [
                line for line in doc_lines if not line.strip().startswith("NOTE:")
            ]
            admin += "\n".join(filtered_lines).strip() + "\n\n"

            # Add screenshot image with max-width styling
            admin += (
                f'<img src="/assets/docs/screenshots/{module_name}.png" '
                f'alt="{page_title}" style="max-width: 100%; height: auto;" />\n\n'
            )

        admin += "---\n\n"
        return admin

    def generate_full_documentation(self) -> str:
        """Generate complete documentation markdown.

        Returns:
            str: Complete markdown documentation
        """
        logging.info("Generating documentation", extra={"tag": "frontend"})

        # Generate all sections
        intro = self.generate_introduction_section()
        workflow = self.generate_user_workflow_section()
        admin = self.generate_admin_section()

        # Combine all sections with footer
        full_doc = intro + workflow + admin + FOOTER_TEMPLATE + "\n"

        logging.info("Documentation generated successfully", extra={"tag": "frontend"})
        return full_doc

    def write_static_documentation(self, output_file: Path, version_file: Path) -> None:
        """Generate and write static documentation files.

        Args:
            output_file: Path to write documentation.md
            version_file: Path to write doc_version.txt

        Returns:
            None
        """
        # Generate markdown
        markdown = self.generate_full_documentation()

        # Get current version
        version = get_app_version()

        # Write documentation.md
        output_file.write_text(markdown, encoding="utf-8")

        # Write doc_version.txt (single line with version)
        version_file.write_text(version, encoding="utf-8")


def setup_logging():
    """Configure logging for CLI operations."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def generate_documentation(job_id: str, headless: bool = True) -> int:
    """Main documentation generation workflow.

    Args:
        job_id: Job ID with complete workflow data
        headless: Run browser in headless mode (default: True)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    setup_logging()

    logging.info(f"Generating documentation for COSMONAUT version {get_app_version()}")

    # Define output paths
    docs_dir = Path(__file__).parent / "assets" / "docs"
    screenshots_dir = docs_dir / "screenshots"

    # Create directories
    docs_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(exist_ok=True)

    # Generate screenshots
    logging.info("Starting screenshot generation...")
    logging.info(f"Using job_id: {job_id}")

    screenshot_gen = ScreenshotGenerator(job_id, headless=headless)

    try:
        # Generate all screenshots (fails on first error)
        # Assumes dev server already running at localhost:8080
        screenshot_gen.generate_all_screenshots(screenshots_dir)
        logging.info("All screenshots captured successfully")

        # Generate static documentation
        logging.info("Generating static documentation files...")
        doc_gen = DocumentationGenerator()
        doc_gen.write_static_documentation(
            output_file=docs_dir / "documentation.md",
            version_file=docs_dir / "doc_version.txt",
        )

        logging.info("Documentation generated successfully!")
        logging.info(f"  - Markdown: {docs_dir / 'documentation.md'}")
        logging.info(f"  - Version: {docs_dir / 'doc_version.txt'}")
        logging.info(f"  - Screenshots: {screenshots_dir}/ (9 files)")

        return 0

    except Exception as e:
        logging.error(f"Documentation generation failed: {e}")
        return 1


def main():
    """Parse arguments and run documentation generation."""
    parser = argparse.ArgumentParser(
        description="Generate static documentation with screenshots for COSMONAUT"
    )
    parser.add_argument(
        "job_id",
        type=str,
        help="Completed job ID to use for screenshot generation (must have data through all workflow steps)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window during screenshot capture (for debugging)",
    )

    args = parser.parse_args()

    sys.exit(generate_documentation(args.job_id, headless=not args.no_headless))


if __name__ == "__main__":
    main()
