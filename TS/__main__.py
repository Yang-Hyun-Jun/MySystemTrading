"""
[mode]
    0: simulator with interactive mode
    1: execute single simulation
    2: controller for real trading

Example) python -m TS --mode 0
Example) python -m TS --mode 1
Example) python -m TS --budget 50000 --from_dash_to 201220.170000-201220.180000 --term 1 --strategy 0
"""

import argparse

from .controller import Controller

# parser = argparse.ArgumentParser()
# parser.add_argument("--term", help="simulation tick interval (seconds)", default=2)
# args = parser.parse_args()


TS_controller = Controller()
TS_controller.main()

