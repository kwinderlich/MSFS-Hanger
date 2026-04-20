from __future__ import annotations

import copy

_VIRTUAL_PILOT_CONFIG = {
    "symbol_directory": "/assets/vpilot",
    "modes": [
        {"code": "AP", "label": "AP", "title": "autopilot master"},
        {"code": "LVL", "label": "LVL", "title": "wing leveler"},
        {"code": "ALT", "label": "ALT", "title": "altitude hold"},
        {"code": "ATT", "label": "ATT", "title": "auto throttle"},
        {"code": "TER", "label": "TER", "title": "terrain follow"},
        {"code": "HDG", "label": "HDG", "title": "heading hold"},
        {"code": "take off", "label": "take off", "title": "take off"},
        {"code": "land", "label": "land", "title": "land"},
        {"code": "patrol", "label": "patrol", "title": "patrol route"},
        {"code": "go-around", "label": "go-around", "title": "go around"},
        {"code": "revalidate", "label": "revalidate", "title": "revalidate waypoints"},
    ],
    "notes": [
        "Build 233 starts the direct UI port branch: a screenshot-like navigation map, top toolbar, bottom AP bar, and symbol-directory driven waypoint markers.",
        "Virtual Pilot is the Pomax-port branch: a map-first server/client virtual pilot harness, rather than the old PID-vs-WAF comparison.",
        "This branch keeps a single navigation map with AP toggles, save/load/reset route behavior, and a single active virtual-pilot controller.",
    ],
}


def get_virtual_pilot_config() -> dict:
    return copy.deepcopy(_VIRTUAL_PILOT_CONFIG)
