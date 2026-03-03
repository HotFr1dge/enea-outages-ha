"""Config flow for Enea Outages integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from enea_outages.client import EneaOutagesClient
from .const import DOMAIN, CONF_BRANCH, CONF_DISTRIBUTION_AREA, CONF_QUERY, DEFAULT_BRANCH

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enea Outages."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._branch: str = DEFAULT_BRANCH
        self._available_branches: list[str] = []
        self._available_distribution_areas: list[tuple[str, str]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 1: select branch."""
        errors: dict[str, str] = {}

        try:
            client = EneaOutagesClient()
            self._available_branches = await self.hass.async_add_executor_job(
                client.get_available_branches
            )
        except Exception as e:
            _LOGGER.error("Failed to get available branches: %s", e)
            errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            self._branch = user_input[CONF_BRANCH]
            return await self.async_step_distribution_area()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_BRANCH, default=DEFAULT_BRANCH): vol.In(
                    self._available_branches or [DEFAULT_BRANCH]
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_distribution_area(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: select distribution area (optional)."""
        errors: dict[str, str] = {}

        try:
            client = EneaOutagesClient()
            self._available_distribution_areas = await self.hass.async_add_executor_job(
                client.get_available_distribution_areas, self._branch
            )
        except Exception as e:
            _LOGGER.error("Failed to get distribution areas for %s: %s", self._branch, e)
            # Non-fatal — proceed without distribution area selection
            self._available_distribution_areas = []

        if user_input is not None:
            distribution_area_name = user_input.get(CONF_DISTRIBUTION_AREA, "")
            # Resolve name → id
            distribution_area_id = ""
            if distribution_area_name:
                area_map = {
                    name: area_id
                    for area_id, name in self._available_distribution_areas
                }
                distribution_area_id = area_map.get(distribution_area_name, "")

            return await self.async_step_query(
                prefill={
                    CONF_BRANCH: self._branch,
                    CONF_DISTRIBUTION_AREA: distribution_area_id,
                }
            )

        area_names = [""] + [name for _, name in self._available_distribution_areas]
        data_schema = vol.Schema(
            {
                vol.Optional(CONF_DISTRIBUTION_AREA, default=""): vol.In(area_names),
            }
        )

        return self.async_show_form(
            step_id="distribution_area", data_schema=data_schema, errors=errors
        )

    async def async_step_query(
        self,
        user_input: dict[str, Any] | None = None,
        prefill: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Step 3: enter optional free-text query (city / street)."""
        errors: dict[str, str] = {}

        # prefill carries data from previous steps
        if prefill:
            self._entry_data = prefill

        if user_input is not None:
            data = {**self._entry_data, CONF_QUERY: user_input.get(CONF_QUERY, "")}

            branch = data[CONF_BRANCH]
            distribution_area = data.get(CONF_DISTRIBUTION_AREA, "")
            query = data.get(CONF_QUERY, "")

            unique_id = branch
            if distribution_area:
                unique_id += f"_{distribution_area}"
            if query:
                unique_id += f"_{query.replace(' ', '_')}"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            title = branch
            if distribution_area:
                # Find human-readable area name for the title
                area_name = next(
                    (name for aid, name in self._available_distribution_areas if aid == distribution_area),
                    distribution_area,
                )
                title += f" – {area_name}"
            if query:
                title += f" ({query})"

            return self.async_create_entry(title=title, data=data)

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_QUERY, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="query", data_schema=data_schema, errors=errors
        )