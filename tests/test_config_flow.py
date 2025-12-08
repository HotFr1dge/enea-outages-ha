"""Test the Enea Outages config flow."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enea_outages.const import DOMAIN, CONF_REGION, CONF_STREET


@pytest.mark.asyncio
async def test_form_user_no_street(hass: HomeAssistant) -> None:
    """Test we get the form and can configure an entry without a street."""
    with patch("custom_components.enea_outages.config_flow.EneaOutagesClient") as mock_client_class:
        mock_client_class.return_value.get_available_regions.return_value = ["Poznań", "Szczecin"]

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert not result["errors"]

        with patch(
            "custom_components.enea_outages.async_setup_entry",
            return_value=True,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_REGION: "Poznań",
                    CONF_STREET: "",
                },
            )
            await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Poznań"
        assert mock_client_class.return_value.get_available_regions.call_count == 2


@pytest.mark.asyncio
async def test_form_user_with_street(hass: HomeAssistant) -> None:
    """Test we get the form and can configure an entry with a street."""
    with patch("custom_components.enea_outages.config_flow.EneaOutagesClient") as mock_client_class:
        mock_client_class.return_value.get_available_regions.return_value = ["Poznań", "Szczecin"]

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert not result["errors"]

        with patch(
            "custom_components.enea_outages.async_setup_entry",
            return_value=True,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_REGION: "Szczecin",
                    CONF_STREET: "Wojska Polskiego",
                },
            )
            await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Szczecin, Wojska Polskiego"
        assert result2["data"] == {CONF_REGION: "Szczecin", CONF_STREET: "Wojska Polskiego"}
        assert mock_client_class.return_value.get_available_regions.call_count == 2


@pytest.mark.asyncio
async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error during region fetching."""
    with patch("custom_components.enea_outages.config_flow.EneaOutagesClient") as mock_client_class:
        mock_client_class.return_value.get_available_regions.side_effect = Exception("Connection error")

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_form_invalid_region(hass: HomeAssistant) -> None:
    """Test we handle an invalid region selection."""
    with patch("custom_components.enea_outages.config_flow.EneaOutagesClient") as mock_client_class:
        mock_client_class.return_value.get_available_regions.return_value = ["Poznań", "Szczecin"]

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        with pytest.raises(data_entry_flow.InvalidData):
            await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_REGION: "Invalid Region",
                    CONF_STREET: "Some Street",
                },
            )


@pytest.mark.asyncio
async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if the location is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REGION: "Poznań", CONF_STREET: "Testowa"},
        unique_id="Poznań_Testowa",
    ).add_to_hass(hass)

    with patch("custom_components.enea_outages.config_flow.EneaOutagesClient") as mock_client_class:
        mock_client_class.return_value.get_available_regions.return_value = ["Poznań", "Szczecin"]

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_REGION: "Poznań",
                CONF_STREET: "Testowa",
            },
        )

        assert result2["type"] == data_entry_flow.FlowResultType.ABORT
        assert result2["reason"] == "already_configured"
