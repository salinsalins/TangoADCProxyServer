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

sys.path.append('../TangoUtils')
import TangoServerPrototype
# from ..TangoUtils import TangoServerPrototype

from tango import AttrQuality, AttrWriteType, DispLevel, DeviceProxy, StdStringVector
from tango import DevState
from tango.server import attribute, command

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Adlink2204 ADC Proxy Python Tango Server'
APPLICATION_NAME_SHORT = 'TangoADCProxyServer'
APPLICATION_VERSION = '1.0'

a = StdStringVector()


class TangoADCProxyServer(TangoServerPrototype.TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME_SHORT

    channel_list = attribute(label="Channel list", dtype=[str],
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ,
                             unit="", format="%d",
                             min_value=1,
                             doc="Channel list [int]")

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
        self.data = {}
        self.info = {}
        self.proxy_device_name = self.config.get('proxy_device_name', 'binp/nbi/adc0')
        try:
            self.proxy_device = DeviceProxy(self.proxy_device_name)
            attributes = self.proxy_device.get_attribute_list()
            self.attributes = [str(a) for a in attributes]
            db = self.device.get_device_db()
            self.properties = db.get_device_attribute_property(self.proxy_device_name, self.attributes)
            self.selected_channels = []
            for attr in self.attributes:
                if attr.startswith("chany"):
                    # save_data and save_log flags
                    sdf = self.as_boolean(self.properties[attr].get("save_data", [False])[0])
                    slf = self.as_boolean(self.properties[attr].get("save_log", [False])[0])
                    if sdf or slf:
                        self.selected_channels.append(attr)
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
        self.selected_channels = []
        self.read_attribute_list()
        self.read_properties()
        for attr in self.attributes:
            if attr.startswith("chany"):
                # save_data and save_log flags
                sdf = self.as_boolean(self.properties[attr].get("save_data", [False])[0])
                slf = self.as_boolean(self.properties[attr].get("save_log", [False])[0])
                if sdf or slf:
                    self.selected_channels.append(attr)
        return self.selected_channels

    def read_attribute_list(self):
        attributes = self.proxy_device.get_attribute_list()
        self.attributes = [str(a) for a in attributes]
        return self.attributes

    def read_properties(self):
        db = self.device.get_device_db()
        self.properties = db.get_device_attribute_property(self.proxy_device_name, self.attributes)
        return self.properties

    @command(dtype_in=str, dtype_out=[float])
    def read_data(self, channel):
        if channel in self.selected_channels:
            return self.data[channel]

    @command(dtype_in=str, dtype_out=str)
    def read_info(self, channel):
        if channel in self.selected_channels:
            return str(self.info[channel])

    @command(dtype_in=str, dtype_out=str)
    def read_properties(self, channel):
        return str(self.properties[channel])


if __name__ == "__main__":
    TangoADCProxyServer.run_server()
