#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest
from pytest import raises, approx
from EasyVision.vision import *
import cv2


class VideoCaptureMockClass(object):

    def __init__(self, dev):
        self._dev = dev
        self._isOpened = dev == 0

    def isOpened(self): return self._isOpened

    def set(self, propr, val): pass

    def get(self, porp): return 0

    def read(self):
        return self.isOpened(), "image"

    def release(self): pass


def VideoCaptureMock(dev):
    return VideoCaptureMockClass(dev)


def test_monocular_vision(mocker):
    mocker.patch('cv2.VideoCapture', VideoCaptureMock)
    vision = MonocularVision(0)


def test_monocular_vision_devicenotfound(mocker):
    mocker.patch('cv2.VideoCapture', VideoCaptureMock)
    with raises(DeviceNotFound):
        MonocularVision(999)


def test_monocular_vision_capture(mocker):
    mocker.patch('cv2.VideoCapture', VideoCaptureMock)
    vision = MonocularVision(0)

    img = vision.capture()
    assert(isinstance(img, Frame))


def test_monocular_vision_capture_debug(mocker):
    mocker.patch('cv2.namedWindow', autospec=True)
    mocker.patch('cv2.destroyWindow', autospec=True)
    mocker.patch('cv2.imshow', autospec=True)
    mocker.patch('cv2.VideoCapture', VideoCaptureMock)
    with MonocularVision(0) as vision:
        vision.debug = True
        img = vision.capture()
        assert(isinstance(img, Frame))
        assert(img.images[0].source is vision)
        assert(img.images[0].image == "image")

    name = "Capture 0"
    cv2.namedWindow.assert_called_with(name, cv2.WINDOW_NORMAL)
    cv2.destroyWindow.assert_called_with(name)
    cv2.imshow.assert_called_with(name, "image")
