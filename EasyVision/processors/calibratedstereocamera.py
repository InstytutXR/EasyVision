# -*- coding: utf-8 -*-
import cv2
import numpy as np
from .base import *
from .calibratedcamera import PinholeCamera


class StereoCamera(namedtuple('StereoCamera', ['left', 'right', 'R', 'T', 'E', 'F'])):

    @staticmethod
    def from_parameters(left, right, R, T, E, F):
        if not isinstance(left, PinholeCamera):
            raise ValueError("Left camera must be PinholeCamera")
        if not isinstance(right, PinholeCamera):
            raise ValueError("Right camera must be PinholeCamera")
        if left.width != right.width or left.height != right.height:
            raise ValueError("Left and Right camera width/height must match")

        return StereoCamera(left, right, R, T, E, F)


class CameraPairProxy(VisionBase):
    def __init__(self, _self, left, right):
        self._left = left
        self._right = right
        self._self = _self
        super(CameraPairProxy, self).__init__()

    def setup(self):
        self._left.setup()
        self._right.setup()
        super(CameraPairProxy, self).setup()

    def release(self):
        self._left.release()
        self._right.release()
        super(CameraPairProxy, self).release()

    def capture(self):
        super(CameraPairProxy, self).capture()
        left = self._left.capture()
        right = self._right.capture()
        if left is None or right is None:
            return None
        return left._replace(images=left.images + right.images)

    @property
    def is_open(self):
        return self._left.is_open and self._right.is_open

    @property
    def frame_size(self):
        return self._left.frame_size

    @property
    def fps(self):
        return self._left.fps

    @property
    def name(self):
        return "({} : {})".format(self._left.name, self._right.name)

    @property
    def frame_count(self):
        return self._left.frame_count

    @property
    def path(self):
        return self._left.path

    @property
    def description(self):
        return "Stereo Pair Vision Proxy"

    @property
    def devices(self):
        return self._left.devices


class CalibratedStereoCamera(ProcessorBase):

    def __init__(self, left, right, camera, grid_shape=(7, 6), max_samples=20, debug=False, display_results=False, enabled=True, *args, **kwargs):
        calibrate = camera is None
        if not isinstance(left, ProcessorBase) or not isinstance(right, ProcessorBase) or \
           left.get_source('CalibratedCamera') is None or right.get_source('CalibratedCamera') is None:
            raise TypeError("Left/Right must have CalibratedCamera")
        if not calibrate:
            if not isinstance(camera, StereoCamera) and not (isinstance(camera, tuple) and len(camera) == 6):
                raise TypeError("Camera must be either StereoCamera or tuple with (frame_size, camera_matrix, distortion)")
            self._camera = StereoCamera._make(camera)
            if left.camera != camera.left or right.camera != camera.right:
                raise ValueError("Respective CalibratedCamera.camera must equal Camera.left/Camera.right")
            if left._calibrate or right._calibrate:
                raise ValueError("Left and Right cameras must NOT be set to calibrate mode")
        else:
            if not left._calibrate or not right._calibrate:
                raise ValueError("Left and Right cameras must be set to calibrate mode")
            left._grid_shape = grid_shape
            self._grid_shape = grid_shape
            self._camera = None
            self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            self.stereocalib_criteria = (cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS, 100, 1e-5)
            self.flags = 0
            self.flags |= cv2.CALIB_FIX_INTRINSIC
            # self.flags |= cv2.CALIB_FIX_PRINCIPAL_POINT
            self.flags |= cv2.CALIB_USE_INTRINSIC_GUESS
            self.flags |= cv2.CALIB_FIX_FOCAL_LENGTH
            # self.flags |= cv2.CALIB_FIX_ASPECT_RATIO
            self.flags |= cv2.CALIB_ZERO_TANGENT_DIST
            # self.flags |= cv2.CALIB_RATIONAL_MODEL
            # self.flags |= cv2.CALIB_SAME_FOCAL_LENGTH
            # self.flags |= cv2.CALIB_FIX_K3
            # self.flags |= cv2.CALIB_FIX_K4
            # self.flags |= cv2.CALIB_FIX_K5
            self._max_samples = max_samples

        vision = CameraPairProxy(self, left, right)

        self._calibrate = calibrate
        super(CalibratedStereoCamera, self).__init__(vision, debug=debug, display_results=display_results, enabled=enabled, *args, **kwargs)

    def setup(self):
        super(CalibratedStereoCamera, self).setup()
        if self._calibrate:
            # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
            self.objp = np.zeros((self._grid_shape[0] * self._grid_shape[1], 3), np.float32)
            self.objp[:, :2] = np.mgrid[0:self._grid_shape[0], 0:self._grid_shape[1]].T.reshape(-1, 2)

            # Arrays to store object points and image points from all the images.
            self.objpoints = []  # 3d point in real world space
            self.imgpoints_l = []  # 2d points in image plane.
            self.imgpoints_r = []  # 2d points in image plane.
            self.calibration_samples = 0

    @property
    def description(self):
        return "Stereo Camera rectify processor"

    @property
    def camera(self):
        return self._camera

    def process(self, image):
        if self._calibrate:
            return image
        else:
            # TODO: rectified images
            return image

    def calibrate(self):
        if not self._calibrate:
            raise ValueError("calibrate parameter must be set")

        if self.calibration_samples >= self._max_samples:
            return self._camera

        frame = self.capture()
        left = frame.images[0]
        right = frame.images[1]

        ret_l, corners_l = left.features
        ret_r, corners_r = right.features

        if ret_l is True and ret_r is True:
            self.objpoints.append(self.objp)
            self.imgpoints_l.append(corners_l)
            self.imgpoints_r.append(corners_r)

            # Draw and display the corners
            if self.display_results:
                img = cv2.drawChessboardCorners(left.image, self._grid_shape, corners_l, ret_l)
                cv2.imshow("Left", img)

                img = cv2.drawChessboardCorners(right.image, self._grid_shape, corners_r, ret_r)
                cv2.imshow("Right", img)

            self.calibration_samples += 1

        if self.calibration_samples > self._max_samples:
            img_shape = left.image.shape[::-1]
            self._finish_calibration(self.objpoints, self.imgpoints_l, self.imgpoints_r, img_shape)

    def _finish_calibration(self, objpoints, imgpoints_l, imgpoints_r, shape):
        left_camera = self.source._left._finish_calibration(objpoints, imgpoints_l, shape)
        right_camera = self.source._right._finish_calibration(objpoints, imgpoints_r, shape)

        ret, M1, d1, M2, d2, R, T, E, F = cv2.stereoCalibrate(
            objpoints,
            imgpoints_l, imgpoints_r,
            left_camera.matrix, left_camera.distortion,
            right_camera.matrix, right_camera.distortion,
            shape,
            criteria=self.stereocalib_criteria, flags=self.flags)

        left_camera = PinholeCamera((shape[0], shape[1]), M1, d1)
        right_camera = PinholeCamera((shape[0], shape[1]), M2, d2)

        self._camera = StereoCamera(left, right, R, T, E, F)
        return self._camera