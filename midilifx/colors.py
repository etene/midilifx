"""Color related constants & utilities."""
import enum
from functools import lru_cache
from typing import NamedTuple


class HSLHue(enum.IntEnum):
    """Human color names for Newton-based HSL hues."""
    RED = 0
    RED_ORANGE = 15
    ORANGE = 30
    ORANGE_YELLOW = 45
    YELLOW = 60
    YELLOW_GREEN = 90
    GREEN = 120
    GREEN_BLUE = 180
    BLUE = 240
    BLUE_INDIGO = 255
    INDIGO_VIOLET = 285
    VIOLET = 300
    VIOLET_RED = 330


class HSLColor(NamedTuple):
    """A triple of HSL color values."""
    hue: HSLHue  # 0 - 360
    saturation: int  # 0 - 100
    lightness: int  # 0 - 100


NEWTON_HUES = {
    'C': HSLHue.INDIGO_VIOLET,
    'C#': HSLHue.VIOLET,
    'D': HSLHue.VIOLET_RED,
    'D#': HSLHue.RED,
    'E': HSLHue.RED_ORANGE,
    'F': HSLHue.ORANGE_YELLOW,
    'F#': HSLHue.YELLOW,
    'G': HSLHue.YELLOW_GREEN,
    'G#': HSLHue.GREEN,
    'A': HSLHue.GREEN_BLUE,
    'A#': HSLHue.BLUE,
    'B': HSLHue.BLUE_INDIGO,
}

NOTE_NAMES = tuple(NEWTON_HUES)
TOTAL_NOTES = len(NOTE_NAMES)


@lru_cache(maxsize=None)
def note_to_hsl(midi_note: int, velocity: int) -> HSLColor:
    """Convert a midi note and velocity to a HSL color.

    The color is chosen based on Newton's color circle:
    https://commons.wikimedia.org/wiki/File:Newton%27s_colour_circle.png
    """
    note_name = NOTE_NAMES[midi_note % TOTAL_NOTES]
    octave = (midi_note // TOTAL_NOTES) + 1
    return HSLColor(
        hue=NEWTON_HUES[note_name],
        saturation=velocity / 127 * 100,
        lightness=octave / 11 * 100,
    )


@lru_cache(maxsize=None)
def pitch_to_temp(pitch: int) -> int:
    """Convert a MIDI pitch (-8192 to 8192) to a kelvin value between 2500 and 9000."""
    max_pitch = 8192
    assert -max_pitch <= pitch <= max_pitch
    min_temp = 2500
    max_temp = 9000
    return max_temp - int(
        (pitch + max_pitch) / (max_pitch * 2) * (max_temp - min_temp)
    )
