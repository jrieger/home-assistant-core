"""Sensor platform for GPSD integration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_ELEVATION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MODE,
    ATTR_TIME,
    EntityCategory,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import GPSDConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_CLIMB = "climb"
ATTR_SPEED = "speed"
ATTR_TOTAL_SATELLITES = "total_satellites"
ATTR_USED_SATELLITES = "used_satellites"

DEFAULT_NAME = "GPS"

_MODE_VALUES = {2: "2d_fix", 3: "3d_fix"}


def get_gpsd_mode(data: dict[str, Any]) -> str | None:
    """Extract and map the GPSD fix mode."""
    if (mode_val := data.get("mode")) is None:
        return None
    try:
        return _MODE_VALUES.get(int(mode_val))
    except ValueError, TypeError:
        return None


def count_total_satellites_fn(data: dict[str, Any]) -> int | None:
    """Count the number of total satellites."""
    satellites = data.get("satellites")
    if satellites is None:
        return None
    try:
        return len(satellites)
    except TypeError:
        return None


def count_used_satellites_fn(data: dict[str, Any]) -> int | None:
    """Count the number of used satellites."""
    satellites = data.get("satellites")
    if satellites is None:
        return None

    try:
        return sum(
            1
            for sat in satellites
            if getattr(sat, "used", False) is True
            or (isinstance(sat, dict) and sat.get("used") is True)
        )
    except TypeError:
        return None


@dataclass(frozen=True, kw_only=True)
class GpsdSensorDescription(SensorEntityDescription):
    """Class describing GPSD sensor entities."""

    value_fn: Callable[[dict[str, Any]], StateType | datetime]


SENSOR_TYPES: tuple[GpsdSensorDescription, ...] = (
    GpsdSensorDescription(
        key=ATTR_MODE,
        translation_key=ATTR_MODE,
        name=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_MODE_VALUES.values()),
        value_fn=get_gpsd_mode,
    ),
    GpsdSensorDescription(
        key=ATTR_LATITUDE,
        translation_key=ATTR_LATITUDE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("lat"),
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_LONGITUDE,
        translation_key=ATTR_LONGITUDE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("lon"),
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_ELEVATION,
        translation_key=ATTR_ELEVATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=lambda data: data.get("alt") or data.get("altHAE"),
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_TIME,
        translation_key=ATTR_TIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.get("time"),
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_SPEED,
        translation_key=ATTR_SPEED,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        value_fn=lambda data: data.get("speed"),
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_CLIMB,
        translation_key=ATTR_CLIMB,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        value_fn=lambda data: data.get("climb"),
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_TOTAL_SATELLITES,
        translation_key=ATTR_TOTAL_SATELLITES,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=count_total_satellites_fn,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_USED_SATELLITES,
        translation_key=ATTR_USED_SATELLITES,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=count_used_satellites_fn,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GPSDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the GPSD component."""
    client = config_entry.runtime_data
    gpsd_data: dict[str, Any] = {}

    entities = [
        GpsdSensor(gpsd_data, config_entry.entry_id, description)
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities)

    async def _listen_gpsd() -> None:
        try:
            async with client:
                async for response in client:
                    data = (
                        response.model_dump()
                        if hasattr(response, "model_dump")
                        else dict(response)
                    )
                    gpsd_data.update({k: v for k, v in data.items() if v is not None})
                    for entity in entities:
                        if entity.hass:
                            entity.async_write_ha_state()
        except asyncio.CancelledError:
            pass

    config_entry.async_create_background_task(hass, _listen_gpsd(), "gpsd_listener")


class GpsdSensor(SensorEntity):
    """Representation of a GPS receiver available via GPSD."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: GpsdSensorDescription

    def __init__(
        self,
        gpsd_data: dict[str, Any],
        unique_id: str,
        description: GpsdSensorDescription,
    ) -> None:
        """Initialize the GPSD sensor."""
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{unique_id}-{self.entity_description.key}"
        self.gpsd_data = gpsd_data

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of GPSD."""
        return self.entity_description.value_fn(self.gpsd_data)
