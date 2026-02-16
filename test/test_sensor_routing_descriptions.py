"""Test that sensor_routing description strings are multiline."""

from sensor_routing.full_pipeline_cli import (
    DESCRIPTION_MEMBERSHIP,
    DESCRIPTION_PREDICTOR,
)


def test_description_membership_is_multiline():
    """DESCRIPTION_MEMBERSHIP must be a multiline string for tooltip display."""
    assert "\n" in DESCRIPTION_MEMBERSHIP


def test_description_predictor_is_multiline():
    """DESCRIPTION_PREDICTOR must be a multiline string for tooltip display."""
    assert "\n" in DESCRIPTION_PREDICTOR
