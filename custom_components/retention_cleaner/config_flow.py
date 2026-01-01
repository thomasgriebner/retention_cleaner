from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


class RetentionCleanerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Retention Cleaner."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        # MVP stub: we will implement the UI form in the next step.
        return self.async_abort(reason="not_implemented")