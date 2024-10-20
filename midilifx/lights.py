"""Lifx lights management module."""
import asyncio
from dataclasses import dataclass
from functools import cached_property
import logging
import time
from typing import Callable, ClassVar

import aiolifx
from aiolifx.products import Product, products_dict
from aiolifx.aiolifx import Light

from midilifx.colors import HSLColor, HSLHue, pitch_to_temp

LOG = logging.getLogger(__name__)


class Lights:
    """Class used by aiolifx discovery to register and unregister lights."""

    INFO_WAIT_TRIES: ClassVar[int] = 30
    INFO_WAIT_DELAY: ClassVar[float] = .1

    def __init__(self) -> None:
        self.lights: dict[str, Light] = {}

    def register(self, light: Light):
        """aiolifx callback to a light to the internal list."""
        light.get_label()
        light.get_version()
        LOG.info("Found light at %s", light.mac_addr)
        self.lights[light.mac_addr] = light

    def unregister(self, light: Light):
        """Aiolifx callback to remove a light from the internal list."""
        self.lights.pop(light.mac_addr, None)
        LOG.warning("Unregistered light at %s", light.mac_addr)

    async def wait_for_light(self) -> Light:
        """Return the first detected aiolifx light."""
        LOG.debug("Waiting for a light to be detected...")
        while not self.lights:
            await asyncio.sleep(.2)
        first_mac = list(self.lights)[0]
        light = self.lights[first_mac]
        # wait a bit for label & product to show up
        for _ in range(self.INFO_WAIT_TRIES):
            await asyncio.sleep(self.INFO_WAIT_DELAY)
            LOG.debug("%s %s", light.label, light.product)
            if light.label is not None and light.product is not None:
                break
        else:
            raise RuntimeError("Failed to get label & product info from light "
                               f"after {self.INFO_WAIT_TRIES} attempts")
        return light


@dataclass
class BulbState:
    """Represents the target state for a bulb managed by LifxLight."""
    color: HSLColor
    temperature: int  # kelvins
    transition_duration: int  # milliseconds
    last_update: float  # timestamp
    needs_update: asyncio.Event

    @property
    def lifx_compat_color(self) -> tuple[int, int, int, int]:
        """Color in a format compatible with the aiolifx LightSetColor command."""
        return (
            round((self.color.hue * 65535) / 360.0),
            round((self.color.saturation * 65535) / 100.0),
            round((self.color.lightness * 65535) / 100.0),
            self.temperature,  # 2500 to 9000
        )


class LifxLight:
    """Control a lifx light's color, temperature & transition duration."""
    DEFAULT_OFF_COLOR = HSLColor(hue=HSLHue.RED, saturation=0, lightness=0)
    # According to aiolifx source code, devices can handle up to 20 messages/s
    UPDATE_INTERVAL = 0.05

    def __init__(self, initial_transition_duration: int = 0) -> None:
        self.lights = Lights()
        self.light_discovery = aiolifx.LifxDiscovery(
            loop=asyncio.get_running_loop(),
            parent=self.lights,
        )
        self._bulb: Light | None = None
        if initial_transition_duration < 0:
            raise ValueError("Transition duration must be positive")
        self._state = BulbState(
            color=self.DEFAULT_OFF_COLOR,
            temperature=pitch_to_temp(0),
            transition_duration=initial_transition_duration,
            last_update=time.time(),
            needs_update=asyncio.Event(),
        )
        self._running: bool = True
        self._scheduled_update: asyncio.Future | None = None
        self.bulb_update_task = asyncio.Task(self._update_bulb_forever())

    @property
    def bulb(self) -> Light:
        """The connected aiolifx Light."""
        assert self._bulb, "LifxLight must be used as a context manager."
        return self._bulb

    async def _get_local_ip(self) -> str:
        """Returns the local IP on the same network as the first detected light."""
        scanner = aiolifx.LifxScan(loop=self.light_discovery.loop)
        ips = await scanner.scan()
        assert len(ips) == 1, "No light found"
        LOG.debug("Local ip is %r", ips[0])
        return ips[0]

    async def __aenter__(self) -> 'LifxLight':
        ip = await self._get_local_ip()
        self.light_discovery.start(ip)
        self._bulb = await self.lights.wait_for_light()
        assert not self.bulb_update_task.done(), self.bulb_update_task.result()
        return self

    def _schedule_update(self, now: Callable[[], float] = time.time):
        """Ensure that the color is updated as soon as possible."""
        if self._scheduled_update and not self._scheduled_update.done():
            LOG.debug("Update already scheduled")
            return
        next_allowed_update = self._state.last_update + self.UPDATE_INTERVAL
        time_to_next_update = max(next_allowed_update - now(), 0.0)
        self._scheduled_update = asyncio.ensure_future(
            self._update_later(after=time_to_next_update)
        )

    async def _update_later(self, after: float = 0.0):
        """Scheduled by schedule_update() to trigger a bulb color update."""
        await asyncio.sleep(after)
        LOG.debug("Triggering update after %.2fms", after * 1000)
        self._state.needs_update.set()

    async def _update_bulb_forever(self):
        """Sends the current color to the bulb each time _state.needs_update is set."""
        state = self._state
        while self._running:
            # this event is rate limited by _schedule_update
            await state.needs_update.wait()
            state.needs_update.clear()
            self.bulb.fire_and_forget(
                msg_type=aiolifx.msgtypes.LightSetColor,
                payload={"color": state.lifx_compat_color, "duration": state.transition_duration},
                num_repeats=1
            )
            state.last_update = time.time()
        LOG.debug("exiting bulb color update loop")

    def set_color(self, value: HSLColor | None):
        """Set the HSL color. Brightness is set to 0 when the color is None."""
        if value is None:
            value = self.DEFAULT_OFF_COLOR
        if value == self._state.color:
            return
        LOG.debug("Requesting color change to %s", value)
        self._state.color = value
        self._schedule_update()

    def set_temperature(self, value: int):
        """Set the color temperature in Kelvins."""
        if value == self._state.temperature:
            return
        LOG.debug("Requesting temperature change to %dk", value)
        self._state.temperature = value
        self._schedule_update()

    def set_transition_duration(self, value: int):
        """Set the transition duration in milliseconds when changing colors."""
        LOG.debug("Changing color transition duration to %dms", value)
        self._state.transition_duration = value

    @cached_property
    def product(self) -> Product:
        """The aiolifx Product for this light."""
        return products_dict[self.bulb.product]

    @cached_property
    def name(self) -> str:
        """The light's label."""
        return self.bulb.label

    @cached_property
    def ip_address(self) -> str:
        """The light's IPv4 address."""
        return self.bulb.ip_addr

    async def __aexit__(self, *a, **kw):
        self._running = False
        self.set_color(None)
        if self._scheduled_update and not self.bulb_update_task.done():
            await self._scheduled_update
        self.light_discovery.cleanup()
