"""
Tools for creating binary format parsers/writers from simple definitions
See ndi_tool.py for examples

Author: Brendan Burkhart
Created on: 2022-7-22

(C) Copyright 2022 Johns Hopkins University (JHU), All Rights Reserved.

--- begin cisst license - do not edit ---

This software is provided "as is" under an open source license, with
no warranty.  The complete license can be found in license.txt and
http://www.cisst.org/cisst/license.txt.

--- end cisst license ---
"""

import inspect
import math
import struct
from typing import Any, List, Tuple, Type, Union

import numpy as np
import numpy.typing as npt


class FieldType:
    """FieldType specifies the type of struct fields, and does (de)serialization"""

    def size(self):
        raise NotImplementedError()

    def default(self):
        raise NotImplementedError()

    def decode(self, data: bytearray):
        raise NotImplementedError()

    def encode(self, value) -> bytearray:
        raise NotImplementedError()


class ByteStruct(FieldType):
    """ByteStruct is a FieldType specified as a format string for the `struct` library"""

    def __init__(self, format: str):
        self.format = struct.Struct(format)

    def size(self):
        return self.format.size

    def default(self):
        return int(0)

    def decode(self, data: bytearray):
        return self.format.unpack(data)[0]

    def encode(self, value):
        return self.format.pack(value)


class Field:
    """
    Field is a single field in a Struct, with a specified field type.

    Field instances *should not* be re-used in different Structs or multiple times in the
    same Struct as this can break Field ordering
    """

    # static counter to order Fields by creation order
    id = 0

    def make_field_type(format: Union[FieldType, Type[FieldType], str]) -> FieldType:
        if isinstance(format, FieldType):
            return format
        elif inspect.isclass(format) and issubclass(format, FieldType):
            return format()
        elif isinstance(format, str):
            return ByteStruct(format)
        else:
            raise TypeError(
                "Field parser type must be a FieldType instance, "
                "a FieldType subclass, or a struct format string"
            )

    def __init__(
        self, field_type: Union[FieldType, Type[FieldType], str], default=None
    ):

        self.type = Field.make_field_type(field_type)
        self._size = self.type.size()
        self._default = default

        self.id = Field.id
        Field.id += 1

    def size(self):
        return self._size

    def default(self):
        return self._default if self._default is not None else self.type.default()

    def decode(self, data: bytearray) -> Tuple[Any, bytearray]:
        if len(data) < self.size():
            raise ValueError("Not enough bytes to complete parsing!")

        remaining_data = data[self.size() :]

        value = self.type.decode(data[0 : self.size()])
        return value, remaining_data

    def encode(self, value: Any, data: bytearray) -> bytearray:
        encoding = self.type.encode(value)
        assert len(encoding) == self.size()
        data.extend(encoding)

        return data


class Vector3f(FieldType):
    """XYZ vector of single-precision 32-bit floats"""

    format = struct.Struct("<3f")

    def __init__(self):
        super().__init__()

    def size(self):
        return Vector3f.format.size

    def default(self):
        return np.array([0.0, 0.0, 0.0])

    def decode(self, data: bytearray) -> npt.ArrayLike:
        values = Vector3f.format.unpack(data)
        return np.array([*values])

    def encode(self, value: npt.ArrayLike) -> bytearray:
        return self.format.pack(*value)


UInt8 = ByteStruct("B")
UInt16 = ByteStruct("H")
Float32 = ByteStruct("f")


class Padding(FieldType):
    """
    Fixed-length zero-padding
    """

    def __init__(self, length: int):
        super().__init__()
        self.format = struct.Struct("<{}B".format(length))
        self.length = length

    def size(self):
        return self.format.size

    def default(self):
        return [0 for i in range(self.length)]

    def decode(self, data: bytearray):
        return 0

    def encode(self, value) -> bytearray:
        return self.format.pack(*self.default())


class Constant(FieldType):
    """
    Constant bytes
    """

    def __init__(self, value: List[int]):
        super().__init__()
        self.value = value
        self.length = len(value)

    def size(self):
        return self.length

    def default(self):
        return self.value

    def decode(self, data: bytearray):
        return [int(byte) for byte in data]

    def encode(self, value) -> bytearray:
        return bytearray(self.value)


class String(FieldType):
    """
    Fixed-size ASCII string

    Do not use with variable-width formats such as UTF-8
    """

    def __init__(self, length):
        super().__init__()
        self.length = length

    def size(self):
        return self.length

    def default(self):
        return ""

    def decode(self, data: bytearray) -> str:
        data = bytearray([byte for byte in data if byte != 0])
        return data.decode("ascii")

    def encode(self, value: str) -> bytearray:
        if len(value) > self.length:
            message = "String '{}' is too long, max length is {}".format(
                value, self.length
            )
            raise ValueError(message)

        padding = self.length - len(value)
        for i in range(padding):
            value += "\0"

        return bytearray(value.encode("ascii"))


class Array(FieldType):
    """Fixed-length array of specified element type"""

    def __init__(self, element_type, length: int):
        super().__init__()
        self.element_type = Field.make_field_type(element_type)
        self.length = length

    def size(self):
        return self.length * self.element_type.size()

    def default(self):
        default_value = self.element_type.default()
        try:
            shape = (0, len(default_value))
        except TypeError:
            shape = (0,)

        default_type = np.dtype(type(default_value))
        return np.empty(shape, dtype=default_type)

    def decode(self, data: bytearray) -> npt.ArrayLike:
        step = self.element_type.size()
        elements = []

        for i in range(self.length):
            element_data = data[i * step : (i + 1) * step]
            elements.append(self.element_type.decode(element_data))

        return np.array(elements)

    def encode(self, value: npt.ArrayLike) -> bytearray:
        if len(value) > self.length:
            raise ValueError("Array too large!")

        padding = self.length - len(value)
        for i in range(padding):
            v = np.array([self.element_type.default()])
            value = np.append(value, v, axis=0)

        data = bytearray([])

        for v in value:
            data.extend(self.element_type.encode(v))

        return data


class Enum(FieldType):
    """
    Enum takes a list of options as tuples of integer value and string name

    Values must be unique and non-negative, however they don't need to be continuous
    or in order
    """

    def __init__(self, options: List[Tuple[int, str]], default: int):
        super().__init__()
        self.options = options

        # Validate options
        distinct_values = set([value for value, name in options])
        if len(distinct_values) != len(options):
            raise ValueError("Invalid Enum options, values must be distinct!")

        for value, name in options:
            if value < 0:
                raise ValueError(
                    "Invalid Enum option ({}, {}), values can't be negative!".format(
                        value, name
                    )
                )

        default_option = [(v, name) for v, name in self.options if v == default]
        if len(default_option) != 1:
            raise ValueError("default Enum value must be one of the provided options")

        self.default_option = default_option[0]

    def default(self):
        return self.default_option

    def size(self):
        highest_option_value = max([value for value, name in self.options])
        bytes_need = math.ceil(math.log(highest_option_value, 2**8))
        return bytes_need

    def decode(self, data: bytearray) -> Tuple[int, str]:
        value = int.from_bytes(data, byteorder="little")
        option = [(v, name) for v, name in self.options if v == value]

        if len(option) != 1:
            raise ValueError("Invalid enum value: {}".format(value))

        return option[0]

    def encode(self, value: Tuple[int, str]) -> bytearray:
        return value[0].to_bytes(length=self.size(), byteorder="little")


class MetaStruct(type):
    """
    Metaclass for struct definitions

    Struct definitions should derive from Struct, not this class. Classes with this
    metaclass can define attributes of type Field, which can be used to
    serialize/deserialize them from byte arrays.
    """

    def __new__(metaclass, name, bases, attrs):
        bases = (*bases, FieldType)
        new_attrs = {}

        # Store all Fields so they can be accessed later
        fields = {}

        for key, value in attrs.items():
            if isinstance(value, Field):
                fields[key] = value
            else:
                new_attrs[key] = value

        new_attrs["_fields"] = fields

        return super().__new__(metaclass, name, bases, new_attrs)


class Struct(metaclass=MetaStruct):
    """
    Struct definitions should derive from this base class. Class (not instance)
    attributes of type Field will be used to produce methods to encode/decode
    the Struct to/from bytearray.

    Derived classes must be default-constructible.
    """

    # Initialize instance storage, fill with None
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls, *args, **kwargs)
        for key, field in cls._fields.items():
            setattr(instance, key, field.default())

        return instance

    # Provides default-constructed value
    # Override to provide custom default value
    @classmethod
    def default(cls):
        return cls()

    @classmethod
    def size(cls):
        return sum([field.size() for key, field in cls._fields.items()])

    @classmethod
    def locate(cls, key: str):
        # Parse fields in order of definition
        all_keys = sorted(cls._fields, key=lambda k: cls._fields[k].id)
        preceeding_keys = all_keys[0 : all_keys.index(key)]
        offset = sum([cls._fields[key].size() for key in preceeding_keys])
        return offset, cls._fields[key].size()

    @classmethod
    def decode(cls, data: bytearray):
        # Parse fields in order of definition
        keys = sorted(cls._fields, key=lambda k: cls._fields[k].id)
        self = cls.default()

        for key in keys:
            value, data = cls._fields[key].decode(data)
            setattr(self, key, value)

        # Post-processing
        self.post_decode()

        return self

    @classmethod
    def encode(cls, self) -> bytearray:
        # Parse fields in order of definition
        keys = sorted(self._fields, key=lambda k: self._fields[k].id)
        data = bytearray([])

        # Pre-precessing hook
        self.pre_encode()

        for key in keys:
            value = getattr(self, key)
            data = self._fields[key].encode(value, data)

        # Post-processing hook
        data = self.post_encode(data)
        return data

    def update(self, key: str, value) -> bytearray:
        setattr(self, key, value)
        return self._fields[key].encode(value, bytearray([]))

    # Hook to perform pre-encode processing
    def pre_encode(self):
        pass

    # Hook to perform post-encode processing
    def post_encode(self, data: bytearray) -> bytearray:
        return data

    # Hook to perform post-decode processing
    def post_decode(self):
        pass


def passthrough_property(keys: List[str]):
    def get(self):
        obj = self
        for key in keys:
            obj = getattr(obj, key)

        return obj

    def set(self, value):
        obj = self
        for key in keys[0:-1]:
            obj = getattr(obj, key)

        setattr(obj, keys[-1], value)

    return property(get, set)
