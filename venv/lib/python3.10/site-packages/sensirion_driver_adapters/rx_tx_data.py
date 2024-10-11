# -*- coding: utf-8 -*-
# (c) Copyright 2021 Sensirion AG, Switzerland

import logging
import re
import struct
from functools import reduce
from typing import Iterable

log = logging.getLogger(__name__)


def array_to_integer(element_bit_width: int, data: Iterable[int]) -> int:
    return reduce(lambda x, y: (x << element_bit_width) | y, data, 0)


class TxData:
    """Models the tx data that is exchanged. It it primarily a descriptor that knows how to convert structured
    data into a list of raw bytes"""

    string_match = re.compile(r'(?P<length>\d*)(?P<descriptor>(s))')

    def __init__(self, cmd_id,
                 descriptor,
                 device_busy_delay=0.0,
                 slave_address=None,
                 ignore_ack=False):
        self._cmd_id = cmd_id
        self._command_width = 2
        if descriptor.startswith('>B'):
            self._command_width = 1
        self._descriptor = descriptor
        self._slave_address = slave_address
        self._device_busy_delay = device_busy_delay
        self._ignore_acknowledge = ignore_ack
        string_fields = re.findall(self.string_match, descriptor)
        self._string_len = 0
        if not any(string_fields):
            return
        if len(string_fields) > 1:
            raise NotImplementedError("A transfer cannot contain more than one string field!")
        self._string_len = int(string_fields[0][0])

    def pack(self, argument_list=[]):
        data_to_pack = [self._cmd_id]
        for arg in argument_list:
            if isinstance(arg, str):
                data_to_pack.append(self._string_to_bytes(arg))
            elif isinstance(arg, (list, tuple)):
                data_to_pack.extend(arg)
            else:
                data_to_pack.append(arg)
        return bytearray(struct.pack(self._descriptor, *data_to_pack))

    @property
    def command_width(self):
        return self._command_width

    @property
    def slave_address(self):
        return self._slave_address

    @property
    def device_busy_delay(self):
        return self._device_busy_delay

    @property
    def ignore_acknowledge(self):
        return self._ignore_acknowledge

    def _string_to_bytes(self, string_param):
        assert self._string_len > 0, "Invalid string descriptor"
        if len(string_param) > self._string_len:
            string_param = string_param[:self._string_len]
            log.warning("Truncating string!")
        return string_param.encode()


class RxData:
    """Descriptor for data to be received"""

    field_match = re.compile(r'(?P<length>\d*)(?P<descriptor>(h|H|b|B|i|I|\?|s|q|Q|f|d))')
    element_size_map = {'B': 8, 'I': 32, 'H': 16}

    def __init__(self, descriptor=None, convert_to_int=False):
        self._descriptor = descriptor
        self._rx_length = 0
        self._conversion_function = None
        if self._descriptor is None:
            return
        self._rx_length = struct.calcsize(self._descriptor)
        self._contains_array = RxData.field_match.search(descriptor) is not None
        self._convert_to_int = convert_to_int

    @property
    def rx_length(self):
        return self._rx_length

    def unpack(self, data):
        if self._contains_array:
            return self.unpack_dynamic_sized(data)
        return struct.unpack(self._descriptor, data)

    def unpack_dynamic_sized(self, data):
        """
        Unpacks data returned by a sensor.

        For SHDLC always this function is used. For i2c all responses that contain arrays are unpacked with this
        function.
        Reasoning:
            struct.pack returns a tuple of values. In the python code an array is treated as one value. Hence a
            descriptor in the form I8b would be unpacked as a tuple with 9 values but the driver would expect only
            two return values, an integer and an array containing the 8 bytes.
        """
        byte_order_specifier = self._descriptor[0]
        descriptor_pos, data_pos = 1, 0
        unpacked = []
        match = self.field_match.match(self._descriptor, descriptor_pos)
        while match:
            descriptor = match.group('descriptor')
            elem_size = struct.calcsize(descriptor)
            elem_bit_width = elem_size * 8
            length = match.group('length')
            descriptor_pos += len(length) + len(descriptor)
            if length:
                field_len = 0
                is_string = descriptor == 's'
                for i in range(data_pos, min(data_pos + elem_size * int(length), len(data))):
                    if data[i] == 0 and is_string:  # in SHDLC we have 0 delimeted arrays
                        break
                    field_len += 1
                descriptor = f'{byte_order_specifier}{field_len // elem_size}{descriptor}'
                val = struct.unpack_from(descriptor, data, data_pos)
                if self._convert_to_int:
                    val = array_to_integer(elem_bit_width, val)
                elif is_string:  # a string
                    val = val[0].decode()
                unpacked.append(val)
            else:
                descriptor = f"{byte_order_specifier} {descriptor}"
                unpacked.extend(struct.unpack_from(descriptor, data, data_pos))
            data_pos += elem_size
            match = self.field_match.match(self._descriptor, descriptor_pos)
        return tuple(unpacked)
