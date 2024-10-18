"""Lifx lights management module."""
import asyncio
from dataclasses import dataclass
import logging
import time
from typing import Callable

import aiolifx

from midilifx.colors import HSLColor, HSLHue, pitch_to_temp

LOG = logging.getLogger(__name__)


class Lights:
    """Class used by aiolifx discovery to register and unregister lights."""
    def __init__(self) -> None:
        self.lights: dict[str, aiolifx.aiolifx.Light] = {}

    def register(self, light: aiolifx.aiolifx.Light):
        """aiolifx allback to a light to the internal list."""
        light.get_label()
        light.get_location()
        light.get_version()
        light.get_group()
        light.get_wififirmware()
        light.get_hostfirmware()
        LOG.info("Found light at %s", light.mac_addr)
        self.lights[light.mac_addr] = light

    def unregister(self, light: aiolifx.aiolifx.Light):
        """Aiolifx callback to remove a light from the internal list."""
        self.lights.pop(light.mac_addr, None)
        LOG.warning("Unregistered light at %s", light.mac_addr)

    async def wait_for_light(self) -> aiolifx.aiolifx.Light:
        """Return the first detected aiolifx light."""
        LOG.debug("Waiting for a light to be detected...")
        while not self.lights:
            await asyncio.sleep(.2)
        first_mac = list(self.lights)[0]
        return self.lights[first_mac]


@dataclass
class BulbState:
    """Represents the target state for a bulb managed by LifxLight."""
    color: HSLColor
    temperature: int
    transition_duration: int
    last_update: float
    needs_update: asyncio.Event

    @property
    def lifx_compat_color(self) -> tuple[int, int, int, int]:
        """Color in a format compatible with the aiolifx LightSetColor command."""
        return (
            int(round((float(self.color.hue) * 65535.0) / 360.0)),
            int(round((float(self.color.saturation) * 65535.0) / 100.0)),
            int(round((float(self.color.lightness) * 65535.0) / 100.0)),
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
        self.bulb = None
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
        self.bulb = await self.lights.wait_for_light()
        return self

    def _schedule_update(self, now: Callable[[], float] = time.time):
        """Ensure that the color is updated as soon as possible."""
        if self._scheduled_update and not self._scheduled_update.done():
            LOG.debug("Update already scheduled")
            return
        current_time = now()
        next_allowed_update = self._state.last_update + self.UPDATE_INTERVAL
        time_to_next_update = next_allowed_update - current_time
        self._scheduled_update = asyncio.ensure_future(
            self._update_later(after=max(time_to_next_update, 0.0))
        )

    async def _update_later(self, after: float = 0.0):
        """Scheduled by schedule_update() to trigger a bulb color update."""
        await asyncio.sleep(after)
        LOG.debug("Triggering update after %.2fms", after * 1000)
        self._state.needs_update.set()

    async def _update_bulb_forever(self):
        """Sends the current color to the bulb each time _state.needs_update is set."""
        assert self.bulb, "LifxLight must be used as a context manager"
        state = self._state
        while self._running:
            # this event is rate limited by schedule_update
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
        """Set the HSL color."""
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

    async def __aexit__(self, *a, **kw):
        self._running = False
        self.set_color(None)
        if self._scheduled_update and not self.bulb_update_task.done():
            await self._scheduled_update
        self.light_discovery.cleanup()
