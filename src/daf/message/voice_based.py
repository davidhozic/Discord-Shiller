"""
    Contains definitions related to voice messaging."""


from contextlib import suppress
from typing import Any, Dict, List, Iterable, Optional, Union, Tuple
from datetime import timedelta, datetime
from typeguard import typechecked

from .base import *
from ..dtypes import *
from ..logging.tracing import *
from ..logging import sql
from ..misc import doc, instance_track, async_util

from .. import dtypes

import asyncio
import _discord as discord


__all__ = (
    "VoiceMESSAGE",
)


# Configuration
# ----------------------#
C_VC_CONNECT_TIMEOUT = 3  # Timeout of voice channels


@instance_track.track_id
@doc.doc_category("Messages", path="message")
@sql.register_type("MessageTYPE")
class VoiceMESSAGE(BaseChannelMessage):
    """
    This class is used for creating objects that represent messages which will be streamed to voice channels.

    .. warning::

        This additionaly requires FFMPEG to be installed on your system.

    .. deprecated:: 2.1

        - start_period, end_period - Using int values, use ``timedelta`` object instead.

    .. versionchanged:: 2.10

        'data' parameter no longer accepets :class:`daf.dtypes.AUDIO` and no longer allows YouTube streaming.
        Instead it accepts :class:`daf.dtypes.FILE`.

    .. versionchanged:: 2.7

        *start_in* now accepts datetime object

    Parameters
    ------------
    start_period: Union[int, timedelta, None]
        The value of this parameter can be:

        - None - Use this value for a fixed (not randomized) sending period
        - timedelta object - object describing time difference, if this is used,
          then the parameter represents the bottom limit of the **randomized** sending period.
    end_period: Union[int, timedelta]
        If ``start_period`` is not None,
        then this represents the upper limit of randomized time period in which messages will be sent.
        If ``start_period`` is None, then this represents the actual time period between each message send.

        .. code-block:: python
            :caption: **Randomized** sending period between **5** seconds and **10** seconds.

            # Time between each send is somewhere between 5 seconds and 10 seconds.
            daf.VoiceMESSAGE(
                start_period=timedelta(seconds=5), end_period=timedelta(seconds=10), data=daf.AUDIO("msg.mp3"),
                channels=[12345], start_in=timedelta(seconds=0), volume=50
            )

        .. code-block:: python
            :caption: **Fixed** sending period at **10** seconds

            # Time between each send is exactly 10 seconds.
            daf.VoiceMESSAGE(
                start_period=None, end_period=timedelta(seconds=10), data=daf.AUDIO("msg.mp3"),
                channels=[12345], start_in=timedelta(seconds=0), volume=50
            )
    data: FILE
        The data parameter is the actual data that will be sent using discord's API.
        The data types of this parameter can be:

            - FILE object.
            - Function that accepts any amount of parameters and returns an FILE object. To pass a function, YOU MUST USE THE :ref:`data_function` decorator on the function.

    channels: Union[Iterable[Union[int, discord.VoiceChannel]], daf.message.AutoCHANNEL]
        Channels that it will be advertised into (Can be snowflake ID or channel objects from PyCord).

        .. versionchanged:: v2.3
            Can also be :class:`~daf.message.AutoCHANNEL`

    volume: Optional[int]
        The volume (0-100%) at which to play the audio. Defaults to 50%. This was added in v2.0.0
    start_in: Optional[timedelta | datetime]
        When should the message be first sent.
        *timedelta* means the difference from current time, while *datetime* means actual first send time.
    remove_after: Optional[Union[int, timedelta, datetime]]
        Deletes the message after:

        * int - provided amounts of successful sends to seperate channels.
        * timedelta - the specified time difference
        * datetime - specific date & time

        .. versionchanged:: v2.10

            Parameter ``remove_after`` of int type will now work at a channel level and
            it nows means the SUCCESSFUL number of sends into each channel.
    """

    __slots__ = (
        "volume",
        "voice_client"
    )

    @typechecked
    def __init__(self,
                 start_period: Union[int, timedelta, None],
                 end_period: Union[int, timedelta],
                 data: Union[FILE, Iterable[FILE], _FunctionBaseCLASS],
                 channels: Union[Iterable[Union[int, discord.VoiceChannel]], AutoCHANNEL],
                 volume: Optional[int] = 50,
                 start_in: Optional[Union[timedelta, datetime]] = timedelta(seconds=0),
                 remove_after: Optional[Union[int, timedelta, datetime]] = None):

        if not dtypes.GLOBALS.voice_installed:
            raise ModuleNotFoundError(
                "You need to install extra requirements: pip install discord-advert-framework[voice]"
            )

        if isinstance(data, Iterable) and len(data) > 1:
            raise ValueError("Iterable was passed to 'data', which has length greater than 1. Only a single FILE object is allowed inside.")

        super().__init__(start_period, end_period, data, channels, start_in, remove_after)
        self.volume = max(0, min(100, volume))  # Clamp the volume to 0-100 %
        self.voice_client = None

    def generate_log_context(self,
                             audio: AUDIO,
                             succeeded_ch: List[discord.VoiceChannel],
                             failed_ch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates information about the message send attempt that is to be saved into a log.

        Parameters
        -----------
        audio: audio
            The audio that was streamed.
        succeeded_ch: List[Union[discord.VoiceChannel]]
            List of the successfully streamed channels
        failed_ch: List[Dict[discord.VoiceChannel, Exception]]
            List of dictionaries contained the failed channel and the Exception object

        Returns
        ----------
        Dict[str, Any]
            .. code-block:: python

                {
                    sent_data:
                    {
                        streamed_audio: str - The filename that was streamed/youtube url
                    },
                    channels:
                    {
                        successful:
                        {
                            id: int - Snowflake id,
                            name: str - Channel name
                        },
                        failed:
                        {
                            id: int - Snowflake id,
                            name: str - Channel name,
                            reason: str - Exception that caused the error
                        }
                    },
                    type: str - The type of the message, this is always VoiceMESSAGE.
              }
        """
        if not (len(succeeded_ch) + len(failed_ch)):
            return None

        succeeded_ch = [{"name": str(channel), "id": channel.id} for channel in succeeded_ch]
        failed_ch = [{"name": str(entry["channel"]), "id": entry["channel"].id,
                     "reason": str(entry["reason"])} for entry in failed_ch]
        return {
            "sent_data": {
                "streamed_audio": audio.to_dict()
            },
            "channels": {
                "successful": succeeded_ch,
                "failed": failed_ch
            },
            "type": type(self).__name__
        }

    async def _get_data(self) -> dict:
        """"
        Returns a dictionary of keyword arguments that is then expanded
        into other methods eg. `_send_channel, _generate_log`

        .. versionchanged:: v2.3
            Turned async.
        """
        data = None
        _data_to_send = {}
        data = await super()._get_data()
        if data is not None:
            if not isinstance(data, (list, tuple, set)):
                data = (data,)
            for element in data:
                if isinstance(element, FILE):
                    _data_to_send["audio"] = element
                    break

        return _data_to_send

    async def _handle_error(self, channel: discord.VoiceChannel, ex: Exception) -> Tuple[bool, ChannelErrorAction]:
        """
        This method handles the error that occurred during the execution of the function.

        Parameters
        -----------
        channel: Union[discord.TextChannel, discord.Thread]
            The channel where the exception occurred.
        ex: Exception
            The exception that occurred during a send attempt.

        Returns
        -----------
        Tuple[bool, ChannelErrorAction]
            Tuple containing (error_handled, ChannelErrorAction),
            where the ChannelErrorAction is a enum telling upper part of the message layer how to proceed.
        """
        handled = False
        action = None

        guild = channel.guild
        member = guild.get_member(self.parent.parent.client.user.id)

        # Acount token invalidated
        if isinstance(ex, discord.HTTPException) and ex.status == 401:  # Acount token invalidated
            action = ChannelErrorAction.REMOVE_ACCOUNT

        # Timeout handling
        elif member is not None and member.timed_out:
            self.next_send_time = member.communication_disabled_until.astimezone().replace(tzinfo=None) + timedelta(minutes=1)
            trace(
                f"User '{member.name}' has been timed-out in guild '{guild.name}'.\n"
                f"Retrying after {self.next_send_time} (1 minute after expiry)",
                TraceLEVELS.WARNING
            )

            if isinstance(ex, discord.HTTPException):
                # Prevent channel removal by the cleanup process
                ex.status = 429
                ex.code = 0

            action = ChannelErrorAction.SKIP_CHANNELS

        return handled, action

    def initialize(self, parent: Any):
        """
        This method initializes the implementation specific API objects
        and checks for the correct channel input context.

        Parameters
        --------------
        parent: daf.guild.GUILD
            The GUILD this message is in

        Raises
        ------------
        TypeError
            Channel contains invalid channels
        ValueError
            Channel does not belong to the guild this message is in.
        ValueError
            No valid channels were passed to object"
        """
        return super().initialize(parent, {discord.VoiceChannel}, lambda: parent.apiobject.voice_channels)

    async def _send_channel(self,
                            channel: discord.VoiceChannel,
                            audio: Optional[AUDIO]) -> dict:
        """
        Sends data to specific channel

        Returns a dictionary:
        - "success" - Returns True if successful, else False
        - "reason"  - Only present if "success" is False, contains the Exception returned by the send attempt

        Parameters
        -------------
        channel: discord.VoiceChannel
            The channel in which to send the data.
        audio: AUDIO
            the audio to stream.
        """
        stream = None
        try:
            # Check if client has permissions before attempting to join
            client_: discord.Client = self.parent.parent.client
            member = channel.guild.get_member(client_.user.id)
            if member is None:
                raise self._generate_exception(
                    404, -1, "Client user could not be found in guild members", discord.NotFound
                )

            if channel.guild.me.pending:
                raise self._generate_exception(
                    403, 50009,
                    "Channel verification level is too high for you to gain access",
                    discord.Forbidden
                )

            ch_perms = channel.permissions_for(member)
            if not all([ch_perms.connect, ch_perms.stream, ch_perms.speak]):
                raise self._generate_exception(
                    403, 50013, "You lack permissions to perform that action", discord.Forbidden
                )

            # Check if channel still exists in cache (has not been deleted)
            if client_.get_channel(channel.id) is None:
                raise self._generate_exception(404, 10003, "Channel was deleted", discord.NotFound)

            stream = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(audio.stream, pipe=True),
                volume=self.volume / 100
            )
            await self._move_to_connect(channel, C_VC_CONNECT_TIMEOUT)
            self.voice_client.play(stream)
            await asyncio.get_event_loop().run_in_executor(None, self.voice_client._player._end.wait)
            return {"success": True}
        except Exception as ex:
            trace(f"Could not play audio due to {ex}", TraceLEVELS.ERROR)
            handled, action = await self._handle_error(channel, ex)
            return {"success": False, "reason": ex, "action": action}

    async def _move_to_connect(self, channel: discord.VoiceChannel, timeout: float):
        if self.voice_client is not None and self.voice_client.is_connected():
            if channel != self.voice_client.channel:
                await self.voice_client.move_to(channel)
        else:
            self.voice_client = channel.guild.voice_client or await channel.connect(timeout=timeout)

        self.voice_client.stop()
        await asyncio.sleep(1)
