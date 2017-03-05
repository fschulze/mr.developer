import sys


if sys.version_info < (3, 0):
    def b(x):
        return x

    def s(x):
        return x

else:
    def b(x):
        return bytes(x, "utf-8")

    def s(x):
        return str(x, "utf-8")
