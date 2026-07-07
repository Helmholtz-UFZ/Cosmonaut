"""Test street selector filter logic (no services required)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _track(tracktype):
    return {"highway": "track", "tracktype": tracktype}


def test_track_grade_allowed_ignores_non_tracks():
    """Non-track features pass regardless of the allowed grade set."""
    from cosmonaut_app.road_network_utils import track_grade_allowed

    properties = {"highway": "residential", "tracktype": None}
    assert track_grade_allowed(properties, [])


def test_track_grade_allowed_filters_by_grade():
    """Tracks pass only when their grade is in the allowed set."""
    from cosmonaut_app.road_network_utils import track_grade_allowed

    assert track_grade_allowed(_track("grade2"), ["grade1", "grade2"])
    assert not track_grade_allowed(_track("grade4"), ["grade1", "grade2"])


def test_track_grade_allowed_buckets_untagged_and_nonstandard_as_ungraded():
    """Missing or non-standard tracktype values fall into the ungraded bucket."""
    from cosmonaut_app.constants.general import UNGRADED_TRACK_GRADE
    from cosmonaut_app.road_network_utils import track_grade_allowed

    for tracktype in (None, "grade2;grade3", "unknown"):
        assert track_grade_allowed(_track(tracktype), [UNGRADED_TRACK_GRADE])
        assert not track_grade_allowed(_track(tracktype), ["grade1"])


def test_default_track_grades_accept_only_1_to_3():
    """The default excludes grade4, grade5 AND untagged tracks (unknown
    condition) — field practice: only known-good grades 1-3."""
    from cosmonaut_app.constants.general import DEFAULT_TRACK_GRADES
    from cosmonaut_app.road_network_utils import track_grade_allowed

    for grade in ("grade1", "grade2", "grade3"):
        assert track_grade_allowed(_track(grade), DEFAULT_TRACK_GRADES)
    for grade in ("grade4", "grade5", None):
        assert not track_grade_allowed(_track(grade), DEFAULT_TRACK_GRADES)
