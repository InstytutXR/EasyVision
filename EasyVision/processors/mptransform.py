# -*- coding: utf-8 -*-
import cv2
import numpy as np
import multiprocessing
import multiprocessing.connection
from .base import *
from EasyVision.base import EasyVisionBase
import functools
import cProfile
import cPickle


Attr = namedtuple("Attr", ['name', 'method', 'args', 'kwargs'])
multiprocessing.connection.BUFSIZE = 32 * 1024 * 1024

class MultiProcessing(ProcessorBase, multiprocessing.Process):

    def __init__(self, vision, freerun=True, *args, **kwargs):
        self._freerun = freerun

        self._running = multiprocessing.Value("i", 0)
        self._frame_in, self._frame_out = multiprocessing.Pipe(False)
        self._ctrl_in, self._ctrl_out = multiprocessing.Pipe(False)
        self._res_in, self._res_out = multiprocessing.Pipe(False)

        self._ctrl_sem = multiprocessing.Semaphore(0)
        self._res_sem = multiprocessing.Semaphore(0)

        self._run_event = multiprocessing.Event()
        self._exit_event = multiprocessing.Event()
        self._frame_event = multiprocessing.Event()
        self._cap_event = multiprocessing.Event()
        self._run_event.clear()
        self._exit_event.clear()
        self._frame_event.clear()
        self._cap_event.clear()

        super(MultiProcessing, self).__init__(vision, *args, **kwargs)

    def __getattr__(self, name):
        def caller_proxy(_self, name, attr):
            @functools.wraps(attr)
            def wrapper(*args, **kwargs):
                return _self.remote_call(name, *args, **kwargs)
            return wrapper

        if name.startswith('__') and name.endswith('__'):
            return super(MultiProcessing, self).__getattr__(name)
        attr = getattr(self._vision, name)
        if hasattr(attr, '__call__'):
            return caller_proxy(self, name, attr)
        else:
            return self.remote_get(name)

    # attribute routing to remote
    #def __setattr__(self, name, value):
    #    if hasattr(self, name):
    #        super(MultiProcessing, self).__setattr__(name, value)
    #    else:
    #        remote_set(name, value)

    def next(self):
        frame = self.capture()

        if frame is None:
            raise StopIteration()
        return frame

    def setup(self):
        assert(self._running.value == 0)
        self.start()
        self._run_event.wait(10)

    def release(self):
        self._running.value = 0
        self._exit_event.wait(10)

    @property
    def description(self):
        return "Allows processors run on a separate process"

    def process(self, image):
        return self._remote_call('process', (image,))

    def capture(self):
        assert(self._running.value)

        if not self._freerun:
            self._cap_event.set()
        self._frame_event.wait(10)
        frame = cPickle.loads(self._frame_in.recv_bytes())
        self._frame_event.clear()
        if isinstance(frame, Exception):
            raise frame
        return frame

    def _send_ctrl(self, ctrl, lock=True):
        assert(self._running.value)
        self._ctrl_out.send(ctrl)
        self._ctrl_sem.release()
        self._res_sem.acquire(lock)
        res = self._res_in.recv()
        if isinstance(res, Exception):
            raise res
        return res

    def remote_get(self, name):
        return self._send_ctrl(Attr(name, 'GET', None, None))

    def remote_set(self, name, value):
        self._send_ctrl(Attr(name, 'SET', value, None))

    def remote_call(self, name, *args, **kwargs):
        return self._send_ctrl(Attr(name, 'CALL', args, kwargs))

    def _remote_call_handle(self):
        if self._ctrl_sem.acquire(False):
            ctrl = self._ctrl_in.recv()
            try:
                result = None
                if ctrl.method == 'SET':
                    cur_obj = self._vision
                    while cur_obj or last_obj:
                        last_obj, cur_obj = cur_obj, getattr(cur_obj, '_vision', None)

                        if hasattr(last_obj, ctrl.name) and not hasattr(cur_obj, ctrl.name):
                            setattr(last_obj, ctrl.name, ctrl.args)
                            break
                    if not cur_obj and not last_obj:
                        raise AttributeError("can't set attribute")
                elif ctrl.method == 'GET':
                    result = getattr(self._vision, ctrl.name)
                elif ctrl.method == 'CALL':
                    result = getattr(self._vision, ctrl.name)(*ctrl.args, **ctrl.kwargs)
                else:
                    pass
                self._res_out.send(result)
            except Exception as e:
                self._res_out.send(e)
            finally:
                self._res_sem.release()

    def run(self):
        cProfile.runctx('self._run()', globals(), locals(), 'processing.profile')

    def _run(self):
        super(MultiProcessing, self).setup()
        self._running.value = 1
        self._lazy_frame = None
        self._run_event.set()
        while self._running.value:
            self._remote_call_handle()

            try:
                if self._freerun:
                    self._capture_freerun()
                else:
                    self._capture_lazy()
            except Exception as e:
                self._send_frame(e)

        super(MultiProcessing, self).release()
        self._exit_event.set()

    def _send_frame(self, frame):
        if not self._frame_event.is_set():
            self._frame_out.send_bytes(cPickle.dumps(frame, protocol=-1))
            self._frame_event.set()

    def _capture_freerun(self):
        frame = self._vision.capture()
        self._send_frame(frame)
        if not frame:
            self.running.value = 0

    def _capture_lazy(self):
        if self._cap_event.wait(.001):
            if self._lazy_frame:
                self._send_frame(self._lazy_frame)
                self._cap_event.clear()
            self._lazy_frame = self._vision.capture()
            if not self._lazy_frame:
                self._send_frame(None)
                self.running.value = 0

    #def enabled_changed(self, last, current):
    #    self.remote_set('enabled', current)

    #def debug_changed(self, last, current):
    #    self.remote_set('debug', current)

    #def display_results_changed(self, last, current):
    #    self.remote_set('display_results', current)
