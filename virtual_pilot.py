from __future__ import annotations

import copy

_VIRTUAL_PILOT_CONFIG = {
    "modes": [
        {"code": "AP", "label": "AP", "title": "autopilot master"},
        {"code": "LVL", "label": "LVL", "title": "wing leveler"},
        {"code": "ALT", "label": "ALT", "title": "altitude hold"},
        {"code": "ATT", "label": "ATT", "title": "auto throttle"},
        {"code": "TER", "label": "TER", "title": "terrain follow"},
        {"code": "HDG", "label": "HDG", "title": "heading hold"},
        {"code": "take off", "label": "take off", "title": "take off"},
        {"code": "land", "label": "land", "title": "land"},
    ],
    "notes": [
        "Virtual Pilot is the Pomax-port branch: a map-first server/client virtual pilot harness, rather than the old PID-vs-WAF comparison.",
        "This branch keeps a single navigation map with AP toggles, save/load/reset route behavior, and a single active virtual-pilot controller.",
    ],
}


def get_virtual_pilot_config() -> dict:
    return copy.deepcopy(_VIRTUAL_PILOT_CONFIG)
