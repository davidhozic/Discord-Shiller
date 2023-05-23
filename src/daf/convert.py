"""
The conversion module is responsible for converting Python objects into different forms.
It is also responsible for doing the reverse, which is converting those other forms back into Python objects.
"""

from typing import Union, Any

import decimal
import importlib
import copy
import base64
import json
import asyncio
import array
import datetime

import _discord as discord

from . import client
from . import guild
from . import message
from . import misc
from . import logging


__all__ = (
    "convert_object_to_semi_dict",
    "convert_from_semi_dict"
)


LAMBDA_TYPE = type(lambda x: x)
CONVERSION_ATTRS = {
    client.ACCOUNT: {
        "attrs": misc.get_all_slots(client.ACCOUNT),
        "attrs_restore": {
            "tasks": [],
            "_update_sem": asyncio.Semaphore(1),
            "_running": False,
            "_client": None,
        },
    },
    guild.AutoGUILD: {
        "attrs": misc.get_all_slots(guild.AutoGUILD),
        "attrs_restore": {
            "_safe_sem": asyncio.Semaphore(1),
            "parent": None,
            "guild_query_iter": None,
            "cache": {}
        },
    },
    message.AutoCHANNEL: {
        "attrs": misc.get_all_slots(message.AutoCHANNEL),
        "attrs_restore": {
            "parent": None,
            "cache": set()
        },
    },
    logging.LoggerSQL: {
        "attrs": ["_daf_id"]
    },
    logging.LoggerJSON: {
        "attrs": []
    },
    logging.LoggerCSV: {
        "attrs": []
    },
    discord.Intents: {
        "custom_encoder": lambda intents: intents.value,  # Ignores other keys and calls the lambda to convert
        "custom_decoder": lambda value: discord.Intents._from_value(value),
    },
    datetime.datetime: {
        "custom_encoder": lambda object: object.isoformat(),
        "custom_decoder": lambda string: datetime.datetime.fromisoformat(string)
    },
    datetime.timedelta: {
        "custom_encoder": lambda object: object.total_seconds(),
        "custom_decoder": lambda seconds: datetime.timedelta(seconds=seconds)
    }
}
"""
This is a custom conversion dictionary.
It's values are datatypes of objects which cannot be normally converted to JSON, so custom rules are required.

Each value of the dictionary is another dictionary, which defined the rules about the specific datatype conversion.
These can contain the following items:

- "attrs": Iterable of attribute names that will be included in the output JSON-compatible dictionary.
- "attrs_restored": Dictionary of attributes (keys) that are skipped when converting to dict.
   When restoring from dictionary, the object will have these attributes set with the co-responding values.
- "attrs_convert": Dictionary of attributes(keys) that which's values can either be a fixed value of a function.
  The values of this override the object's attribute values. If a function is given, the function is (as parameter) 
  passed the object that is being converted and whatever it returns is used in
  the output dictionary as the attribute value.
- "attrs_skip": Iterable of attributes names that will be completely ignored when converting. They also won't be set
  when restoring from the output dictionary.

2 special items can be used, which override the default conversion logic.
If they are passed, the previously talked about items will be ignored.
These are:

- "custom_encoder": A function that accepts the object being converted as a parameter. It must return a JSON
  serializable object.
- "custom_decoder": A function that accepts the JSON compatible object. It must return the original Python object.
"""


# Guilds
CONVERSION_ATTRS[guild.GUILD] = {
    "attrs": misc.get_all_slots(guild.GUILD),
    "attrs_restore": {
        "update_semaphore": asyncio.Semaphore(1),
        "parent": None
    },
    "attrs_convert": {
        "_apiobject": lambda guild: guild.snowflake
    },
}

CONVERSION_ATTRS[guild.USER] = CONVERSION_ATTRS[guild.GUILD].copy()
CONVERSION_ATTRS[guild.USER]["attrs"] = misc.get_all_slots(guild.USER)


# Messages
CHANNEL_LAMBDA = (
    lambda message_:
        [(x if isinstance(x, int) else x.id) for x in message_.channels]
        if not isinstance(message_.channels, message.AutoCHANNEL)
        else message_.channels
)

CONVERSION_ATTRS[message.TextMESSAGE] = {
    "attrs": misc.get_all_slots(message.TextMESSAGE),
    "attrs_restore": {
        "update_semaphore": asyncio.Semaphore(1),
        "parent": None,
        "sent_messages": {}
    },
    "attrs_convert": {
        "channels": CHANNEL_LAMBDA
    },
}

CONVERSION_ATTRS[message.VoiceMESSAGE] = {
    "attrs": misc.get_all_slots(message.VoiceMESSAGE),
    "attrs_restore": {
        "update_semaphore": asyncio.Semaphore(1),
        "parent": None,
    },
    "attrs_convert": {
        "channels": CHANNEL_LAMBDA
    },
}


CONVERSION_ATTRS[message.DirectMESSAGE] = {
    "attrs": misc.get_all_slots(message.DirectMESSAGE),
    "attrs_restore": {
        "update_semaphore": asyncio.Semaphore(1),
        "parent": None,
        "previous_message": None,
        "dm_channel": None
    },
    "attrs_convert": {
        "channels": CHANNEL_LAMBDA
    },
}


def convert_object_to_semi_dict(object_: object) -> dict:
    """
    Converts an object into ObjectInfo.

    Parameters
    ---------------
    object_: object
        The object to convert.
    """
    def _convert_json_slots(object_):
        type_object = type(object_)
        attrs = CONVERSION_ATTRS.get(type_object)
        if attrs is None:
            # No custom rules defined, try to convert normally with either vars or __slots__
            try:
                attrs = {"attrs": object_.__slots__ if hasattr(object_, "__slots__") else vars(object_)}
            except TypeError:
                return object_  # Not structured object or does not have overrides defined, return the object itself

        # Check if custom conversion function is requested
        if (encoder_func := attrs.get("custom_encoder")) is not None:
            data_conv = encoder_func(object_)
        else:
            # No custom conversion function provided, use the normal rules
            data_conv = {}
            (
                attrs,
                attrs_restore,
                attrs_convert,
                skip
            ) = (
                attrs["attrs"],
                attrs.get("attrs_restore", {}),
                attrs.get("attrs_convert", {}),
                attrs.get("attrs_skip", [])
            )
            for k in attrs:
                # Manually set during restored or is a class attribute
                if k in attrs_restore or k in skip:
                    continue

                if k in attrs_convert:
                    value = attrs_convert[k]
                    if isinstance(value, LAMBDA_TYPE):
                        value = value(object_)
                else:
                    value = getattr(object_, k)

                data_conv[k] = convert_object_to_semi_dict(value)

        return {"object_type": f"{type_object.__module__}.{type_object.__name__}", "data": data_conv}

    def _convert_json_dict(object_: dict):
        data_conv = {}
        for k, v in object_.items():
            data_conv[k] = convert_object_to_semi_dict(v)

        return data_conv

    object_type = type(object_)
    if object_type in {int, float, str, bool, decimal.Decimal, type(None)}:
        if object_type is decimal.Decimal:
            object_ = float(object_)

        return object_

    if isinstance(object_, (set, list, tuple)):
        object_ = [convert_object_to_semi_dict(value) for value in object_]
        return object_

    if isinstance(object_, dict):
        return _convert_json_dict(object_)

    return _convert_json_slots(object_)


def convert_from_semi_dict(d: Union[dict, list, Any]):
    """
    Function that converts the ``d`` parameter which is a semi-dict back to the object
    representation.

    Parameters
    ---------------
    d: Union[dict, list, Any]
        The semi-dict / list to convert.
    """
    if isinstance(d, list):
        _return = []
        for value in d:
            _return.append(convert_from_semi_dict(value) if isinstance(value, dict) else value)

        return _return

    elif isinstance(d, dict):
        if "object_type" not in d:  # It's a normal dictionary
            data = {}
            for k, v in d.items():
                data[k] = convert_from_semi_dict(v)

            return data

        # Find the class
        path = d["object_type"].split(".")
        module_path, class_name = '.'.join(path[:-1]), path[-1]
        module = importlib.import_module(module_path)
        class_ = getattr(module, class_name)
        conversion_attrs = CONVERSION_ATTRS.get(class_)

        if conversion_attrs is not None and (decoder_func := conversion_attrs.get("custom_decoder")) is not None:
            # Custom decoder function is used
            _return = decoder_func(d["data"])
        else:
            # Create an instance
            if issubclass(class_, array.array):
                _return = array.array.__new__(class_, 'Q')
            else:
                _return = object.__new__(class_)
                # Use object.__new__ instead of class.__new__
                # to prevent any objects who have IDs tracked from updating the weakref dictionary (in misc module)

            # Set saved attributes
            for k, v in d["data"].items():
                if isinstance(v, (dict, list)):
                    v = convert_from_semi_dict(v)

                setattr(_return, k, v)

            # Set overriden attributes
            attrs = CONVERSION_ATTRS.get(class_)
            if attrs is not None:
                attrs_restore = attrs.get("attrs_restore", {})
                for k, v in attrs_restore.items():
                    if isinstance(v, LAMBDA_TYPE):
                        v = v(_return)

                    if not isinstance(v, discord.Client):  # For some reason it fails to logging when copied.
                        v = copy.copy(v)  # Prevent external modifications since it's passed by reference

                    setattr(_return, k, v)

        return _return
    else:
        return d


def convert_object_to_b64(d: object) -> bytes:
    """
    Converts an object first into semi-dict representation and then into bytes encoded b64 string.
    """
    return base64.b64encode(json.dumps(convert_object_to_semi_dict(d)).encode()).decode()


def convert_from_b64(data: str) -> object:
    """
    Decodes a b64 string and returns the original object.
    """
    return convert_from_semi_dict(json.loads(base64.b64decode(data).decode()))
