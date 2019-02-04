# -*- coding: utf-8 -*-
from .base import *
import Pyro4
import functools
import cPickle
import socket
from EasyVision.server import Command


class PyroCapture(VisionBase):
    def __init__(self, name, *args, **kwargs):
        self._name = name
        self._proxy = None
        self._sock = None
        super(PyroCapture, self).__init__(*args, **kwargs)

    def __getattr__(self, name):
        def caller_proxy(_self, _name, _attr):
            @functools.wraps(_attr)
            def wrapper(*args, **kwargs):
                return _self.remote_call(_name, *args, **kwargs)
            return wrapper

        if name.startswith('__') and name.endswith('__') or self._proxy is None:
            return super(PyroCapture, self).__getattr__(name)

        attr = getattr(self._vision, name)
        if hasattr(attr, '__call__'):
            return caller_proxy(self, name, attr)
        else:
            return self.remote_get(name)

    def __command(self, cmd):
        assert(self._proxy is not None)
        data = cPickle.dumps(cmd, protocol=-1)
        blob_id = self._proxy.command(data)
        if blob_id is not None:
            self._sock.sendall(blob_id)
            f = self._sock.makefile('rb')
            return cPickle.load(f)  # FIXME: This is really very unsafe

    def remote_get(self, name):
        return self.__command(Command(name, 'GET', None, None))

    def remote_set(self, name, value):
        self.__command(Command(name, 'SET', value, None))

    def remote_call(self, name, *args, **kwargs):
        return self.__command(Command(name, 'CALL', args, kwargs))

    def setup(self):
        super(PyroCapture, self).setup()
        self._proxy = Pyro4.Proxy('PYRONAME:%s' % self._name)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect(tuple(self._proxy.getsockname()))
        self._proxy.setup()

    def release(self):
        self._proxy.release()
        self._sock.close()
        self._proxy = None
        super(PyroCapture, self).release()

    def capture(self):
        super(PyroCapture, self).capture()
        return self._proxy.capture()

    def compute(self):
        super(PyroCapture, self).capture()
        return self._proxy.compute()

    @property
    def frame_size(self):
        return self.remote_get('frame_size')

    @property
    def fps(self):
        return self.remote_get('fps')

    @property
    def frame_count(self):
        return self.remote_get('frame_count')

    @property
    def is_open(self):
        return self.remote_get('is_open')

    @property
    def name(self):
        return self._name if self._name else "Capture {}".format(self._path)

    @property
    def description(self):
        return "Remote capturer using Pyro"

    @property
    def path(self):
        return self.remote_get('path')

    @property
    def devices(self):
        return self.remote_get('devices')

    @property
    def autoexposure(self):
        return self.remote_get('autoexposure')

    @property
    def autofocus(self):
        return self.remote_get('autofocus')

    @property
    def autowhitebalance(self):
        return self.remote_get('autowhitebalance')

    @property
    def autogain(self):
        return self.remote_get('autogain')

    @property
    def exposure(self):
        return self.remote_get('exposure')

    @property
    def focus(self):
        return self.remote_get('focus')

    @property
    def whitebalance(self):
        return self.remote_get('whitebalance')

    @property
    def gain(self):
        return self.remote_get('gain')

    @autoexposure.setter
    def autoexposure(self, value):
        self.remote_set('autoexposure', value)

    @autofocus.setter
    def autofocus(self, value):
        self.remote_set('autofocus', value)

    @autowhitebalance.setter
    def autowhitebalance(self, value):
        self.remote_set('autowhitebalance', value)

    @autogain.setter
    def autogain(self, value):
        self.remote_set('autogain', value)

    @exposure.setter
    def exposure(self, value):
        self.remote_set('exposure', value)

    @focus.setter
    def focus(self, value):
        self.remote_set('focus', value)

    @whitebalance.setter
    def whitebalance(self, value):
        self.remote_set('whitebalance', value)

    @gain.setter
    def gain(self, value):
        self.remote_set('gain', value)

    # Calibrated camera specifics
    @property
    def camera(self):
        return self.remote_get('camera')

    @camera.setter
    def camera(self, value):
        self.remote_set('camera', value)
