"""
This module is responsible for the logging in daf.
It contains all the logging classes.
"""
from __future__ import annotations
from contextlib import suppress
from datetime import datetime
from typing import Optional

from .tracing import trace, TraceLEVELS
from .. import misc

import json
import csv
import pathlib
import shutil


__all__ = (
    "LoggerBASE",
    "LoggerJSON",
    "LoggerCSV",
    "get_logger",
    "set_logger"
)

# Constants
# ---------------------#
C_FILE_NAME_FORBIDDEN_CHAR = ('<','>','"','/','\\','|','?','*',":")


class GLOBAL:
    "Singleton for global variables"
    logger: LoggerBASE = None  


@misc.doc_category("Logging", path="logging")
class LoggerBASE:
    """
    .. versionadded:: v2.2

    The base class for making loggers.
    This can be used to implement your custom logger as well.
    This does absolutely nothing, and is here just for demonstration.

    Parameters
    ----------------
    fallback: Optional[LoggerBASE]
        The manager to use, in case saving using this manager fails.
    """
    def __init__(self, fallback: Optional[LoggerBASE] = None) -> None:
        self.fallback = fallback
        raise NotImplementedError

    async def initialize(self) -> None:
        "Initializes self and the fallback"
        if self.fallback is not None:
            try:
                await self.fallback.initialize()
            except Exception as exc:
                trace(f"[Logging:] Could not initialize {type(self).__name__}'s fallback: {type(self.fallback).__name__}", TraceLEVELS.WARNING)
                self.fallback = None


    async def _save_log(self, guild_context: dict, message_context: dict):
        """
        Used for saving the log for a sent message.

        Parameters
        -------------
        guild_context: dict
            Context generated by the xGUILD object, see guild.xGUILD._generate_log() for more info.
        message_context: dict
            Context generated by the xMESSAGE object, see guild.xMESSAGE.generate_log_context() for more info.
        """
        raise NotImplementedError
    
    async def update(self, **kwargs):
        """
        Used to update the original parameters.

        Parameters
        -------------
        kwargs: Any
            Keyword arguments of any original parameters.

        Raises
        ----------
        TypeError
            Invalid keyword argument was passed.
        Other
            Other exceptions raised from ``.initialize`` method (if it exists).
        """
        await misc._update(self, **kwargs)


@misc.doc_category("Logging", path="logging")
class LoggerCSV(LoggerBASE):
    """
    .. versionadded:: v2.2

    Logging class for generating .csv file logs.
    The logs are saved into CSV files and fragmented
    by guild/user and day (each day, new file for each guild).

    Each entry is in the following format:
    
    ``Timestamp, Guild Type, Guild Name, Guild Snowflake, Message Type,
    Sent Data, Message Mode (Optional), Channels (Optional), Success Info (Optional)``

    Parameters
    ----------------
    path: str
        Path to the folder where logs will be saved.
    delimiter: str
        The delimiter between columns to use.
    fallback: Optional[LoggerBASE]
        The manager to use, in case saving using this manager fails.

    Raises
    ----------
    OSError
        Something went wrong at OS level (insufficient permissions?)
        and fallback failed as well.
    """
    def __init__(self, path: str, delimiter: str, fallback: Optional[LoggerBASE] = None) -> None:
        self.path = path
        self.fallback = fallback
        self.delimiter = delimiter
    
    async def _save_log(self, guild_context: dict, message_context: dict) -> None:
        timestruct = datetime.now()
        timestamp = "{:02d}.{:02d}.{:04d} {:02d}:{:02d}:{:02d}".format(timestruct.day, timestruct.month, timestruct.year,
                                                                    timestruct.hour, timestruct.minute, timestruct.second)

        logging_output = (pathlib.Path(self.path)
                        .joinpath("{:02d}".format(timestruct.year))
                        .joinpath("{:02d}".format(timestruct.month))
                        .joinpath("{:02d}".format(timestruct.day)))

        logging_output.mkdir(parents=True,exist_ok=True)
        logging_output = logging_output.joinpath("".join(char if char not in C_FILE_NAME_FORBIDDEN_CHAR
                                                              else "#" for char in guild_context["name"]) + ".csv")          
        # Create file if it doesn't exist
        if not logging_output.exists():
            logging_output.touch()

        # Write to file
        with open(logging_output,'a', encoding='utf-8', newline='') as f_writer:
            try:
                csv_writer = csv.writer(f_writer, delimiter=self.delimiter, quoting=csv.QUOTE_NONNUMERIC, quotechar='"')
                # Timestamp, Guild Type, Guild Name, Guild Snowflake, Message Type, Sent Data, Message Mode, Message Channels, Success Info
                csv_writer.writerow([
                    timestamp, guild_context["type"], guild_context["name"], guild_context["id"],
                    message_context["type"], message_context["sent_data"], message_context.get("mode", ""),
                    message_context.get("channels", ""), message_context.get("success_info", "")
                ])
                
            except Exception as exc:
                raise OSError(*exc.args) from exc # Raise OSError for any type of exceptions


@misc.doc_category("Logging", path="logging")
class LoggerJSON(LoggerBASE):
    """
    .. versionadded:: v2.2

    Logging class for generating .json file logs.
    The logs are saved into JSON files and fragmented
    by guild/user and day (each day, new file for each guild).

    Parameters
    ----------------
    path: str
        Path to the folder where logs will be saved.
    fallback: Optional[LoggerBASE]
        The manager to use, in case saving using this manager fails.

    Raises
    ----------
    OSError
        Something went wrong at OS level (insufficient permissions?)
        and fallback failed as well.
    """
    def __init__(self, path: str, fallback: Optional[LoggerBASE] = None) -> None:
        self.path = path
        self.fallback = fallback
    
    async def _save_log(self, guild_context: dict, message_context: dict) -> None:
        timestruct = datetime.now()
        timestamp = "{:02d}.{:02d}.{:04d} {:02d}:{:02d}:{:02d}".format(timestruct.day, timestruct.month, timestruct.year,
                                                                    timestruct.hour, timestruct.minute, timestruct.second)

        logging_output = (pathlib.Path(self.path)
                        .joinpath("{:02d}".format(timestruct.year))
                        .joinpath("{:02d}".format(timestruct.month))
                        .joinpath("{:02d}".format(timestruct.day)))

        logging_output.mkdir(parents=True,exist_ok=True)
        logging_output = logging_output.joinpath("".join(char if char not in C_FILE_NAME_FORBIDDEN_CHAR
                                                              else "#" for char in guild_context["name"]) + ".json")          
        # Create file if it doesn't exist
        file_exists = True
        if not logging_output.exists():
            logging_output.touch()
            file_exists = False

        # Write to file
        with open(logging_output,'r+', encoding='utf-8') as f_writer:
            json_data = None
            if file_exists:
                try:
                    json_data: dict = json.load(f_writer)
                except json.JSONDecodeError:
                    # No valid json in the file, create a .old file to store this invalid data.
                    # Copy-paste to .old file to prevent data loss
                    shutil.copyfile(logging_output, f"{logging_output}.old")
                finally:
                    f_writer.seek(0) # Reset cursor to the beginning of the file after reading

            if json_data is None:
                # Some error or new file
                json_data = {}
                json_data["name"] = guild_context["name"]
                json_data["id"] = guild_context["id"]
                json_data["type"] = guild_context["type"]
                json_data["message_history"] = []

            json_data["message_history"].insert(0,
                {
                    **message_context,
                    "index": json_data["message_history"][0]["index"] + 1 if len(json_data["message_history"]) else 0,
                    "timestamp": timestamp
                })
            json.dump(json_data, f_writer, indent=4)
            f_writer.truncate() # Remove any old data


async def initialize(logger: LoggerBASE) -> None:
    """
    Initialization coroutine for the module.
    
    Parameters
    --------------
    The logger manager to use for saving logs.
    """
    while logger is not None:
        with suppress(Exception):
            await logger.initialize()
            break

        trace(f"Could not initialize manager {type(logger).__name__}, falling to {type(logger.fallback).__name__}", TraceLEVELS.WARNING)
        logger = logger.fallback # Could not initialize, try fallback
    else:
        trace("Logging will be disabled as the logging manager and it's fallbacks all failed initialization", TraceLEVELS.ERROR)

    GLOBAL.logger = logger


@misc.doc_category("Getters", path="logging")
def get_logger() -> LoggerBASE:
    """
    Returns
    ---------
    LoggerBASE
        The selected logging object which is of inherited type from LoggerBASE.
    """
    return GLOBAL.logger


@misc.doc_category("Setters", path="logging")
async def set_logger(logger: LoggerBASE):
    """
    Coroutine changes the used logger.

    Parameters
    -------------
    logger: LoggerBASE
        The logger to use.

    Raises
    -------------
    Any
        Exceptions raised in logger.initialize()
    """
    await logger.initialize()
    GLOBAL.logger = logger


async def save_log(guild_context: dict, message_context: dict):
    """
    Saves the log to the selected manager or saves
    to the fallback manager if logging fails to the selected.

    Parameters
    ------------
    guild_context: dict
        Information about the guild message was sent into
    message_context: dict
        Information about the message sent
    """
    mgr = GLOBAL.logger
    while mgr is not None:
        try:
            await mgr._save_log(guild_context, message_context)
            break
        except Exception as exc:
            trace(f"{type(mgr).__name__} failed, falling to {type(mgr.fallback).__name__}\nReason: {exc}", TraceLEVELS.WARNING)
            mgr = mgr.fallback # Could not initialize, try fallback
    else:
        trace("Could not save log to the manager or any of it's fallback", TraceLEVELS.ERROR)
