"""
    This modules contains functions and classes
    related to the console debug long or trace.
"""
from enum import Enum, auto
import time
from threading import Lock

__all__ = (
    "TraceLEVELS",
    "trace"
)

m_use_debug = None
m_lock = Lock() # For print thread safety

class TraceLEVELS(Enum):
    """
    Levels of trace for debug.

    .. seealso:: :ref:`trace`
    """
    NORMAL = 0
    WARNING = auto()
    ERROR =  auto()

def trace(message: str,
          level:   TraceLEVELS = TraceLEVELS.NORMAL):
    """
    Prints a trace to the console.
    
    Parameters
    --------------
    message: str
        Trace message.
    level: TraceLEVELS
        Level of the trace. Defaults to TraceLEVELS.NORMAL.
    """
    if m_use_debug:
        with m_lock:
            timestruct = time.localtime()
            timestamp = "Date: {:02d}.{:02d}.{:04d} Time:{:02d}:{:02d}"
            timestamp = timestamp.format(timestruct.tm_mday,
                                        timestruct.tm_mon,
                                        timestruct.tm_year,
                                        timestruct.tm_hour,
                                        timestruct.tm_min)
            l_trace = f"{timestamp}\nTrace level: {level.name}\nMessage: {message}\n"
            print(l_trace)
