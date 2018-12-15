#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest
from pytest import raises, approx
from EasyVision.exceptions import *
from EasyVision.engine.base import EngineBase
from EasyVision.vision.base import VisionBase


class Subclass(EngineBase):

    def __init__(self, vision, *args, **kwargs):
        super(Subclass, self).__init__(vision, *args, **kwargs)

    def compute(self):
        return self.vision.capture()

    @property
    def description(self):
        pass

    @property
    def capabilities(self):
        pass


class VisionSubclass(VisionBase):

    def __init__(self, *args, **kwargs):
        super(VisionSubclass, self).__init__(*args, **kwargs)
        self.frame = 0
        self.frames = 10

    def capture(self):
        from datetime import datetime
        self.frame += 1
        return (datetime.now, ('an image',))

    def release(self):
        pass

    @property
    def is_open(self):
        print self.frame, self.frames
        return self.frame < self.frames

    @property
    def description(self):
        pass

    @property
    def path(self):
        pass

    @property
    def frame_size(self):
        pass

    @property
    def fps(self):
        pass

    @property
    def frame_count(self):
        return self.frames

    @property
    def devices(self):
        """
        :return: [{name:, description:, path:, etc:}]
        """
        pass


def test_abstract_vision_abstract():
    with raises(TypeError):
        _ = EngineBase(None)


def test_abstract_vision_implementation():
    _ = Subclass(VisionSubclass())


def test_abstract_vision_implementation_bar_arg():
    class BadVision(object):
        pass

    with raises(TypeError):
        _ = Subclass(BadVision())


def test_iterator():
    with Subclass(VisionSubclass()) as engine:
        count = 0
        for result in engine:
            count += 1
            if count > 13:
                break
        assert(count == 10)