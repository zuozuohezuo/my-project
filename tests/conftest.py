"""Qt integration tests run without opening native desktop windows."""

import os


os.environ["QT_QPA_PLATFORM"] = "offscreen"
