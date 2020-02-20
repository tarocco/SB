from math import exp, log


def soft_maximum(a, b):
    return log(1 + exp(b - a)) + a


def soft_minimum(a, b):
    return b - log(1 + exp(b - a))

