from __future__ import annotations

import copy
import math

_WE_ARE_FLYING_CONFIG = {
    "modes": [
        {"code": "WAF", "label": "WAF", "title": "we-are-flying virtual pilot"},
        {"code": "PATH", "label": "PATH", "title": "flight path policy"},
        {"code": "TURN", "label": "TURN", "title": "turn anticipation"},
        {"code": "TRIM", "label": "TRIM", "title": "trim/control law"},
        {"code": "LAND", "label": "LAND", "title": "landing phases planned"},
    ],
    "notes": [
        "We are-Flying Test is the map-first, path-policy side: own virtual pilot, own line-following policy, no stock HDG/NAV dependency.",
        "This harness compares a Pomax-style flight-path policy against the PID Test controller.",
    ],
}


def get_we_are_flying_config() -> dict:
    return copy.deepcopy(_WE_ARE_FLYING_CONFIG)


def normalize_heading(value: float | None) -> float | None:
    if value is None:
        return None
    return (float(value) + 360.0) % 360.0


def heading_error_deg(current: float | None, target: float | None) -> float:
    cur = normalize_heading(current)
    tgt = normalize_heading(target)
    if cur is None or tgt is None:
        return 0.0
    diff = (tgt - cur + 540.0) % 360.0 - 180.0
    return diff


def blend_heading(current: float | None, target: float | None, *, max_step_deg: float = 3.5, blend: float = 0.35) -> float | None:
    cur = normalize_heading(current)
    tgt = normalize_heading(target)
    if tgt is None:
        return cur
    if cur is None:
        return tgt
    err = heading_error_deg(cur, tgt)
    step = max(-abs(max_step_deg), min(abs(max_step_deg), err * max(0.0, min(1.0, blend))))
    return normalize_heading(cur + step)


def path_heading(path_heading_deg: float, signed_cross_nm: float, *, lookahead_nm: float, current_track_deg: float | None = None) -> float:
    """A gentler path policy inspired by the are-we-flying approach.

    It uses the lookahead path heading as the primary target, applies a limited
    cross-track intercept correction, and damps the result against current track
    to avoid the endless circling/overcorrection seen in the PID controller.
    """
    base = normalize_heading(path_heading_deg) or 0.0
    lookahead = max(0.08, float(lookahead_nm or 0.08))
    # gentler intercept than the PID side
    intercept = math.degrees(math.atan2(float(signed_cross_nm) * 0.65, lookahead))
    intercept = max(-12.0, min(12.0, intercept))
    desired = normalize_heading(base - intercept) or base
    if current_track_deg is not None:
        # only move partway each tick, like a higher-level flight law
        smoothed = blend_heading(current_track_deg, desired, max_step_deg=2.6, blend=0.28)
        return normalize_heading(smoothed if smoothed is not None else desired) or desired
    return desired


def surface_profile() -> dict:
    return {
        'bank_limit_deg': 8.0,
        'aileron_limit': 0.28,
        'bank_gain': 0.12,
        'heading_gain': 0.018,
        'cross_gain': 4.2,
        'elevator_scale': 4300,
        'throttle_gain': 0.24,
        'pitch_limit_down': -2.0,
        'pitch_limit_up': 3.0,
    }
