"""Sensors for each National Grid meter: grid power, energy and cost so far today, and the effective rate.

These are for dashboards and automations. The Energy dashboard uses the long-term statistics written by
coordinator.py instead (National Grid's data arrives late, and statistics put each hour in the right place).

Unique IDs are "<service point>_<key>": changing a key would create new entities and orphan the old ones.
"""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Create the four sensors for every meter the coordinator found."""
    coordinator = entry.runtime_data
    sensors = []
    for service_point in coordinator.meters:
        for sensor_class in (GridPowerSensor, EnergyTodaySensor, CostTodaySensor, RateSensor):
            sensors.append(sensor_class(coordinator, service_point))
    async_add_entities(sensors)


class NationalGridSensor(CoordinatorEntity, SensorEntity):
    """Shared base: one device per meter, and access to that meter's real-time reads."""

    _attr_has_entity_name = True
    key = ""  # set by each sensor; part of the unique ID

    def __init__(self, coordinator, service_point):
        """Attach the sensor to its meter's device."""
        super().__init__(coordinator)
        self.service_point = service_point
        self._attr_unique_id = f"{service_point}_{self.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, service_point)},
            "name": f"National Grid {service_point}",
            "manufacturer": "National Grid",
        }

    @property
    def reads(self):
        """This meter's real-time 15-minute reads from the last update, oldest first."""
        return self.coordinator.data.get(self.service_point) or []

    def kwh_imported_today(self):
        """Energy taken from the grid since local midnight (exported intervals count as zero)."""
        midnight = dt_util.start_of_local_day()
        return sum(max(read["value"], 0) for read in self.reads if read["start"] >= midnight)


class GridPowerSensor(NationalGridSensor):
    """Average power over the latest 15-minute interval: positive when importing, negative when exporting.

    That sign convention is what the Energy dashboard's "Standard" power measurement type expects.
    """

    key, _attr_name = "power", "Grid power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT

    @property
    def native_value(self):
        """Convert the latest interval's kWh into average kW."""
        if not self.reads:
            return None
        latest = self.reads[-1]
        hours = (latest["end"] - latest["start"]).total_seconds() / 3600
        return round(latest["value"] / hours, 3)

    @property
    def extra_state_attributes(self):
        """When the latest interval ended, so it's clear how fresh the value is."""
        if self.reads:
            return {"interval_end": self.reads[-1]["end"].isoformat()}
        return None


class EnergyTodaySensor(NationalGridSensor):
    """Energy imported from the grid today, from real-time reads. Resets at midnight."""

    key, _attr_name = "energy_today", "Energy imported today"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self):
        """Today's imported kWh."""
        return round(self.kwh_imported_today(), 3)


class CostTodaySensor(NationalGridSensor):
    """Approximate cost of today's imported energy, at the effective rate. Unknown until bills are fetched."""

    key, _attr_name = "cost_today", "Cost today"
    _attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_unit_of_measurement(self):
        """Home Assistant's configured currency."""
        return self.hass.config.currency

    @property
    def native_value(self):
        """Today's imported kWh times the effective rate."""
        if (rate := self.coordinator.rate(self.service_point)) is not None:
            return round(self.kwh_imported_today() * rate, 2)
        return None


class RateSensor(NationalGridSensor):
    """All-in cost per kWh, blended over the last three bills (total charges ÷ kWh)."""

    key, _attr_name = "rate", "Effective rate"
    _attr_suggested_display_precision = 4

    @property
    def native_unit_of_measurement(self):
        """Currency per kWh, for example USD/kWh."""
        return f"{self.hass.config.currency}/{UnitOfEnergy.KILO_WATT_HOUR}"

    @property
    def native_value(self):
        """The blended rate, or None until bills are fetched."""
        return self.coordinator.rate(self.service_point)
