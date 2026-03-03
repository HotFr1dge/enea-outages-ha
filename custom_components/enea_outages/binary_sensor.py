"""Platform for binary_sensor integration."""

from __future__ import annotations

import logging
from datetime import datetime

from enea_outages.client import EneaOutagesClient
from enea_outages.models import Outage, OutageType
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_BRANCH, CONF_DISTRIBUTION_AREA, CONF_QUERY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    query = config_entry.data.get(CONF_QUERY, "")

    entry_coordinators = hass.data[DOMAIN][config_entry.entry_id]
    planned_coordinator = entry_coordinators[OutageType.PLANNED]
    unplanned_coordinator = entry_coordinators[OutageType.UNPLANNED]

    async_add_entities([
        EneaOutagesActiveBinarySensor(
            planned_coordinator,
            unplanned_coordinator,
            config_entry,
            BinarySensorEntityDescription(
                key=f"{config_entry.entry_id}_outage_active",
                translation_key="outage_active",
                icon="mdi:power-plug-off",
            ),
            query,
        )
    ])


class EneaOutagesActiveBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor to indicate if any outage is currently active."""

    _attr_has_entity_name = True

    def __init__(
        self,
        planned_coordinator,
        unplanned_coordinator,
        config_entry: ConfigEntry,
        entity_description: BinarySensorEntityDescription,
        query: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(planned_coordinator)
        self._unplanned_coordinator = unplanned_coordinator
        self.entity_description = entity_description
        self._config_entry = config_entry
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

    def _filter_outages(self, all_outages: list[Outage]) -> list[Outage]:
        """Filter outages by query if provided."""
        if not all_outages:
            return []
        if self._query:
            return [
                o for o in all_outages
                if EneaOutagesClient._description_matches_query(o.description, self._query)
            ]
        return all_outages

    @property
    def is_on(self) -> bool | None:
        """Return true if any outage is currently active."""
        now = datetime.now()

        for outage in self._filter_outages(self.coordinator.data):
            if outage.start_time and outage.end_time and outage.start_time <= now <= outage.end_time:
                return True

        for outage in self._filter_outages(self._unplanned_coordinator.data):
            if outage.end_time and now <= outage.end_time:
                return True

        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._unplanned_coordinator.async_add_listener(self._handle_coordinator_update)
        )