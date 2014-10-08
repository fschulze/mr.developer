import sys


if sys.version_info < (3, 0):
    b = lambda x: x
    s = lambda x: x
else:
    b = lambda x: bytes(x, "utf-8")
    s = lambda x: str(x, "utf-8")
