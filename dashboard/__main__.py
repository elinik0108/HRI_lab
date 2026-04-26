"""Entry point: python -m HRI_lab_Pepper.dashboard [--url ...]"""

import time
import threading

from HRI_lab_Pepper.dashboard.server import _cli
from HRI_lab_Pepper.session import PepperSession
from HRI_lab_Pepper.speech.tts import TextToSpeech


# ------------------------------------------------------------
# Setup Pepper
# ------------------------------------------------------------
session = PepperSession.connect("tcp://172.18.48.52:9559")

tts = TextToSpeech(session)
tts.set_language("English")
tts.set_volume(70)
tts.set_speed(80)

tts.speak("Hi")
tts.speak("What's going on?")


memory = session.service("ALMemory")


# ------------------------------------------------------------
# Touch logic
# ------------------------------------------------------------
def touch_loop():
    print("[TOUCH] Loop started")

    while True:
        if memory.getData("FrontTactilTouched"):
            print("Front head touched")
            tts.speak("You touched my head!")

        elif memory.getData("MiddleTactilTouched"):
            print("Middle head touched")
            tts.speak("Middle head touched!")

        elif memory.getData("RearTactilTouched"):
            print("Back head touched")
            tts.speak("You touched the back of my head!")

        elif memory.getData("HandLeftBackTouched"):
            print("Don't touch my left hand!")
            tts.speak("Don't touch my left hand!")

        time.sleep(0.2)


# ------------------------------------------------------------
# Start robot loop in background thread
# ------------------------------------------------------------
t = threading.Thread(target=touch_loop, daemon=True)
t.start()


# ------------------------------------------------------------
# Start dashboard (MAIN THREAD)
# ------------------------------------------------------------
print("[CORE] Starting dashboard server...")
_cli()