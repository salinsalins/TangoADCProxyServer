#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Adlink2204 ADC Proxy Tango Device server
A. L. Sanin, started 13.01.2023
"""
import json
import sys
import time
import numpy

sys.path.append('../TangoUtils')
from log_exception import log_exception
from TangoServerPrototype import TangoServerPrototype as TangoServerPrototype

from tango import AttrQuality, AttrWriteType, DispLevel, DeviceProxy, StdStringVector, AttributeInfoListEx
from tango import DevState
from tango.server import attribute, command

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Adlink2204 ADC Proxy Python Tango Server'
APPLICATION_NAME_SHORT = 'TangoADCProxyServer'
APPLICATION_VERSION = '1.1'

a = StdStringVector()


class TangoADCProxyServer(TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME_SHORT

    channel_list = attribute(label="Channel list", dtype=[str],
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ,
                             max_dim_x=256,
                             unit="", format="%s",
                             doc="Channel list")

    Shot_id = attribute(label="Shot_id", dtype=int,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%d",
                        doc="Last shot number")

    Elapsed = attribute(label="Elapsed", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="s", format="%f",
                        doc="Elapsed time from last shot in seconds")

    reading = attribute(label="data_reading", dtype=bool,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%s",
                        doc="Data reding in progress flag")

    root_reading = attribute(label="root_data_reading", dtype=bool,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ,
                             unit="", format="%s",
                             doc="Root device data reding in progress flag")

    # server_nama = attribute(label="server_nama", dtype=str,
    #                         display_level=DispLevel.OPERATOR,
    #                         access=AttrWriteType.READ,
    #                         unit="", format="%s",
    #                         doc="Server name")

    # Shot_id = attribute(name="Shot_id", label="Shot_id", forwarded=True)
    # Elapsed = attribute(name="Elapsed", label="Elapsed", forwarded=True)

    def init_device(self):
        super().init_device()
        self.debug('Initialization')
        self.configure_tango_logging()
        self.time = time.time()
        self.set_state(DevState.INIT)
        self.proxy_device = None
        self.last_shot = -1
        self.last_elapsed = -1
        self.attributes = []
        self.properties = {}
        self.channels = []
        self.data = {}
        self.info = {}
        self.proxy_device_name = self.config.get('root_device_name', 'binp/nbi/adc0')
        self.data_reading = False
        self.root_data_reading = False
        try:
            self.proxy_device = DeviceProxy(self.proxy_device_name)
            self.read_channel_list()
            self.last_shot = self.proxy_device.read_attribute('Shot_id').value
            self.read_data()
            self.read_info()
            self.set_running('Initialization completed')
        except:
            log_exception('Initialization error')
            self.set_fault('Initialization error')
            self.error(f'Error initializing {self}')

    def delete_device(self):
        super().delete_device()
        self.proxy_device = None

    # def read_server_nama(self):
    #     # self.read_data()
    #     # self.read_info()
    #     self.set_running()
    #     return str(self.channels)

    def read_Shot_id(self):
        attr = self.proxy_device.read_attribute('Shot_id')
        if isinstance(attr, Exception):
            raise attr
        self.Shot_id.set_quality(attr.quality)
        self.Shot_id.set_time(attr.time)
        return attr.value

    def read_Elapsed(self):
        self.logger.debug('')
        attr = self.proxy_device.read_attribute('Elapsed')
        if isinstance(attr, Exception):
            raise attr
        self.logger.debug('%s'%attr)
        self.logger.debug('%s'%attr.quality)
        self.Elapsed.set_quality(attr.quality)
        self.Elapsed.set_time(attr.time)
        self.logger.debug('')
        return attr.value

    def read_channel_list(self):
        self.channels = []
        self.read_attribute_list()
        self.read_properties()
        for attr in self.attributes:
            if attr.startswith("chany"):
                # save_data and save_log flags
                sdf = as_boolean(self.properties[attr].get("save_data", [False])[0])
                slf = as_boolean(self.properties[attr].get("save_log", [False])[0])
                if sdf or slf:
                    self.channels.append(attr)
        # self.read_data()
        # self.read_info()
        qual = AttrQuality.ATTR_VALID
        self.channel_list.set_quality(qual)
        self.set_running()
        return self.channels

    def read_attribute_list(self):
        attributes = self.proxy_device.get_attribute_list()
        if isinstance(attributes, Exception):
            qual = AttrQuality.ATTR_INVALID
            self.attribute_list.set_quality(qual)
            raise attributes
        self.attributes = [str(a) for a in attributes]
        self.set_running()
        return self.attributes

    def read_reading(self):
        return self.data_reading

    def read_root_reading(self):
        return self.root_data_reading

    def read_properties(self):
        db = self.proxy_device.get_device_db()
        self.properties = db.get_device_attribute_property(self.proxy_device_name, self.attributes)
        self.set_running()
        return self.properties

    @command(dtype_in=str, dtype_out=[float])
    def read_channel_data(self, channel):
        if self.data_reading:
            self.logger.debug('Data reading is in progress')
            self.set_status('Data reading is in progress')
            result = numpy.zeros((1,))
            result[0] = -2.0
            return result
        if channel in self.data:
            self.set_running()
            return self.data[channel].value
        else:
            self.logger.debug(f'No data for channel {channel}')
            self.set_fault(f'No data for channel {channel}')
            return numpy.zeros((1,))

    @command(dtype_in=str, dtype_out=str)
    def read_channel_info(self, channel):
        if self.data_reading:
            self.logger.debug('Data reading is in progress')
            self.set_status('Data reading is in progress')
            return ''
        if channel in self.channels and channel in self.info:
            self.set_running()
            return str(self.info[channel]).replace("'", '"')
        else:
            self.logger.debug(f'No info for channel {channel}')
            self.set_fault(f'No info for channel {channel}')
            return ''

    @command(dtype_in=str, dtype_out=str)
    def read_channel_properties(self, channel):
        self.set_running()
        return str(self.properties[channel]).replace("'", '"')

    def read_data(self):
        if self.root_data_reading:
            self.logger.info('Root device data reading is in progress')
            return
        self.data_reading = True
        self.set_status('Data reading is in progress')
        for chan in self.channels:
            attr = self.proxy_device.read_attribute(chan)
            avg = int(self.properties[chan].get("save_avg", ['1'])[0])
            avg_value = average_aray(attr.value, avg)
            attr.value = avg_value
            attr.avg = avg
            self.data[chan] = attr
            chanx = chan.replace('chany', 'chanx')
            attr = self.proxy_device.read_attribute(chanx)
            avg_value = average_aray(attr.value, avg)
            attr.value = avg_value
            attr.avg = avg
            self.data[chanx] = attr
        self.last_shot = self.proxy_device.read_attribute('Shot_id').value
        self.data_reading = False
        self.set_status('Data reading finished')

    def read_info(self):
        self.info = self.proxy_device.get_attribute_config_ex(self.channels)


TRUE_VALUES = ('true', 'on', '1', 'y', 'yes')
FALSE_VALUES = ('false', 'off', '0', 'n', 'no')


def as_boolean(value):
    value = str(value)
    if value.lower() in TRUE_VALUES:
        return True
    if value.lower() in FALSE_VALUES:
        return False
    return None


def average_aray(arr, avg):
    if avg > 1 and arr is not None:
        m = len(arr) // avg
        if m > 0:
            y = arr[:(m * avg)]
            return numpy.average(y.reshape((m, avg)), 1)
        else:
            return numpy.average(arr)
    else:
        return arr


def looping():
    for dev in TangoServerPrototype.device_list:
        ev = dev.proxy_device.read_attribute('Elapsed').value
        if dev.last_elapsed > ev:
            dev.root_data_reding = True
        dev.last_elapsed = ev
        if dev.last_shot != dev.proxy_device.read_attribute('Shot_id').value:
            dev.root_data_reding = False
            dev.read_data()
            dev.read_info()
            dev.last_elapsed = dev.proxy_device.read_attribute('Elapsed').value
    time.sleep(1.0)


if __name__ == "__main__":
    TangoADCProxyServer.run_server(event_loop=looping)
