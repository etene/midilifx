"""The module at the center of the action, translates MIDI events for an Lifx light."""
import logging
from typing import AsyncIterator

from mido.messages import BaseMessage

from midilifx.colors import note_to_hsl, pitch_to_temp
from midilifx.lights import LifxLight

LOG = logging.getLogger(__name__)

MIDI_CC_MODULATION = 1


async def midi_light(midi_events: AsyncIterator[BaseMessage], channels: set[int]):
    """Changes the colors of a detected Lifx light based on MIDI messages."""
    # A dict of currently playing notes and their velocities
    currently_playing: dict[int, int] = {}
    async with LifxLight() as light:
        LOG.info("Listening for events on channel(s) %s", channels)
        async for evt in midi_events:
            if getattr(evt, "channel", None) in channels:
                LOG.debug("MIDI event received: %s", evt)
                match evt:
                    case BaseMessage(type="note_on") if evt.velocity:
                        currently_playing[evt.note] = evt.velocity
                    case BaseMessage(type="note_off"):
                        currently_playing.pop(evt.note, None)
                    case BaseMessage(type="pitchwheel"):
                        light.set_temperature(pitch_to_temp(evt.pitch))
                    case BaseMessage(type="control_change") if evt.control == MIDI_CC_MODULATION:
                        light.set_transition_duration(evt.value * 4)
                        continue

                LOG.debug("Currently playing notes: %s", currently_playing)
                if play_list := list(currently_playing.items()):
                    # set the color to the first currently playing note and velocity
                    light.set_color(note_to_hsl(*play_list[0]))
                else:
                    light.set_color(None)
