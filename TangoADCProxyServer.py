#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Adlink2204 ADC Proxy Tango Device server
A. L. Sanin, started 13.01.2023
"""
import json
import sys

import logging
import time
from math import isnan

import numpy
import tango

from log_exception import log_exception

sys.path.append('../TangoUtils')
from TangoServerPrototype import TangoServerPrototype as TangoServerPrototype
# from ..TangoUtils import TangoServerPrototype

from tango import AttrQuality, AttrWriteType, DispLevel, DeviceProxy, StdStringVector, AttributeInfoListEx
from tango import DevState
from tango.server import attribute, command

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Adlink2204 ADC Proxy Python Tango Server'
APPLICATION_NAME_SHORT = 'TangoADCProxyServer'
APPLICATION_VERSION = '1.0'

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
        self.attributes = []
        self.properties = {}
        self.channels = []
        self.data = {}
        self.info = {}
        self.proxy_device_name = self.config.get('root_device_name', 'binp/nbi/adc0')
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
        return self.proxy_device.read_attribute('Shot_id').value

    def read_Elapsed(self):
        return self.proxy_device.read_attribute('Elapsed').value

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
        self.set_running()
        return self.channels

    def read_attribute_list(self):
        attributes = self.proxy_device.get_attribute_list()
        self.attributes = [str(a) for a in attributes]
        self.set_running()
        return self.attributes

    def read_properties(self):
        db = self.proxy_device.get_device_db()
        self.properties = db.get_device_attribute_property(self.proxy_device_name, self.attributes)
        self.set_running()
        return self.properties

    @command(dtype_in=str, dtype_out=[float])
    def read_channel_data(self, channel):
        if channel in self.channels and channel in self.data:
            self.set_running()
            return self.data[channel].value
        else:
            self.logger.debug(f'No data for channel {channel}')
            self.set_fault(f'No data for channel {channel}')
            return numpy.zeros((1,))

    @command(dtype_in=str, dtype_out=str)
    def read_channel_info(self, channel):
        if channel in self.channels and channel in self.info:
            # a = AttributeInfoListEx()
            self.set_running()
            return str(self.info[channel])
        else:
            self.logger.debug(f'No info for channel {channel}')
            self.set_fault(f'No info for channel {channel}')
            return ''

    @command(dtype_in=str, dtype_out=str)
    def read_channel_properties(self, channel):
        self.set_running()
        return str(self.properties[channel])

    def read_data(self):
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
    if avg > 1:
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
        if dev.last_shot != dev.proxy_device.read_attribute('Shot_id').value:
            dev.read_data()
            dev.read_info()
    time.sleep(1.0)


if __name__ == "__main__":
    TangoADCProxyServer.run_server(event_loop=looping)
