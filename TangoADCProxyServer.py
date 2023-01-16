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

sys.path.append('../TangoUtils')
from TangoServerPrototype import TangoServerPrototype as TangoServerPrototype
# from ..TangoUtils import TangoServerPrototype

from tango import AttrQuality, AttrWriteType, DispLevel, DeviceProxy, StdStringVector
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
                             unit="", format="%d",
                             min_value=1,
                             doc="Channel list [str]")

    Shot_id = attribute(name="Shot_id", label="Shot_id", forwarded=True)
    Elapsed = attribute(name="Elapsed", label="Elapsed", forwarded=True)

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
        self.proxy_device_name = self.config.get('proxy_device_name', 'binp/nbi/adc0')
        try:
            self.proxy_device = DeviceProxy(self.proxy_device_name)
            attributes = self.proxy_device.get_attribute_list()
            self.attributes = [str(a) for a in attributes]
            db = self.device.get_device_db()
            self.properties = db.get_device_attribute_property(self.proxy_device_name, self.attributes)
            for attr in self.attributes:
                if attr.startswith("chany"):
                    # save_data and save_log flags
                    sdf = self.as_boolean(self.properties[attr].get("save_data", [False])[0])
                    slf = self.as_boolean(self.properties[attr].get("save_log", [False])[0])
                    if sdf or slf:
                        self.channels.append(attr)
                        self.data[attr] = {}
                        self.info[attr] = {}
            self.last_shot = self.Shot_id
            self.set_running('Initialization completed')
        except:
            self.set_fault('Initialization error')
            self.error(f'Error initializing {self}')

    def delete_device(self):
        super().delete_device()
        self.proxy_device = None

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
                    self.selected_channels.append(attr)
        self.set_running()
        return self.channels

    def read_attribute_list(self):
        attributes = self.proxy_device.get_attribute_list()
        self.attributes = [str(a) for a in attributes]
        self.set_running()
        return self.attributes

    def read_properties(self):
        db = self.device.get_device_db()
        self.properties = db.get_device_attribute_property(self.proxy_device_name, self.attributes)
        self.set_running()
        return self.properties

    @command(dtype_in=str, dtype_out=[float])
    def read_data(self, channel):
        if channel in self.selected_channels:
            return self.data[channel]
        self.set_running()

    @command(dtype_in=str, dtype_out=str)
    def read_channel_info(self, channel):
        if channel in self.selected_channels:
            return str(self.info[channel])
        self.set_running()

    @command(dtype_in=str, dtype_out=str)
    def read_channel_properties(self, channel):
        self.set_running()
        return str(self.properties[channel])


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
    for dev in TangoServerPrototype.devices_list:
        if dev.last_shot != dev.Shot_id:
            dev.read_channel_list()
            for chan in dev.channels:
                attr = dev.self.proxy_device.read_attribute(chan)
                avg = int(dev.properties.get("save_avg", ['1'])[0])
                dev.data[attr] = average_aray(attr.value, avg)
                attr = dev.self.proxy_device.read_attribute(chan.replace('chany', 'chanx'))
                dev.data[attr] = average_aray(attr.value, avg)
            dev.last_shot = dev.Shot_id
    time.sleep(1.0)


if __name__ == "__main__":
    TangoADCProxyServer.run_server(event_loop=looping)
