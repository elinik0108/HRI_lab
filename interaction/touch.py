#!/usr/bin/env python
# =============================================================================
#                    HRI_lab_Pepper — Touch Sensor Module
# =============================================================================
"""
Event-driven access to Pepper's tactile head and hand sensors via Naoqi
``ALMemory``.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.interaction.touch import TouchSensor, TouchZone

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    touch = TouchSensor(session)

    def on_head(value):
        print("Head touched!", value)

    # Subscribe and store the handle to keep the connection alive
    handle = touch.on_event(TouchZone.HEAD_MIDDLE, on_head)

    # … later:
    touch.remove_event(handle)
"""

from enum import Enum
from typing import Callable, Any

from HRI_lab_Pepper.config import B, W


class TouchZone(str, Enum):
    """Naoqi memory event keys for Pepper's touch sensors."""

    # Head
    HEAD_FRONT  = "FrontTactilTouched"
    HEAD_MIDDLE = "MiddleTactilTouched"
    HEAD_REAR   = "RearTactilTouched"

    # Hands
    HAND_LEFT   = "HandLeftBackTouched"
    HAND_RIGHT  = "HandRightBackTouched"

    # Bumpers
    BUMPER_LEFT  = "LeftBumperPressed"
    BUMPER_RIGHT = "RightBumperPressed"
    BUMPER_BACK  = "BackBumperPressed"

    # Chest button
    CHEST       = "ChestButtonPressed"


# Raw ALMemory data-key paths for synchronous bulk polling.
# Used by get_all_state() to read all sensors in one RPC call.
_SENSOR_DATA_KEYS: dict = {
    "head_front":   "Device/SubDeviceList/Head/Touch/Front/Sensor/Value",
    "head_middle":  "Device/SubDeviceList/Head/Touch/Middle/Sensor/Value",
    "head_rear":    "Device/SubDeviceList/Head/Touch/Rear/Sensor/Value",
    "hand_left":    "Device/SubDeviceList/LHand/Touch/Back/Sensor/Value",
    "hand_right":   "Device/SubDeviceList/RHand/Touch/Back/Sensor/Value",
    "bumper_fl":    "Device/SubDeviceList/Bumper/FrontLeft/Sensor/Value",
    "bumper_fr":    "Device/SubDeviceList/Bumper/FrontRight/Sensor/Value",
    "bumper_back":  "Device/SubDeviceList/Bumper/Back/Sensor/Value",
    "chest_button": "Device/SubDeviceList/ChestBoard/Button/Sensor/Value",
}


class TouchSensor:
    """
    Subscriptions to Pepper's capacitive and contact sensors.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    """

    def __init__(self, session: "qi.Session") -> None:
        self._memory  = session.service("ALMemory")
        self._handles: dict = {}
        print(f"{B}[Touch] Ready.{W}")

        from HRI_lab_Pepper.session import PepperSession
        PepperSession.register_cleanup(self.remove_all_events)

    # ------------------------------------------------------------------

    def on_event(
        self,
        zone: "TouchZone | str",
        callback: Callable[[Any], None],
    ) -> object:
        """
        Register a callback when *zone* is touched.

        Parameters
        ----------
        zone : TouchZone or str
            The sensor event key.  Use :class:`TouchZone` enum values for
            convenience.
        callback : callable
            ``callback(value)`` — called with the raw ALMemory event value
            (typically ``1.0`` for pressed, ``0.0`` for released).

        Returns
        -------
        qi.SignalSubscriber
            Keep this object alive to maintain the subscription.  Pass it
            to :meth:`remove_event` to unsubscribe.
        """
        event_key = zone.value if isinstance(zone, TouchZone) else str(zone)
        subscriber = self._memory.subscriber(event_key)
        handle     = subscriber.signal.connect(callback)
        # Store subscriber to prevent GC
        self._handles[id(handle)] = (subscriber, handle)
        print(f"{B}[Touch] Subscribed to '{event_key}'.{W}")
        return handle

    def remove_event(self, handle: object) -> None:
        """
        Unsubscribe a touch callback.

        Parameters
        ----------
        handle : object
            The value returned by :meth:`on_event`.
        """
        entry = self._handles.pop(id(handle), None)
        if entry is not None:
            subscriber, sub_handle = entry
            try:
                subscriber.signal.disconnect(sub_handle)
            except Exception:
                pass

    def remove_all_events(self) -> None:
        """Unsubscribe all registered touch callbacks."""
        for _, (subscriber, sub_handle) in list(self._handles.items()):
            try:
                subscriber.signal.disconnect(sub_handle)
            except Exception:
                pass
        self._handles.clear()

    def get_value(self, zone: "TouchZone | str") -> float:
        """
        Synchronously poll the current value of a touch sensor.

        Returns
        -------
        float
            ``1.0`` if currently pressed, ``0.0`` otherwise.
        """
        event_key = zone.value if isinstance(zone, TouchZone) else str(zone)
        return float(self._memory.getData(event_key) or 0.0)

    def get_all_state(self) -> dict:
        """
        Poll **all** 9 touch/bumper sensors in a single ALMemory RPC call.

        Returns
        -------
        dict
            Mapping of sensor short-name → bool, e.g.::

                {
                    "head_front":   False,
                    "head_middle":  True,
                    "head_rear":    False,
                    "hand_left":    False,
                    "hand_right":   False,
                    "bumper_fl":    False,
                    "bumper_fr":    False,
                    "bumper_back":  False,
                    "chest_button": False,
                }
        """
        names = list(_SENSOR_DATA_KEYS.keys())
        keys  = list(_SENSOR_DATA_KEYS.values())
        try:
            values = self._memory.getListData(keys)
        except Exception:
            # Fallback: individual getData calls
            values = [self._memory.getData(k) for k in keys]
        return {names[i]: bool(values[i] or 0) for i in range(len(names))}
