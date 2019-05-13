import datetime

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_WEEKDAY, ATTR_DATE
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify


DOMAIN = 'sensor'

CONF_RECYCLING_EPOCH = 'recycling_epoch'

WASTE_ONLY = 'waste_only'
WASTE_AND_RECYCLING = 'waste_and_recycling'
BIN_COLLECTION_TYPES = {
    WASTE_ONLY: 'Waste',
    WASTE_AND_RECYCLING: 'Waste & Recycling',
}
BIN_COLLECTION_ICON = {
    WASTE_ONLY: 'mdi:trash-can-outline',
    WASTE_AND_RECYCLING: 'mdi:recycle',
}

DEFAULT_NAME = 'Next Bin Collection'
DEFAULT_ICON = 'mdi:trash-can-outline'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_RECYCLING_EPOCH, default=DEFAULT_NAME): cv.date,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Setup the sensor platform."""
    sensor_name = config.get(CONF_NAME)
    recycling_epoch = config.get(CONF_RECYCLING_EPOCH)

    sensors = [
        NextBinCollectionSensor(hass, sensor_name, recycling_epoch),
        NextBinCollectionDateSensor(hass, sensor_name, recycling_epoch),
    ]

    for sensor in sensors:
        async_track_point_in_utc_time(
            hass, sensor.point_in_time_listener, sensor.get_next_interval())

    async_add_entities(sensors, True)


class BaseNextBinCollectionSensor(Entity):

    def __init__(self, hass, name, recycling_epoch):
        """Initialize the sensor."""
        self.hass = hass
        self._name = name
        self._recycling_epoch = recycling_epoch

        self._state = None
        self._next_date = None
        self._type = None

        self._update_internal_state(dt_util.utcnow())

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        return BIN_COLLECTION_ICON.get(self._state, DEFAULT_ICON)

    @property
    def device_state_attributes(self):
        return {
            ATTR_DATE: self._next_date.isoformat(),
            CONF_WEEKDAY: self._next_date.strftime('%A'),
        }

    def _update_internal_state(self, now):
        from dateutil import relativedelta

        today = dt_util.as_local(now).date()
        bin_day = relativedelta.weekdays[self._recycling_epoch.weekday()]
        self._next_date = \
            today + relativedelta.relativedelta(weekday=bin_day)

        # If next date is a factor of 2 weeks away from epoch, it is recycling
        self._type = WASTE_AND_RECYCLING if \
            ((self._next_date - self._recycling_epoch).days / 7) % 2 == 0 \
            else WASTE_ONLY

    def get_next_interval(self, now=None):
        """Compute next time update should occur (eg first thing tomorrow)."""
        if now is None:
            now = dt_util.utcnow()
        start_of_day = dt_util.start_of_local_day(dt_util.as_local(now))
        return start_of_day + datetime.timedelta(days=1)

    @callback
    def point_in_time_listener(self, now):
        """Update state and schedule same listener to run again."""
        self._update_internal_state(now)
        self.async_schedule_update_ha_state()
        async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval())


class NextBinCollectionSensor(BaseNextBinCollectionSensor):

    def _update_internal_state(self, now):
        super()._update_internal_state(now)

        type_readable = BIN_COLLECTION_TYPES[self._type]

        today = dt_util.as_local(now).date()
        difference = self._next_date - today

        if (difference.days == 0):
            humanisation = 'Today'
        elif (difference.days == 1):
            humanisation = 'Tomorrow'
        else:
            weekday = self._next_date.strftime('%A')
            if (difference.days < 8):
                humanisation = f'This {weekday}'
            else:
                humanisation = f'Next {weekday}'

        self._state = f'{humanisation} ({type_readable})'


class NextBinCollectionDateSensor(BaseNextBinCollectionSensor):

    def __init__(self, hass, name, recycling_epoch):
        super().__init__(hass, name, recycling_epoch)
        self.entity_id = f'{DOMAIN}.{slugify(name)}_date'

    def _update_internal_state(self, now):
        super()._update_internal_state(now)
        self._state = self._next_date.isoformat()
