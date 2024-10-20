"""Commandline entrypoint module for midilifx. See main()."""
import argparse
import asyncio
import logging
from typing import AsyncIterator, Iterable

from mido import open_input  # pylint: disable=E0611
from mido.messages import BaseMessage

from midilifx.midi import midi_light

LOG = logging.getLogger("midi-light")


def int_set(value: str) -> set[int]:
    """For argparse use, parses the value as a set of integers."""
    return set(map(int, value.split(",")))


async def to_async_iterable(sync_iterable: Iterable[BaseMessage]) -> AsyncIterator[BaseMessage]:
    """Dark asyncio magic to turn a sync Mido MIDI message source into an async iterator."""
    it = iter(sync_iterable)
    while (value := await asyncio.to_thread(next, it, None)) is not None:
        yield value


async def main():
    """Commandline entrypoint that creates a virtual midi device to control a Lifx light."""
    args = get_psr().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="[%(levelname)s] %(funcName)s: %(message)s",
    )
    with open_input(args.port, virtual=True) as inport:
        LOG.info("Opened virtual MIDI port %r", inport.name)
        await midi_light(
            midi_events=to_async_iterable(inport),
            channels=args.channels,
            initial_transition_duration=args.transition,
        )


def get_psr():
    """Create the ArgumentParser for the commandline entrypoint."""
    psr = argparse.ArgumentParser(
        description="Detect a Lifx light and use it as a MIDI note visualizer.",
        epilog="Hue depends on notes, lightness on octaves and saturation on velocity."
    )
    psr.add_argument(
        "-p", "--port",
        type=str,
        metavar="NAME",
        default="midilifx",
        help="Name of the virtual MIDI device to create.",
    )
    psr.add_argument(
        "-c", "--channels",
        default={0},
        type=int_set,
        help="Channel(s) to listen on, comma separated.",
    )
    psr.add_argument(
        "-t", "--transition",
        default=0,
        type=int,
        metavar="MS",
        help="Initial transition duration for color changes. "
             "Can be altered through modulation MIDI CC events.",
    )
    psr.add_argument(
        "-d", "--debug",
        default=False,
        action="store_true",
        help="Show debug logs.",
    )
    return psr


if __name__ == "__main__":
    asyncio.run(main=main())
