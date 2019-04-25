import datetime
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_WEEKDAY, WEEKDAYS
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

CONF_RECYCLING_EPOCH = 'recycling_epoch'
ATTR_NEXT_BIN_COLLECTION_DATE = 'date'

WASTE_ONLY = 'waste_only'
WASTE_AND_RECYCLING = 'waste_and_recycling'
BIN_COLLECTION_ICON = {
    WASTE_ONLY: 'mdi:trash-can-outline',
    WASTE_AND_RECYCLING: 'mdi:recycle',
}

DATE_STR_FORMAT = '%A, %Y-%m-%d'

DEFAULT_NAME = 'Next Bin Collection'
DEFAULT_ICON = 'mdi:trash-can-outline'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RECYCLING_EPOCH, default=DEFAULT_NAME): cv.date,
    vol.Required(CONF_WEEKDAY): vol.Any(*WEEKDAYS),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Setup the sensor platform."""
    from dateutil import relativedelta

    sensor_name = config.get(CONF_NAME)
    weekday = config.get(CONF_WEEKDAY)
    recycling_epoch = config.get(CONF_RECYCLING_EPOCH)

    sensors = [
        NextBinCollectionSensor(hass, sensor_name, weekday, recycling_epoch),
        NextBinCollectionDateSensor(hass, f'{sensor_name} Date', weekday,
                                    recycling_epoch),
    ]

    for sensor in sensors:
        async_track_point_in_utc_time(
            hass, sensor.point_in_time_listener, sensor.get_next_interval())

    async_add_entities(sensors, True)


class NextBinCollectionSensor(Entity):

    def __init__(self, hass, name, weekday, recycling_epoch):
        """Initialize the sensor."""
        self.hass = hass
        self._name = name
        self._weekday = weekday
        self._recycling_epoch = recycling_epoch
        self._state = None
        self._next_bin_collection = None

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
            CONF_WEEKDAY: self._weekday,
            ATTR_NEXT_BIN_COLLECTION_DATE: self._next_bin_collection,
        }

    def _update_internal_state(self, now):
        from dateutil import relativedelta

        RD_WEEKDAYS = {
            'sun': relativedelta.SU,
            'mon': relativedelta.MO,
            'tue': relativedelta.TU,
            'wed': relativedelta.WE,
            'thu': relativedelta.TH,
            'fri': relativedelta.FR,
            'sat': relativedelta.SA,
        }

        weekday = RD_WEEKDAYS.get(self._weekday)

        today = dt_util.as_local(now).date()
        next_bin_collection = \
            today + relativedelta.relativedelta(weekday=weekday)

        self._state =  WASTE_AND_RECYCLING if \
            ((next_bin_collection - self._recycling_epoch).days / 7) % 2 == 0 \
            else WASTE_ONLY
        self._next_bin_collection = \
            next_bin_collection.strftime(DATE_STR_FORMAT)

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
        print('scheduling next run for ' + self.get_next_interval().isoformat())
        async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval())


class NextBinCollectionDateSensor(NextBinCollectionSensor):

    def _update_internal_state(self, now):
        super()._update_internal_state(now)
        self._state = self._next_bin_collection
