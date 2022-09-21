import argparse
import numpy as np
import struct
import colorama
from colorama import Fore, Back, Style

colorama.init(strip=False)

"""
NDI .rom file format:

little endian

byte 28: marker count
from byte 72:
    4 byte floats, every 3 is a marker
"""

# RED if different, GREEN is non-zero but same value
def color(string, values):
    not_zero = not all([x == 0 for x in values])
    different = not all([x == values[0] for x in values])

    different_color = Fore.WHITE + Back.RED + Style.BRIGHT
    not_zero_color = Fore.BLACK + Back.GREEN + Style.BRIGHT

    if different:
        return different_color + string + Style.RESET_ALL
    elif not_zero:
        return not_zero_color + string + Style.RESET_ALL
    else:
        return string


def compare(roms):
    data = zip(*[list(r) for r in roms])

    fmt = "'{: >1}' {:>3d} {:>2x}"
    fmt = "{:>4d}: " + ",    ".join([fmt for i in range(len(roms))])

    def b_to_string(b):
        if b == 0:
            return ""

        string = str(chr(b))
        return string if string.isalnum() and string.isascii() else ""

    for i, b in enumerate(data):
        row = [x for j in range(len(b)) for x in [b_to_string(b[j]), b[j], b[j]]]
        print(color(fmt.format(i, *row), b))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("input", metavar="f", type=str, nargs="+", help="Input file")
    args = parser.parse_args()

    roms = []
    for i in args.input:
        with open(i, "rb") as f:
            roms.append(f.read())

    compare(roms)
