"""Test the Dash app."""

import logging
import time
from logging.config import dictConfig
from unittest.mock import patch

import pytest
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from cosmopolitan_app.app import app
from cosmopolitan_app.constants import (
    CHANGE_INPUT_BUTTON_ID,
    CHECK_INPUT_ID,
    JOB_LOGS_ID,
    NAVBAR_TOGGLER_ID,
    NEW_JOB_LINK_ID,
    PREPARE_INPUT_ID,
    RESULT_BUTTON_ID,
    SUBMISSION_STATUS_ID,
    SUBMIT_JOB_ID,
)
from cosmopolitan_app.form_factory import (
    active_form_factory,
    active_form_template_factory,
)
from cosmopolitan_app.logger import get_logger_config_web
from cosmopolitan_app.pydantic_models import ModelWebsite


def wait_for_all_images_loaded(driver, timeout=5):
    """Wait for all images on the page to be loaded."""
    end_time = time.time() + timeout
    while time.time() < end_time:
        all_loaded = driver.execute_script(
            """
            return Array.from(document.images).every(img => img.complete);
        """
        )
        if all_loaded:
            return True
        time.sleep(0.1)
    return False


def check_all_errors(dash_duo):
    """Simplified error checking that works with most WebDriver configurations."""
    time.sleep(1)  # for everything to load properly
    errors = []

    # Console errors (most reliable)
    console_logs = dash_duo.driver.get_log("browser")
    console_errors = [
        log
        for log in console_logs
        if log["level"] in ["SEVERE", "ERROR"]
        and "favicon" not in log["message"].lower()
    ]
    if console_errors:
        errors.extend([f"Console: {log['message']}" for log in console_errors])

    # JavaScript errors
    js_errors = dash_duo.driver.execute_script(
        """
        return (window.jsErrors || []).concat(
            Array.from(document.querySelectorAll('[data-error]'))
            .map(el => el.dataset.error)
        );
        """
    )
    if js_errors:
        errors.extend([f"JS Error: {err}" for err in js_errors if err])

    # Basic broken image check
    wait_for_all_images_loaded(dash_duo.driver)
    broken_images = dash_duo.driver.execute_script(
        """
        return Array.from(document.querySelectorAll('img'))
            .filter(img => img.complete && img.naturalWidth === 0 && img.src !== '')
            .map(img => img.src);
        """
    )
    if broken_images:
        errors.extend([f"Broken image: {img}" for img in broken_images])

    if errors:
        pytest.fail("Errors detected:\n" + "\n".join(errors))


def scroll_to_element_and_click(dash_duo, element_id):
    """Scroll to a specific element in the Dash app."""
    for _ in range(5):
        element = dash_duo.wait_for_element(f"#{element_id}", timeout=10)
        try:
            dash_duo.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
            time.sleep(0.5)
            element.click()
            return element
        except ElementClickInterceptedException:
            pass
        except StaleElementReferenceException:
            pass


def save_snapshot(dash_duo):
    """Save a snapshot of the current state of the Dash app."""
    rendered_html = dash_duo.driver.execute_script(
        "return document.documentElement.outerHTML"
    )
    with open("debug_source.html", "w") as f:
        f.write(rendered_html)
    dash_duo.driver.save_screenshot("headless_debug.png")


@patch("cosmopolitan_app.map_utils.create_tile_layer_component")
def test_full_procedure(
    mock_tile_layer, dash_duo, crns_file_path, pred_file_paths, celery_worker
):
    """Test the full procedure of the Dash app."""
    # Mock tile layer creation to avoid tile server dependency in tests Mock returns
    # None so only the legend is rendered, preventing JavaScript tile fetch errors
    mock_tile_layer.return_value = None

    # Ensure Celery worker is running before starting tests
    dictConfig(get_logger_config_web(True))
    if celery_worker.poll() is not None:
        logging.error("Celery worker process terminated unexpectedly")
        raise RuntimeError("Celery worker not available for testing")

    logging.info("Starting full procedure test with Celery worker")
    dash_duo.start_server(app)
    dash_duo.driver.set_window_size(1920, 1080)
    dash_duo.driver.execute_cdp_cmd("Runtime.enable", {})
    dash_duo.driver.execute_cdp_cmd("Log.enable", {})
    check_all_errors(dash_duo)

    # Expand navbar if collapsed
    try:
        toggler = dash_duo.wait_for_element(f"#{NAVBAR_TOGGLER_ID}", timeout=10)
        if toggler.is_displayed():
            toggler.click()
    except (NoSuchElementException, ElementNotInteractableException):
        pass

    dash_duo.wait_for_element(f"#{NEW_JOB_LINK_ID}", timeout=10).click()
    check_all_errors(dash_duo)
    dash_duo.wait_for_element(f"#{PREPARE_INPUT_ID}", timeout=10).click()
    check_all_errors(dash_duo)

    # Uncheck predictors
    predictor_dropdown_id = active_form_factory.id_format.format(
        field_name="pred_streams"
    )
    # First the button to open the dropdown menu
    dropdown_menu = dash_duo.find_element("#pred_streams").find_element(
        "xpath", "./ancestor::div[contains(@class, 'dropdown-menu')]"
    )
    aria_labelledby = dropdown_menu.get_attribute("aria-labelledby")
    aria_labelledby = aria_labelledby.replace(":", "\\:")
    scroll_to_element_and_click(dash_duo, aria_labelledby)
    # Now the dropdown menu should be open
    # Find all checked checkboxes in the dropdown menu and uncheck them
    checked_checkboxes = dash_duo.find_elements(
        f"#{predictor_dropdown_id} input[type='checkbox']:checked", "CSS_SELECTOR"
    )
    for checkbox in checked_checkboxes:
        scroll_to_element_and_click(dash_duo, checkbox.get_attribute("id"))

    # Upload predictor files
    pred_field_name = "predictor_upload"
    assert (
        pred_field_name in ModelWebsite.model_fields
    ), "Predictor field not found in pymodel"
    pred_upload_id = active_form_factory.id_format.format(field_name=pred_field_name)
    upload_element = dash_duo.find_element(f"#{pred_upload_id} input[type='file']")
    selected_pred_id = active_form_template_factory.selected_predictors_key
    for pred_file_path in pred_file_paths:
        pred_file_name = str(pred_file_path.name)

        upload_element.send_keys(str(pred_file_path))
        for attempts in range(10):
            time.sleep(1)
            items = dash_duo.find_elements(f"#{selected_pred_id}")
            if any(pred_file_name in item.text for item in items):
                break
        else:
            raise AssertionError(
                f"Predictor file {pred_file_name} not found in the list after upload"
            )

    # Upload CRNS file

    # Uncheck all CRNS measurement fields
    for crns_measurment_field_name in ["train_data", "station_data", "rover_data"]:
        crns_measurment_id = active_form_factory.id_format.format(
            field_name=crns_measurment_field_name
        )
        scroll_to_element_and_click(dash_duo, crns_measurment_id)

    crns_file_name = str(crns_file_path.name)
    crns_field_name = "crns_upload"
    assert (
        crns_field_name in ModelWebsite.model_fields
    ), "CRNS field not found in pymodel"
    crns_upload_id = active_form_factory.id_format.format(field_name=crns_field_name)

    upload_element = dash_duo.find_element(f"#{crns_upload_id} input[type='file']")
    upload_element.send_keys(str(crns_file_path))
    selected_crns_id = active_form_template_factory.selected_crns_key
    for attempts in range(10):
        time.sleep(1)
        items = dash_duo.find_elements(f"#{selected_crns_id}")
        if any(crns_file_name in item.text for item in items):
            break
    else:
        raise AssertionError(
            f"CRNS file {crns_file_name} not found in the list after upload"
        )

    check_all_errors(dash_duo)

    # Check input
    scroll_to_element_and_click(dash_duo, CHECK_INPUT_ID)
    check_all_errors(dash_duo)
    # Change input
    scroll_to_element_and_click(dash_duo, CHANGE_INPUT_BUTTON_ID)
    check_all_errors(dash_duo)
    scroll_to_element_and_click(dash_duo, CHECK_INPUT_ID)
    check_all_errors(dash_duo)

    # Submit job
    scroll_to_element_and_click(dash_duo, SUBMIT_JOB_ID)
    check_all_errors(dash_duo)

    # Wait for the submission status to change
    for attempts in range(60):
        time.sleep(1)
        status_element = dash_duo.wait_for_element(
            f"#{SUBMISSION_STATUS_ID}", timeout=1
        )
        if "RUNNING" in status_element.text:
            continue
        elif "PENDING" in status_element.text:
            continue
        break

    time.sleep(10)

    if "COMPLETED" not in status_element.text:
        logging.error(f"Job finished with status: {status_element.text}")
        save_snapshot(dash_duo)
        job_logs = dash_duo.find_element(f"#{JOB_LOGS_ID}").text
        raise AssertionError("Job did not complete successfully. Logs:\n" + job_logs)

    scroll_to_element_and_click(dash_duo, RESULT_BUTTON_ID)
    time.sleep(10)
    check_all_errors(dash_duo)
