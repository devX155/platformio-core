# Copyright (c) 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import re

from platformio.compat import get_class_attributes, string_types
from platformio.exception import PlatformioException

# pylint: disable=too-many-instance-attributes
# pylint: disable=redefined-builtin, too-many-arguments


class DataModelException(PlatformioException):
    pass


class DataFieldException(DataModelException):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super(DataFieldException, self).__init__()

    def __str__(self):
        return "%s for `%s.%s` field" % (
            self.message,
            self.field.parent.__class__.__name__,
            self.field.name,
        )


class ListOfType(object):
    def __init__(self, type):
        self.type = type


class DataField(object):
    def __init__(
        self,
        default=None,
        type=str,
        required=False,
        min_length=None,
        max_length=None,
        regex=None,
        validate_factory=None,
        title=None,
    ):
        self.default = default
        self.type = type
        self.required = required
        self.min_length = min_length
        self.max_length = max_length
        self.regex = regex
        self.validate_factory = validate_factory
        self.title = title

        self.parent = None
        self.name = None
        self.value = None

    def __repr__(self):
        return '<DataField %s="%s">' % (
            self.title,
            self.default if self.value is None else self.value,
        )

    def validate(self, parent, name, value):
        self.parent = parent
        self.name = name
        self.title = self.title or name.title()

        try:
            if self.required and value is None:
                raise ValueError("Missed value")
            if self.validate_factory is not None:
                return self.validate_factory(self, value) or self.default
            if value is None:
                return self.default
            if inspect.isclass(self.type) and issubclass(self.type, DataModel):
                return self.type(**value).as_dict()
            if isinstance(self.type, ListOfType):
                return self._validate_list_of_type(self.type.type, value)
            if issubclass(self.type, (str, bool)):
                return getattr(self, "_validate_%s_value" % self.type.__name__)(value)
        except ValueError as e:
            raise DataFieldException(self, str(e))
        return value

    def _validate_list_of_type(self, list_of_type, value):
        if not isinstance(value, list):
            raise ValueError("Value should be a list")
        if isinstance(list_of_type, DataField):
            return [list_of_type.validate(self.parent, self.name, v) for v in value]
        assert issubclass(list_of_type, DataModel)
        return [list_of_type(**v).as_dict() for v in value]

    def _validate_str_value(self, value):
        if not isinstance(value, string_types):
            value = str(value)
        if self.min_length and len(value) < self.min_length:
            raise ValueError(
                "Minimum allowed length is %d characters" % self.min_length
            )
        if self.max_length and len(value) > self.max_length:
            raise ValueError(
                "Maximum allowed length is %d characters" % self.max_length
            )
        if self.regex and not re.match(self.regex, value):
            raise ValueError(
                "Value `%s` does not match RegExp `%s` pattern" % (value, self.regex)
            )
        return value

    @staticmethod
    def _validate_bool_value(value):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "yes", "1")


class DataModel(object):

    _field_names = None
    _exceptions = None

    def __init__(self, **kwargs):
        self._field_names = []
        self._exceptions = []
        for name, field in get_class_attributes(self).items():
            if not isinstance(field, DataField):
                continue
            self._field_names.append(name)
            value = None
            try:
                value = field.validate(self, name, kwargs.get(name))
            except DataFieldException as e:
                self._exceptions.append(e)
                if isinstance(self, StrictDataModel):
                    raise e
            finally:
                setattr(self, name, value)

    def __eq__(self, other):
        assert isinstance(other, DataModel)
        if self.get_field_names() != other.get_field_names():
            return False
        if self.get_exceptions() != other.get_exceptions():
            return False
        for name in self._field_names:
            if getattr(self, name) != getattr(other, name):
                return False
        return True

    def __repr__(self):
        fields = []
        for name in self._field_names:
            fields.append('%s="%s"' % (name, getattr(self, name)))
        return "<%s %s>" % (self.__class__.__name__, " ".join(fields))

    def get_field_names(self):
        return self._field_names

    def get_exceptions(self):
        return self._exceptions

    def as_dict(self):
        return {name: getattr(self, name) for name in self._field_names}


class StrictDataModel(DataModel):
    pass
