"""
    ~  guild  ~
    This module contains the class defitions for all things
    regarding the guild and also defines a USER class from the
    BaseGUILD class.
"""

from    contextlib import suppress
from    typing import Literal, Union, List
from    .exceptions import *
from    .tracing import *
from    .const import *
from    .message import *
from    . import client
from    . import sql
import  _discord as discord
import  time
import  json
import  pathlib
import  shutil

__all__ = (
    "GUILD",
    "USER"
)

#######################################################################
# Globals
#######################################################################
class GLOBALS:
    """ ~  class  ~
    - @Info: Contains the global variables for the module"""
    server_log_path = None


class BaseGUILD:
    """ ~ class ~
    - @Info: BaseGUILD object is used for creating inherited classes that work like a guild
    - @Param: 
        - snowflake    ~ The snowflake of the guild
        - generate_log ~ Whether or not to generate a log file for the guild"""

    __slots__ = (       # Faster attribute access
        "initialized",
        "apiobject",
        "snowflake",
        "_generate_log",
        "_messages",
        "t_messages",
        "vc_messages"
    )
    __logname__ = "BaseGUILD" # Dummy to demonstrate correct definition for @sql.register_type decorator

    @property
    def log_file_name(self):
        """~ property (getter) ~
        - @Info: The method returns a string that transforms the xGUILD's discord name into
               a string that contains only allowed character. This is a method instead of
               property because the name can change overtime."""
        raise NotImplementedError

    def __init__(self,
                 snowflake: int,
                 generate_log: bool=False) -> None:
        self.initialized = False
        self.apiobject = None
        self.snowflake = snowflake
        self._generate_log = generate_log
        self.t_messages: List[Union[TextMESSAGE, DirectMESSAGE]] = []
        self.vc_messages: List[VoiceMESSAGE] = []

    def __eq__(self, other) -> bool:
        """
        ~  operator method  ~
        - @Return: ~ Returns True if objects have the same snowflake or False otherwise
        - @Info:   The function is used to compare two objects"""
        return self.snowflake == other.snowflake

    async def add_message(self, message):
        """~  coro  ~
        - @Info:   Adds a message to the message list
        - @Param:  message ~ message object to add"""
        raise NotImplementedError

    async def initialize(self):
        """~  coro  ~
        - @Return: bool:
                - Returns True if the initialization was successful
                - Returns False if failed, indicating the object should be removed from the server_list
        - @Info: The function initializes all the <IMPLEMENTATION> objects (and other objects inside the  <IMPLEMENTATION> object reccurssively).
                 It tries to get the  discord.<IMPLEMENTATION> object from the self.<implementation>_id and then tries to initialize the MESSAGE objects."""
        raise NotImplementedError

    async def advertise(self,
                        mode: Literal["text", "voice"]):
        """~ async method
        - @Info:
            - This is the main coroutine that is responsible for sending all the messages to this specificc guild,
              it is called from the core module's advertiser task
        """
        raise NotImplementedError

    async def generate_log(self,
                           message_context: dict) -> None:
        """~ async method
        - @Param:
            - data_context  ~ string representation of sent data, which is the return data of xxxMESSAGE.send()
        - @Info:   Generates a log of a xxxxMESSAGE send attempt either in file or in a SQL database"""

        guild_context = {
            "name" : str(self.apiobject),
            "id" : self.snowflake,
            "type" : type(self).__logname__,
        }

        try:
            # Try to obtain the sql manager. If it returns None (sql logging disabled), save into file
            manager = sql.get_sql_manager()
            if (
                manager is None or  # Short circuit evaluation
                not await manager.save_log(guild_context, message_context)
            ):
                timestruct = time.localtime()
                timestamp = "{:02d}.{:02d}.{:04d} {:02d}:{:02d}:{:02d}".format(timestruct.tm_mday,
                                                                            timestruct.tm_mon,
                                                                            timestruct.tm_year,
                                                                            timestruct.tm_hour,
                                                                            timestruct.tm_min,
                                                                            timestruct.tm_sec)
                logging_output = pathlib.Path(GLOBALS.server_log_path)\
                            .joinpath("{:02d}".format(timestruct.tm_year))\
                            .joinpath("{:02d}".format(timestruct.tm_mon))\
                            .joinpath("{:02d}".format(timestruct.tm_mday))
                with suppress(FileExistsError):
                    logging_output.mkdir(parents=True,exist_ok=True)

                logging_output = str(logging_output.joinpath(self.log_file_name))

                # Create file if it doesn't exist
                fresh_file = False
                with suppress(FileExistsError), open(logging_output, "x", encoding="utf-8"):
                    fresh_file = True

                # Write to file
                with open(logging_output,'r+', encoding='utf-8') as appender:
                    appender_data = None
                    appender.seek(0) # Append moves cursor to the end of the file
                    try:
                        appender_data = json.load(appender)
                    except json.JSONDecodeError:
                        # No valid json in the file, create new data
                        # and create a .old file to store this invalid data
                        # Copy-paste to .old file to prevent data loss
                        if not fresh_file: ## Failed because the file was just created, no need to copy-paste
                            # File not newly created, and has invalid data
                            shutil.copyfile(logging_output, f"{logging_output}.old")
                        # Create new data
                        appender_data = {}
                        appender_data["name"] = guild_context["name"]
                        appender_data["id"]   = guild_context["id"]
                        appender_data["type"] = guild_context["type"]
                        appender_data["message_history"] = []
                    finally:
                        appender.seek(0) # Reset cursor to the beginning of the file after reading

                    appender_data["message_history"].insert(0,
                        {
                            **message_context,
                            "index":    appender_data["message_history"][0]["index"] + 1 if len(appender_data["message_history"]) else 0,
                            "timestamp": timestamp
                        })                
                    json.dump(appender_data, appender, indent=4)
                    appender.truncate() # Remove any old data

        except Exception as exception:
            # Any uncautch exception (prevent from complete framework stop)
            trace(f"[{type(self).__name__}]: Unable to save log. Exception: {exception}", TraceLEVELS.WARNING)


@sql.register_type("GuildTYPE")
class GUILD(BaseGUILD):
    """ ~ class ~
    - @Info: The GUILD object represents a server to which messages will be sent.
    - @Param:
        - guild_id ~ identificator which can be obtained by enabling developer mode in discord's settings and
                     afterwards right-clicking on the server/guild icon in the server list and clicking "Copy ID",
        - messages_to_send ~List of TextMESSAGE/VoiceMESSAGE objects
        - generate_log ~ bool variable, if True it will generate a file log for each message send attempt."""
    
    __logname__ = "GUILD" # For sql.register_type
    __slots__   = set()   # Removes __dict__ (prevents dynamic attributes)

    @property
    def log_file_name(self):
        """~ property (getter) ~
        - @Info: The method returns a string that transforms the GUILD's discord name into
               a string that contains only allowed character. This is a method instead of
               property because the name can change overtime."""
        return "".join(char if char not in C_FILE_NAME_FORBIDDEN_CHAR else "#" for char in self.apiobject.name) + ".json"

    def __init__(self,
                 guild_id: int,
                 messages_to_send: List[Union[TextMESSAGE, VoiceMESSAGE]],
                 generate_log: bool=False):
        self._messages = messages_to_send
        super().__init__(guild_id, generate_log)

    async def add_message(self, message: Union[TextMESSAGE, VoiceMESSAGE]):
        """~  coro  ~
        - @Info:   Adds a message to the message list
        - @Param:  message ~ message object to add
        - @Exceptions:
            - <class DAFInvalidParameterError code=DAF_INVALID_TYPE> ~ Raised when the message is not of type TextMESSAGE or VoiceMESSAGE
            - Other exceptions from message.initialize() method"""
        if not isinstance(message, (TextMESSAGE, VoiceMESSAGE)):
            raise DAFInvalidParameterError(f"Invalid xxxMESSAGE type: {type(message).__name__}, expected  {TextMESSAGE.__name__} or {VoiceMESSAGE.__name__}", DAF_INVALID_TYPE)

        await message.initialize()

        if isinstance(message, TextMESSAGE):
            self.t_messages.append(message)
        elif isinstance(message, VoiceMESSAGE):
            self.vc_messages.append(message)

    def remove_message(self, message: Union[TextMESSAGE, VoiceMESSAGE]):
        """~ method ~
        - @Info:   Removes a message from the message list
        - @Param:  message ~ message object to remove
        - @Exceptions:
            - <class DAFInvalidParameterError code=DAF_INVALID_TYPE> ~ Raised when the message is not of type TextMESSAGE or VoiceMESSAGE"""
        if isinstance(message, TextMESSAGE):
            self.t_messages.remove(message)
            return
        elif isinstance(message, VoiceMESSAGE):
            self.vc_messages.remove(message)
            return

        raise DAFInvalidParameterError(f"Invalid xxxMESSAGE type: {type(message).__name__}, expected  {TextMESSAGE.__name__} or {VoiceMESSAGE.__name__}", DAF_INVALID_TYPE)

    async def initialize(self):
        """ ~ async method
        - @Info:   This function initializes the API related objects and then tries to initialize the MESSAGE objects.
        - @Exceptions:
            - <class DAFNotFoundError code=DAF_GUILD_ID_NOT_FOUND> ~ Raised when the guild_id wasn't found
            - Other exceptions from .add_message(message_object) method"""
        if self.initialized: # Already initialized, just return
            return

        guild_id = self.snowflake
        cl = client.get_client()
        self.apiobject = cl.get_guild(guild_id)

        if self.apiobject is not None:
            for message in self._messages:
                await self.add_message(message)

            self.initialized = True
            return

        raise DAFNotFoundError(f"Unable to find guild with ID: {guild_id}", DAF_GUILD_ID_NOT_FOUND)

    async def advertise(self,
                        mode: Literal["text", "voice"]):
        """~ async method
        - @Info:
            - This is the main coroutine that is responsible for sending all the messages to this specificc guild,
              it is called from the core module's advertiser task"""
        msg_list = self.t_messages if mode == "text" else self.vc_messages
        marked_del = []

        for message in msg_list: # Copy the avoid issues with the list being modified while iterating
            if message.is_ready():
                message.reset_timer()
                message_ret = await message.send()
                # Check if the message still has any channels (as they can be auto removed on 404 status)
                if len(message.channels) == 0:
                    marked_del.append(message) # All channels were removed (either not found or forbidden) -> remove message from send list
                if self._generate_log and message_ret is not None:
                    await self.generate_log(message_ret)

        # Cleanup messages marked for removal
        for message in marked_del:
            if message in msg_list:
                msg_list.remove(message)
            trace(f"[GUILD]: Removing a {type(message).__name__} because it's channels were removed, in guild {self.apiobject.name}(ID: {self.snowflake})", TraceLEVELS.WARNING)


@sql.register_type("GuildTYPE")
class USER(BaseGUILD):
    """~ class ~
    - @Info:
        - The USER objects represents a Discord user/member.
    - @Params:
        - user_id ~ id of the user you want to DM,
        - messages ~ list of DirectMESSAGE objects which
                            represent messages that will be sent to the DM
        - generate_log ~ dictates if log should be generated for each sent message"""

    __logname__ = "USER" # For sql.register_type
    __slots__   = set()  # Removes __dict__ (prevents dynamic attributes)

    @property
    def log_file_name(self):
        """~ property (getter) ~
        - @Info: The method returns a string that transforms the USER's discord name into
               a string that contains only allowed character. This is a method instead of
               property because the name can change overtime."""
        return "".join(char if char not in C_FILE_NAME_FORBIDDEN_CHAR else "#" for char in f"{self.apiobject.display_name}#{self.apiobject.discriminator}") + ".json"

    def __init__(self,
                 user_id: int,
                 messages_to_send: List[DirectMESSAGE],
                 generate_log: bool = False) -> None:
        super().__init__(user_id, generate_log)
        self._messages = messages_to_send

    async def add_message(self, message):
        """~  coro  ~
        - @Info:   Adds a message to the message list
        - @Param:  message ~ message object to add
        - @Exceptions:
            - <class DAFInvalidParameterError code=DAF_INVALID_TYPE> ~ Raised when the message is not of type DirectMESSAGE
            - Other exceptions from message.initialize() method
        """
        if not isinstance(message, DirectMESSAGE):
            raise DAFInvalidParameterError(f"Invalid xxxMESSAGE type: {type(message).__name__}, expected  {DirectMESSAGE.__name__}", DAF_INVALID_TYPE)

        await message.initialize(user=self.apiobject)
        self.t_messages.append(message)

    async def initialize(self):
        """ ~ async method
        - @Info: This function initializes the API related objects and then tries to initialize the MESSAGE objects.
        - @Exceptions:
            - <class DAFNotFoundError code=DAF_USER_CREATE_DM> ~ Raised when the user_id wasn't found
            - Other exceptions from .add_message(message_object) method
        """
        if self.initialized: # Already initialized, just return
            return

        user_id = self.snowflake
        cl = client.get_client()
        self.apiobject = cl.get_user(user_id) # Get object from cache
        if self.apiobject is None: 
            # User not found in cache, try to fetch from API
            with suppress(discord.HTTPException):
                self.apiobject = await cl.fetch_user(user_id)

        # Api object was found in cache or fetched from API -> initialize messages
        if self.apiobject is not None:
            for message in self._messages:
                await self.add_message(message)
            
            self.initialized = True
            return

        # Api object wasn't found, even after direct API call to discord.
        raise DAFNotFoundError(f"[USER]: Unable to create DM with user id: {user_id}", DAF_USER_CREATE_DM)

    async def advertise(self,
                        mode: Literal["text", "voice"]) -> None:
        """ ~ async method
        - @Info:
            - This is the main coroutine that is responsible for sending all the messages to this specificc guild,
              it is called from the core module's advertiser task"""
        if mode == "text":  # Does not have voice messages, only text based (DirectMESSAGE)
            for message in self.t_messages: # Copy the avoid issues with the list being modified while iterating
                if message.is_ready():
                    message.reset_timer()
                    message_ret = await message.send()
                    if self._generate_log and message_ret is not None:
                        await self.generate_log(message_ret)
                    
                    if message.dm_channel is None:
                        self.t_messages.clear()            # Remove all messages since that they all share the same user and will fail
                        trace(f"Removing all messages for user {self.apiobject.display_name}#{self.apiobject.discriminator} (ID: {self.snowflake}) because we do not have permissions to send to that user.", TraceLEVELS.WARNING)
                        break