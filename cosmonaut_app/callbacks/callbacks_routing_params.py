from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import os
import json
import glob
import shutil
import logging
from datetime import datetime, timezone

from cosmonaut_app.constants.html_ids import (
    CFG_AN_INPUT_ROUTING_PARAMS_ID,
    CFG_IR_INPUT_ROUTING_PARAMS_ID,
    CFG_LBF_INPUT_ROUTING_PARAMS_ID,
    CFG_MAI_INPUT_ROUTING_PARAMS_ID,
    CFG_OO_INPUT_ROUTING_PARAMS_ID,
    CFG_SN_INPUT_ROUTING_PARAMS_ID,
    CFG_TL_INPUT_ROUTING_PARAMS_ID,
    CFG_WD_INPUT_ROUTING_PARAMS_ID,
    PARAMS_ALERT_ALERT_ROUTING_PARAMS_ID,
    PARAMS_LOAD_BUTTON_ROUTING_PARAMS_ID,
    ROUTING_COMPLETE_STORE_SHARED_ID,
    RUN_ROUTING_BUTTON_ROUTING_PARAMS_ID,
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    TAGS_LAST_SELECTION_STORE_SHARED_ID,
    URL_DIV_NAV_SHARED_ID,
)
from cosmonaut_app.app import app
from cosmonaut_app.config import WEB_WORK_DIR, osm_tags_mapping
from sensor_routing.sensor_routing_cli import (
    Config,
    load_or_create_parameters,
    sensor_routing,
)
from cosmonaut_app.utils.routing_post import silence_prints, build_solution_route_4326

log = logging.getLogger(__name__)


@app.callback(
    Output(CFG_SN_INPUT_ROUTING_PARAMS_ID, "value"),
    Output(CFG_LBF_INPUT_ROUTING_PARAMS_ID, "value"),
    Output(CFG_TL_INPUT_ROUTING_PARAMS_ID, "value"),
    Output(CFG_OO_INPUT_ROUTING_PARAMS_ID, "value"),
    Output(CFG_MAI_INPUT_ROUTING_PARAMS_ID, "value"),
    Output(CFG_AN_INPUT_ROUTING_PARAMS_ID, "value"),
    Output(CFG_IR_INPUT_ROUTING_PARAMS_ID, "value"),
    Output(CFG_WD_INPUT_ROUTING_PARAMS_ID, "value"),
    Input(PARAMS_LOAD_BUTTON_ROUTING_PARAMS_ID, "n_intervals"),
    State(URL_DIV_NAV_SHARED_ID, "pathname"),
    prevent_initial_call=True,
)
def init_params(_n, pathname):
    # /job/<job_id>/routing-params
    try:
        job_id = pathname.split("/job/")[1].split("/")[0]
    except Exception:
        raise PreventUpdate
    workdir = os.path.join(WEB_WORK_DIR, job_id)
    cfg = load_or_create_parameters(working_dir=workdir)
    return (
        cfg.segment_number,
        cfg.lower_benefit_limit,
        cfg.time_limit,
        cfg.optimization_objective,
        cfg.max_aco_iteration,
        cfg.ant_no,
        [True] if cfg.is_reversed else [],
        cfg.working_directory,
    )


@app.callback(
    Output(PARAMS_ALERT_ALERT_ROUTING_PARAMS_ID, "children", allow_duplicate=True),
    Output(PARAMS_ALERT_ALERT_ROUTING_PARAMS_ID, "color", allow_duplicate=True),
    Output(PARAMS_ALERT_ALERT_ROUTING_PARAMS_ID, "is_open", allow_duplicate=True),
    Output(ROUTING_COMPLETE_STORE_SHARED_ID, "data", allow_duplicate=True),
    Input(RUN_ROUTING_BUTTON_ROUTING_PARAMS_ID, "n_clicks"),
    State(CFG_SN_INPUT_ROUTING_PARAMS_ID, "value"),
    State(CFG_LBF_INPUT_ROUTING_PARAMS_ID, "value"),
    State(CFG_TL_INPUT_ROUTING_PARAMS_ID, "value"),
    State(CFG_OO_INPUT_ROUTING_PARAMS_ID, "value"),
    State(CFG_MAI_INPUT_ROUTING_PARAMS_ID, "value"),
    State(CFG_AN_INPUT_ROUTING_PARAMS_ID, "value"),
    State(CFG_IR_INPUT_ROUTING_PARAMS_ID, "value"),
    State(CFG_WD_INPUT_ROUTING_PARAMS_ID, "value"),
    State(URL_DIV_NAV_SHARED_ID, "pathname"),
    prevent_initial_call=True,
)
def run_routing(n, sn, lbf, tl, oo, mai, an, ir_list, wd, pathname):
    if not n:
        raise PreventUpdate
    try:
        job_id = pathname.split("/job/")[1].split("/")[0]
    except Exception:
        return ("Ungültige URL.", "danger", True, False)

    workdir = wd or os.path.join(WEB_WORK_DIR, job_id)
    input_dir = os.path.join(workdir, "input")
    transient_dir = os.path.join(workdir, "transient")
    os.makedirs(transient_dir, exist_ok=True)

    # simple lock to avoid double runs
    lock_path = os.path.join(transient_dir, "routing.lock")
    if os.path.exists(lock_path):
        return ("Routing läuft bereits. Bitte warten…", "warning", True, False)
    # acquire lock
    with open(lock_path, "w", encoding="utf-8") as f:
        f.write(datetime.now(timezone.utc).isoformat())

    success = False
    message = "Routing fehlgeschlagen."
    level = "danger"

    # prepare hiding bookkeeping early so we can always restore in finally
    tmp_hide_dir = os.path.join(input_dir, "_routing_tmp_hide")
    moved: list[str] = []

    # Unhide anything left from a previous failed run
    try:
        if os.path.isdir(tmp_hide_dir):
            for p in glob.glob(os.path.join(tmp_hide_dir, "*.geojson")):
                try:
                    shutil.move(p, os.path.join(input_dir, os.path.basename(p)))
                except Exception as e:
                    log.warning("Could not unhide %s: %s", p, e)
            try:
                if not os.listdir(tmp_hide_dir):
                    os.rmdir(tmp_hide_dir)
            except Exception:
                pass
    except Exception as e:
        log.warning("Unhide sweep failed: %s", e)

    try:
        # Build config and persist parameters for THIS job
        try:
            cfg = Config(
                sn=sn,
                lbf=lbf,
                tl=tl,
                oo=oo,
                mai=mai,
                an=an,
                ir=bool(ir_list),
                wd=workdir,
            )
        except Exception as e:
            return (f"Parameter ungültig: {e}", "danger", True, False)

        params_path = os.path.join(workdir, "parameters.json")
        params = cfg.model_dump(by_alias=True)
        with open(params_path, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2, ensure_ascii=False)
        log.info("Parameters written to %s", params_path)

        # Deterministically use the projected file that contains osmid
        projected_candidates = [
            p
            for p in glob.glob(os.path.join(input_dir, "osm_data_*.geojson"))
            if "_4326" not in os.path.basename(p)
        ]
        chosen = projected_candidates[0] if projected_candidates else None
        if not chosen:
            any_geo = glob.glob(os.path.join(input_dir, "*.geojson"))
            if not any_geo:
                return (
                    "Kein GeoJSON im input/-Ordner gefunden.",
                    "danger",
                    True,
                    False,
                )
            chosen = max(any_geo, key=os.path.getmtime)
        log.info("Routing uses GeoJSON: %s", chosen)

        # Hide only competing projected (*.geojson) files; keep all *_4326.geojson visible
        os.makedirs(tmp_hide_dir, exist_ok=True)
        for p in glob.glob(os.path.join(input_dir, "*.geojson")):
            base = os.path.basename(p)
            if os.path.abspath(p) == os.path.abspath(chosen):
                continue
            if "_4326" in base:
                # keep 4326 companions; backend may need them
                continue
            try:
                shutil.move(p, os.path.join(tmp_hide_dir, base))
                moved.append(base)
            except Exception as e:
                log.warning("Could not move %s: %s", p, e)

        log.info("Starting sensor-routing in %s", workdir)

        # Ensure backend reads OUR parameters (stream only key progress)
        with silence_prints(
            "sensor-routing",
            info_patterns=[
                r"point mapping done",
                r"benefit_calculation done",
                r"Paths calculation completed",
                r"path finding done",
                r"route finding done",
                r"Execution time",
                r"all done",
            ],
        ):
            sensor_routing(
                params["sn"],  # segments per class
                params["md"],  # max distance
                params["wd"],  # working directory
                params["tl"],  # time limit
                params["oo"],  # objective
                params["mai"],  # max ACO iteration
                params["an"],  # number of ants
                params["ir"],  # reversed network
                params["lbf"],  # lower benefit limit
            )

        # Post-process: create a 4326 route layer if solution exists
        route_fc = build_solution_route_4326(workdir)
        if route_fc or os.path.isfile(os.path.join(transient_dir, "solution.json")):
            success = True
            message = "Routing abgeschlossen. Route wird angezeigt."
            level = "success"
        else:
            pf_path = os.path.join(transient_dir, "pf_output.json")
            if os.path.isfile(pf_path):
                success = True
                message = "Routing abgeschlossen (pf_output)."
                level = "success"

    except Exception as e:
        if os.path.isfile(os.path.join(transient_dir, "solution.json")):
            success = True
            message = "Routing abgeschlossen (mit Warnungen)."
            level = "warning"
            log.warning("Routing raised but produced solution.json: %s", e)
        else:
            message = f"Routing fehlgeschlagen: {e}"
            level = "danger"
            log.exception("Routing failed")
    finally:
        # Always restore hidden files and release lock
        try:
            for base in list(moved):
                src = os.path.join(tmp_hide_dir, base)
                dst = os.path.join(input_dir, base)
                if os.path.exists(src):
                    try:
                        shutil.move(src, dst)
                    except Exception as e:
                        log.warning("Could not restore %s: %s", src, e)
            try:
                if os.path.isdir(tmp_hide_dir) and not os.listdir(tmp_hide_dir):
                    os.rmdir(tmp_hide_dir)
            except Exception:
                pass
        except Exception:
            pass
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception:
            pass

    # Signal the map to refresh (routing-complete=True)
    return (message, level, True, success)


# Hydrate hidden tags-dropdown so the same streets stay visible
@app.callback(
    Output(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value", allow_duplicate=True),
    Input(PARAMS_LOAD_BUTTON_ROUTING_PARAMS_ID, "n_intervals"),
    State(TAGS_LAST_SELECTION_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def _hydrate_tags_for_params(_n, last_selection):
    return last_selection or list(osm_tags_mapping.keys())
