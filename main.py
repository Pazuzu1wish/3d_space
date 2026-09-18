import argparse

from src.game import Game
from src.controller import LAYOUTS

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='3D Space — Cockpit Dogfighter')
    parser.add_argument('--layout', choices=['auto'] + sorted(LAYOUTS), default='auto',
                        help="Controller layout: 'ds4', 'xpad' (Xbox-style / TwinStick phone app), "
                             "or 'auto' to guess from the device name (default: auto)")
    args = parser.parse_args()

    layout = None if args.layout == 'auto' else args.layout
    Game(layout=layout).main()
