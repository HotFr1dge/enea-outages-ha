"""The Enea Outages integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from functools import partial

from enea_outages.client import EneaOutagesClient
from enea_outages.models import Outage, OutageType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_BRANCH,
    CONF_DISTRIBUTION_AREA,
    DEFAULT_PLANNED_SCAN_INTERVAL,
    DEFAULT_UNPLANNED_SCAN_INTERVAL,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

# Cache of coordinators per (branch, distribution_area) and outage type
# Key: (branch, distribution_area) tuple
# Value: dict[OutageType, DataUpdateCoordinator]
COORDINATORS: dict[tuple[str, str], dict[OutageType, DataUpdateCoordinator]] = {}


class EneaOutagesOutageTypeCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Enea Outages data for a specific outage type."""

    def __init__(
        self,
        hass: HomeAssistant,
        branch: str,
        distribution_area: str,
        outage_type: OutageType,
    ) -> None:
        """Initialize."""
        self.branch = branch
        self.distribution_area = distribution_area
        self.outage_type = outage_type
        update_interval = (
            DEFAULT_PLANNED_SCAN_INTERVAL
            if outage_type == OutageType.PLANNED
            else DEFAULT_UNPLANNED_SCAN_INTERVAL
        )
        name = f"{DOMAIN}_{branch}"
        if distribution_area:
            name += f"_{distribution_area}"
        name += f"_{outage_type.value}"

        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self) -> list[Outage]:
        """Fetch data from Enea API for the specific outage type."""
        try:
            client = EneaOutagesClient()
            return await self.hass.async_add_executor_job(
                partial(
                    client.get_outages_for_branch,
                    branch=self.branch,
                    outage_type=self.outage_type,
                    distribution_area=self.distribution_area,
                )
            )
        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with Enea API for {self.outage_type.name} "
                f"in {self.branch} (area: {self.distribution_area or 'all'}): {err}"
            ) from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enea Outages from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    branch = entry.data[CONF_BRANCH]
    distribution_area = entry.data.get(CONF_DISTRIBUTION_AREA, "")
    cache_key = (branch, distribution_area)

    if cache_key not in COORDINATORS:
        COORDINATORS[cache_key] = {}

    # Setup Planned Outages Coordinator
    if OutageType.PLANNED not in COORDINATORS[cache_key]:
        planned_coordinator = EneaOutagesOutageTypeCoordinator(
            hass, branch, distribution_area, OutageType.PLANNED
        )
        await planned_coordinator.async_config_entry_first_refresh()
        COORDINATORS[cache_key][OutageType.PLANNED] = planned_coordinator
    else:
        planned_coordinator = COORDINATORS[cache_key][OutageType.PLANNED]

    # Setup Unplanned Outages Coordinator
    if OutageType.UNPLANNED not in COORDINATORS[cache_key]:
        unplanned_coordinator = EneaOutagesOutageTypeCoordinator(
            hass, branch, distribution_area, OutageType.UNPLANNED
        )
        await unplanned_coordinator.async_config_entry_first_refresh()
        COORDINATORS[cache_key][OutageType.UNPLANNED] = unplanned_coordinator
    else:
        unplanned_coordinator = COORDINATORS[cache_key][OutageType.UNPLANNED]

    hass.data[DOMAIN][entry.entry_id] = {
        OutageType.PLANNED: planned_coordinator,
        OutageType.UNPLANNED: unplanned_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register the service for manual refresh
    async def handle_update_all_coordinators(call):
        for area_coords in COORDINATORS.values():
            for coordinator in area_coords.values():
                await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "update", handle_update_all_coordinators)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        branch = entry.data[CONF_BRANCH]
        distribution_area = entry.data.get(CONF_DISTRIBUTION_AREA, "")
        cache_key = (branch, distribution_area)

        hass.data[DOMAIN].pop(entry.entry_id)

        # Remove coordinators if no other entry is still using this (branch, distribution_area)
        still_used = any(
            entry_coords[OutageType.PLANNED].branch == branch
            and entry_coords[OutageType.PLANNED].distribution_area == distribution_area
            for entry_coords in hass.data[DOMAIN].values()
        )
        if not still_used:
            COORDINATORS.pop(cache_key, None)

    # If all config entries are unloaded, unregister the service
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, "update")

    return unload_ok