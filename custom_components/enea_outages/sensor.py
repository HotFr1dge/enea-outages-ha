"""Platform for sensor integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from enea_outages.client import EneaOutagesClient
from enea_outages.models import Outage, OutageType
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_BRANCH,
    CONF_DISTRIBUTION_AREA,
    CONF_QUERY,
    ATTR_DESCRIPTION,
    ATTR_START_TIME,
    ATTR_END_TIME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    query = config_entry.data.get(CONF_QUERY, "")

    entry_coordinators = hass.data[DOMAIN][config_entry.entry_id]
    planned_coordinator = entry_coordinators[OutageType.PLANNED]
    unplanned_coordinator = entry_coordinators[OutageType.UNPLANNED]

    entities = [
        EneaOutagesCountSensor(
            planned_coordinator,
            config_entry,
            OutageType.PLANNED,
            SensorEntityDescription(
                key=f"{config_entry.entry_id}_planned_outages_count",
                translation_key="planned_outages_count",
                icon="mdi:power-off",
            ),
            query,
        ),
        EneaOutagesCountSensor(
            unplanned_coordinator,
            config_entry,
            OutageType.UNPLANNED,
            SensorEntityDescription(
                key=f"{config_entry.entry_id}_unplanned_outages_count",
                translation_key="unplanned_outages_count",
                icon="mdi:power-off",
            ),
            query,
        ),
        EneaOutagesSummarySensor(
            planned_coordinator,
            config_entry,
            OutageType.PLANNED,
            SensorEntityDescription(
                key=f"{config_entry.entry_id}_planned_outages_summary",
                translation_key="planned_outages_summary",
                icon="mdi:calendar-clock",
            ),
            query,
        ),
        EneaOutagesSummarySensor(
            unplanned_coordinator,
            config_entry,
            OutageType.UNPLANNED,
            SensorEntityDescription(
                key=f"{config_entry.entry_id}_unplanned_outages_summary",
                translation_key="unplanned_outages_summary",
                icon="mdi:alert-outline",
            ),
            query,
        ),
    ]

    async_add_entities(entities)


class EneaOutagesBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Enea Outages sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        outage_type: OutageType,
        entity_description: SensorEntityDescription,
        query: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._config_entry = config_entry
        self._outage_type = outage_type
        self._query = query
        self._branch = config_entry.data[CONF_BRANCH]
        self._distribution_area = config_entry.data.get(CONF_DISTRIBUTION_AREA, "")

        self._attr_unique_id = f"{config_entry.entry_id}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=self._build_device_name(),
            model="Enea Outages Monitor",
            manufacturer="Enea Operator",
        )

    def _build_device_name(self) -> str:
        name = f"Enea Outages ({self._branch}"
        if self._distribution_area:
            name += f", {self._distribution_area}"
        if self._query:
            name += f" – {self._query}"
        name += ")"
        return name

    @property
    def _outages_data(self) -> list[Outage]:
        """Return coordinator data filtered by query if provided."""
        all_outages: list[Outage] = self.coordinator.data or []
        if self._query:
            return [
                o for o in all_outages
                if EneaOutagesClient._description_matches_query(o.description, self._query)
            ]
        return all_outages

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EneaOutagesCountSensor(EneaOutagesBaseSensor):
    """Sensor to report the count of Enea Outages."""

    @property
    def native_value(self) -> int:
        """Return the number of outages."""
        return len(self._outages_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        outages = sorted(
            self._outages_data,
            key=lambda o: (
                o.start_time if self._outage_type == OutageType.PLANNED else o.end_time
            ) or datetime.max,
        )
        return {
            "outages": [
                {
                    ATTR_DESCRIPTION: o.description,
                    ATTR_START_TIME: o.start_time.isoformat() if o.start_time else None,
                    ATTR_END_TIME: o.end_time.isoformat() if o.end_time else None,
                }
                for o in outages[:10]
            ]
        }


class EneaOutagesSummarySensor(EneaOutagesBaseSensor):
    """Sensor to report a summary of Enea Outages."""

    @property
    def native_value(self) -> str:
        """Return the summary of the next/current outage."""
        outages = self._outages_data
        if not outages:
            return "Brak"

        if self._outage_type == OutageType.PLANNED:
            outages = sorted(
                outages,
                key=lambda o: o.start_time or datetime.max,
            )
            o = outages[0]
            start = o.start_time.strftime("%Y-%m-%d %H:%M") if o.start_time else "Nieznany"
            end = o.end_time.strftime("%H:%M") if o.end_time else "Nieznany"
            return f"Od: {start} do: {end} ({o.description})"
        else:
            outages = sorted(
                outages,
                key=lambda o: o.end_time or datetime.max,
            )
            o = outages[0]
            end = o.end_time.strftime("%Y-%m-%d %H:%M") if o.end_time else "Nieznany"
            return f"Do: {end} ({o.description})"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        outages = sorted(
            self._outages_data,
            key=lambda o: (
                o.start_time if self._outage_type == OutageType.PLANNED else o.end_time
            ) or datetime.max,
        )
        return {
            "outages": [
                {
                    ATTR_DESCRIPTION: o.description,
                    ATTR_START_TIME: o.start_time.isoformat() if o.start_time else None,
                    ATTR_END_TIME: o.end_time.isoformat() if o.end_time else None,
                }
                for o in outages[:10]
            ]
        }