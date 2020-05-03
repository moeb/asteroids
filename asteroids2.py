#!/usr/bin/env python3

import math
import time
import random

from abc import ABC, abstractmethod, abstractproperty

import pymunk
import pyglet
from pyglet import gl
from pyglet.window import key
from pyglet.graphics import Batch
from pyglet.graphics import OrderedGroup
from pyglet.sprite import Sprite


class classproperty:
    """
    helper to create immutable static classattributes
    """
    def __init__(self, f):
        self._f = f
    def __get__(self, obj, owner):
        return self._f(owner)
    def __set__(self, *args, **kwargs):
        raise RuntimeError

class Controller(type):
    _collision_type = {}

    def __new__(cls, name, bases, dct):
        self = super().__new__(cls, name, bases, dct)
        # on class creation register class with collision type
        cls._collision_type.setdefault(self, len(cls._collision_type))
        # get collision type once
        coll_type = len(cls._collision_type)
        # create property
        def _coll_fun(child_cls):
            return coll_type
        self.collision_type = property(_coll_fun)
        return self


class Test(metaclass=Controller):
    pass

class Blub(metaclass=Controller):
    pass

print(Test.collision_type)
print(Blub.collision_type)
Test.collision_type = 8
print(Test.collision_type)
