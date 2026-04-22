from __future__ import annotations


def get_virtual_pilot_config() -> dict:
    return {
        'modes': [
            {'code': 'AP', 'label': 'AP'},
            {'code': 'LVL', 'label': 'LVL'},
            {'code': 'ALT', 'label': 'ALT'},
            {'code': 'ATT', 'label': 'ATT'},
            {'code': 'HDG', 'label': 'HDG'},
            {'code': 'TER', 'label': 'TER'},
            {'code': 'take off', 'label': 'Take Off'},
            {'code': 'land', 'label': 'Land'},
        ],
        'notes': [
            'Release 238 keeps MSFS Hangar as the shell and swaps in a Pomax-powered sidecar for SimConnect, map, and waypoint flying.',
            'The integrated engine is launched from inside Virtual Pilot and opens in the desktop app\'s native browser panel.',
            'Node is auto-detected; if it is missing on Windows, the app can download a portable Node runtime on first start for the integrated pilot.'
        ],
    }
