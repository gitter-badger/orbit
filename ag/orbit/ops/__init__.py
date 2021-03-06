# Copyright (C) 2018 Alpha Griffin
# @%@~LICENSE~@%@

from abc import ABC, abstractmethod, abstractclassmethod
from decimal import Decimal

from cashaddress.convert import Address, is_valid
from rfc3986 import uri_reference
from rfc3986.validators import Validator

import unicodedata


class Abstract(ABC):
    """Abstract base class for all ORBIT operations.

    This class defines a some methods that subclasses are required to implement.
    It also makes available a number of useful helper methods.
    """

    SEPARATOR = b'\xFF' # this byte should not exist anywhere in any UTF-8 or our accepted ASCII subset
    ENDIAN = 'big'
    ENCODING = 'utf-8'

    link_uri_validator_1 = Validator().require_presence_of('scheme', 'host')
    link_uri_validator_2 = Validator().require_presence_of('scheme', 'path')
    src_uri_validator_1 = Validator().require_presence_of('scheme', 'host', 'path').allow_schemes('http', 'https')
    src_uri_validator_2 = Validator().require_presence_of('scheme', 'path').allow_schemes('data')

    def __eq__(self, other):
        """Equality test.

        Operations are considered equal if they are of the same type
        and all their members are equal.
        """

        if isinstance(other, self.__class__) or isinstance(self, other.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __ne__(self, other):
        """Inequality test.

        Simply returns the opposite of ``__eq__()``
        """

        return not self.__eq__(other)

    @abstractmethod
    def __str__(self):
        raise NotImplementedError('__str__() must be implemented by subclass')

    @abstractmethod
    def admin(self):
        raise NotImplementedError('admin() must be implemented by subclass')

    @abstractmethod
    def validate(self):
        raise NotImplementedError('validate() must be implemented by subclass')

    @abstractmethod
    def prepare(self):
        raise NotImplementedError('prepare() must be implemented by subclass')

    @abstractclassmethod
    def parse(cls, data):
        raise NotImplementedError('parse() must be implemented by subclass')

    @classmethod
    def read_text(cls, data, encoding=None):
        done = False
        end = data.find(cls.SEPARATOR)

        if end < 0:
            done = True
            end = len(data)
        elif end == 0:
            return (None, 0, False)

        if encoding is None:
            encoding = cls.ENCODING

        return (data[:end].decode(encoding), end, done)

    @classmethod
    def is_safe_unicode(cls, text, forbidden_types):
        btext = text.encode(cls.ENCODING)
        for b in btext:
            if b == cls.SEPARATOR:
                return False

        return not cls.has_unicode_type(text, forbidden_types)

    @classmethod
    def has_unicode_type(cls, text, types):
        for c in text:
            category = unicodedata.category(c)
            for t in types:
                if category.startswith(t):
                    return True

        return False

    @classmethod
    def is_safe_ascii(cls, text):
        try:
            btext = text.encode('ascii')
            for b in btext:
                if b < 32 or b > 126 or b == cls.SEPARATOR:
                    return False
        except UnicodeEncodeError:
            return False

        return True

    @classmethod
    def is_link_uri(cls, text):
        if not cls.is_safe_ascii(text):
            return False

        uri = uri_reference(text)

        try:
            cls.link_uri_validator_1.validate(uri)
        except Exception:
            try:
                cls.link_uri_validator_2.validate(uri)
            except Exception:
                return False

        return True

    @classmethod
    def is_src_uri(cls, text):
        if not cls.is_safe_ascii(text):
            return False

        uri = uri_reference(text)

        try:
            cls.src_uri_validator_1.validate(uri)
        except Exception:
            try:
                cls.src_uri_validator_2.validate(uri)
            except Exception:
                return False

        return True

    @classmethod
    def to_string(cls, indent=None, **kwargs):
        text = "{}".format(cls.__name__)

        if len(kwargs) > 0:
            text += ':'

            for key, value in kwargs.items():
                text += '\n{}'.format(indent) if indent else ' '
                text += '{}={}'.format(key, value if isinstance(value, Decimal) else repr(value))

        return text

    @classmethod
    def validate_range(cls, name, value, minval, maxval, optional=False): # minval and maxval are inclusive
        if not optional and value is not None:
            if value < minval or value > maxval:
                raise ValueError('{} is out of range: supplied={}, min={}, max={}'.format(name, value, minval, maxval))

        return value

    @classmethod
    def validate_range_bytesize(cls, name, value, size, optional=False, allow_zero=True, signed=False):
        if value == 0 and not allow_zero:
            raise ValueError('{} may not be zero'.format(name))
        if not optional and value is not None:
            minval = 0 - 2**(8*size - 1)
            maxval = 2**(8*size - 1) - 1
            if value < minval or value > maxval:
                raise ValueError('{} is out of range: supplied={}, min={}, max={}{}'.format(name, value, minval, maxval,
                    ", zero is not allowed" if not allow_zero else ""))

        return value

    @classmethod
    def validate_address(cls, name, address):
        if not is_valid(address):
            raise ValueError('{} is not a valid bitcoincash address'.format(name))

        return address

    @classmethod
    def serialize_address(cls, address):
        address = Address.from_string(address)
        addr_ver = Address._address_type('cash', address.version)[1]

        data = addr_ver.to_bytes(1, 'big')
        data += len(address.payload).to_bytes(1, 'big')
        data += bytes(address.payload)

        return data

    @classmethod
    def deserialize_address(cls, data):
        if len(data) < 2:
            raise ValueError('Not enough data reading address version/length')

        addr_ver = int.from_bytes(data[0:1], 'big')
        addr_len = int.from_bytes(data[1:2], 'big')

        if len(data) < addr_len + 2:
            raise ValueError('Not enough data reading address')

        address = Address(addr_ver, list(data[2:addr_len+2])).cash_address()
        data = data[2+addr_len:]

        return (address, data)

