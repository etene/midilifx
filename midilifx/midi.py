"""The module at the center of the action, translates MIDI events for an Lifx light."""
import logging
from typing import AsyncIterator

from mido.messages import BaseMessage

from midilifx.colors import note_to_hsl, pitch_to_temp
from midilifx.lights import LifxLight

LOG = logging.getLogger(__name__)

MIDI_CC_MODULATION = 1


async def midi_light(
        midi_events: AsyncIterator[BaseMessage],
        channels: set[int],
        initial_transition_duration: int = 0,
        ):
    """Changes the colors of a detected Lifx light based on MIDI messages."""
    assert channels, "midi_light is useless without channels"
    # A dict of currently playing notes and their velocities
    currently_playing: dict[int, int] = {}
    async with LifxLight(initial_transition_duration=initial_transition_duration) as light:
        LOG.info("Connected to %r (%s) at %s", light.name, light.product.name, light.ip_address)
        LOG.info("Listening for MIDI events on channel(s) %s", channels)
        async for evt in midi_events:
            if getattr(evt, "channel", None) in channels:
                LOG.debug("%s received on channel %d", evt.type, evt.channel)
                match evt:
                    case BaseMessage(type="note_on") if evt.velocity:
                        currently_playing[evt.note] = evt.velocity
                    case BaseMessage(type="note_off"):
                        currently_playing.pop(evt.note, None)
                    case BaseMessage(type="pitchwheel"):
                        temp = pitch_to_temp(
                            pitch=evt.pitch,
                            min_temp=light.product.min_kelvin,
                            max_temp=light.product.max_kelvin,
                        )
                        light.set_temperature(temp)
                        # Changing color temp. already updates the bulb.
                        # No need to call set_color below.
                        continue
                    case BaseMessage(type="control_change") if evt.control == MIDI_CC_MODULATION:
                        light.set_transition_duration(evt.value * 4)
                        # Changing transition duration does not trigger a change,
                        # it's for the next color change. No need to call set_color.
                        continue
                    case _:
                        continue

                LOG.debug("Currently playing notes: %s", currently_playing)
                if play_list := list(currently_playing.items()):
                    # set the color to the first currently playing note and velocity
                    light.set_color(note_to_hsl(*play_list[0]))
                else:
                    # turn "off" the light (ie set its brightness to 0), there is no note
                    light.set_color(None)
