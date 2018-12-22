# -*- coding: utf-8 -*-
import cv2
import numpy as np
import multiprocessing
from .base import *


class MultiProcessing(ProcessorBase, multiprocessing.Process):
    def __init__(self, vision, freerun=True, *args, **kwargs):
        self._freerun = freerun

        self.exit_event = multiprocessing.Event()
        self.event = multiprocessing.Event()
        self.cap_event = multiprocessing.Event()
        self.exit_event.clear()
        self.event.clear()
        self.cap_event.clear()
        self.running = multiprocessing.Value("i", 1)
        self._in, self._out = multiprocessing.Pipe()

        super(MultiProcessing, self).__init__(vision, *args, **kwargs)

        self.start()

    @property
    def description(self):
        return "Allows processors run on a separate process"

    def process(self, image):
        return self._vision.process(image)

    def capture(self):
        if not self.enabled:
            return self._vision.capture()

        if self.running.value == 0:
            return None

        if self._freerun:
            self.cap_event.set()

        self.event.wait(10)
        print 'wait done'
        frame = self._out.recv()
        print frame
        self.event.clear()
        return frame

    def release(self):
        self.running.value = 0
        self.exit_event.wait(1)
        self._vision.release()

    def run(self):
        frame = None
        while self.running.value:
            if self._freerun:
                frame = self._vision.capture()
                if not frame:
                    self.running.value = 0
                    print 'not running anymore'
                    return

                if not self.event.is_set():
                    print 'event not set'
                    self._in.send(frame)
                    self.event.set()
            else:
                self.cap_event.wait(1)
                if frame:
                    self._in.send(frame)
                    self.event.set()
                    self.cap_event.clear()
                frame = self._vision.capture()
                if not frame:
                    self.running.value = 0
                    return
        self.exit_event.set()

    def enabled_changed(self, last, current):
        pass