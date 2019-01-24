# -*- coding: utf-8 -*-
from .base import *
from EasyVision.processors.base import *
from EasyVision.processors import FeatureExtraction, CalibratedCamera, FeatureMatchingMixin
import cv2
import numpy as np
from future_builtins import zip


class VisualOdometry2DEngine(FeatureMatchingMixin, OdometryBase):

    def __init__(self, vision, feature_type=None, pose=None, num_features=6000, min_features=1000,
                 min_matches=30, distance_thresh=None, ratio=.7, reproj_thresh=None,
                 debug=False, display_results=False, *args, **kwargs):
        feature_extractor_provided = False
        if not isinstance(vision, ProcessorBase) and not isinstance(vision, VisionBase):
            raise TypeError("Vision must be either VisionBase or ProcessorBase")
        if isinstance(vision, ProcessorBase):
            if vision.get_source('CalibratedCamera') is None:
                raise TypeError("Vision must contain CalibratedCamera")

            if vision.get_source('FeatureExtraction') is not None:
                feature_type = vision.feature_type
                feature_extractor_provided = True
            elif not feature_type:
                raise TypeError("Feature type must be provided")

        if feature_type == 'FAST':
            defaults = dict(threshold=25, nonmaxSuppression=True)
            self._extract = False
        elif feature_type == 'GFTT':
            defaults = dict(maxCorners=3000, qualityLevel=0.01, blockSize=3, minDistance=1)
            self._extract = False
        else:
            self._extract = True
            defaults = dict()

        self._distance_thresh = 200
        self._reproj_thresh = .3
        if feature_type == 'ORB':
            defaults['nfeatures'] = num_features
            #defaults['scoreType'] = cv2.ORB_FAST_SCORE
            defaults['nlevels'] = 4
            defaults.update(kwargs)
            self._reproj_thresh = .5
            self._distance_thresh = 100

        self._feature_type = feature_type
        _vision = FeatureExtraction(vision, feature_type=feature_type, extract=self._extract, **defaults) if not feature_extractor_provided else vision

        self._min_features = min_features


        self._lk_params = dict(
            winSize=(21, 21),
            #maxLevel = 3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )

        self._camera = _vision.camera
        self._last_image = None
        self._last_kps = None
        self._last_features = None
        self._last_pose = None
        self._pose = pose
        self._min_matches = min_matches
        self._ratio = ratio
        if distance_thresh is not None:
            self._distance_thresh = distance_thresh
        if reproj_thresh is not None:
            self._reproj_thresh = reproj_thresh
        super(VisualOdometry2DEngine, self).__init__(_vision, debug=debug, display_results=display_results, *args, **kwargs)

    def compute(self, absolute_scale=1.0):
        frame = self.vision.capture()
        if not frame:
            return None
        current_image = frame.images[0]

        pose = self._compute_match(current_image, absolute_scale) if self._extract else self._compute_track(current_image, absolute_scale)

        self._last_image = current_image

        return frame, pose

    def _compute_match(self, current_image, absolute_scale):
        if not self._last_image:
            self._last_kps = np.float32([x.pt for x in current_image.features.points])
        else:
            M = self._match_features(self._last_features, current_image.features)

            if M is None:
                print "failed to find matches"
                return self._pose
            last, current = M
            #if len(current) < self._min_features:
            #    return self._pose

            self._last_kps = current

            E, mask = cv2.findEssentialMat(current, last,
                                           focal=self._camera.focal_point[0], pp=self._camera.center,
                                           method=cv2.RANSAC, prob=0.999, threshold=self._reproj_thresh)

            ret, R, t, _mask = cv2.recoverPose(E, current, last, focal=self._camera.focal_point[0], pp=self._camera.center, mask=mask)

            if not ret:
                print "failed to recoverPose"
                return self._pose

            if self._pose:
                self._pose = self._pose._replace(translation=self._pose.translation + absolute_scale * self._pose.rotation.dot(t),
                                                rotation=R.dot(self._pose.rotation))
            else:
                self._pose = Pose(R, t)
            self._last_pose = Pose(R, t)

            if self.debug:
                img = cv2.cvtColor(current_image.image, cv2.COLOR_GRAY2BGR)
                img = img.get() if isinstance(img, cv2.UMat) else img
                for m, a, b in zip(mask, last, current):
                    cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 255 if m else 0, 0 if m else 255))
                    cv2.circle(img, (int(a[0]), int(a[1])), 3, (0, 255 if m else 0, 0 if m else 255))
                cv2.imshow(self.name, img)

        self._last_features = current_image.features
        return self._pose

    def _compute_track(self, current_image, absolute_scale):
        self.vision.enable = False
        if not self._last_image:
            self._last_kps = np.array([x.pt for x in current_image.features.points], dtype=np.float32)
        else:
            self._last_kps, cur_kps = self._track_features(self._last_image.image, current_image.image, self._last_kps)

            if self.debug:
                img = cv2.cvtColor(current_image.image, cv2.COLOR_GRAY2BGR)
                for a, b in zip(last, current):
                    cv2.line(img, (a[0], a[1]), (b[0], b[1]), (0, 0, 255))
                for x, y in self._last_kps:
                    cv2.circle(img, (x, y), 5, (0, 255, 0))
                cv2.imshow(self.name, img)

            E, mask = cv2.findEssentialMat(cur_kps, self._last_kps,
                                           focal=self._camera.focal_point[0], pp=self._camera.center,
                                           method=cv2.RANSAC, prob=0.999, threshold=self._reproj_thresh)
            last_kps = np.float32([kp for m, kp in zip(mask, self._last_kps) if m])
            cur_kps = np.float32([kp for m, kp in zip(mask, cur_kps) if m])
            _, R, t, mask = cv2.recoverPose(E, cur_kps, last_kps,
                                            focal=self._camera.focal_point[0], pp=self._camera.center)
            if self._pose:
                self._pose = self._pose._replace(translation=self._pose.translation + absolute_scale * self._pose.rotation.dot(t),
                                                rotation=R.dot(self._pose.rotation))
            else:
                self._pose = Pose(R, t)
            self._last_pose = Pose(R, t)

            if len(self._last_kps) < self._min_features:
                current_image = self.vision.process(current_image)
                cur_kps = np.array([x.pt for x in current_image.features.points], dtype=np.float32)

            self._last_kps = cur_kps

        return self._pose

    @property
    def feature_type(self):
        return self._feature_type

    @property
    def camera(self):
        return self._camera

    @property
    def pose(self):
        return self._pose

    @pose.setter
    def pose(self, value):
        if not isinstance(value, Pose) and value is not None:
            raise TypeError("Pose must be of type Pose")
        self._pose = value

    @property
    def relative_pose(self):
        return self._last_pose

    @property
    def camera_orientation(self):
        pass

    @camera_orientation.setter
    def camera_orientation(self, value):
        pass

    @property
    def description(self):
        return "Monocular Visual Odometry inspired by https://github.com/uoip/monoVO-python (2D-2D)"

    @property
    def capabilities(self):
        return EngineCapabilities(
                (ProcessorBase, FeatureExtraction),
                (Frame, Pose),
                {'feature_type': ('FREAK', 'SURF', 'SIFT', 'ORB', 'KAZE', 'AKAZE', 'FAST', 'GFTT')}
            )

    def _track_features(self, image_ref, image_cur, px_ref):
        kp2, st, err = cv2.calcOpticalFlowPyrLK(image_ref, image_cur, px_ref, None, **self._lk_params)  # shape: [k,2] [k,1] [k,1]

        umat = isinstance(st, cv2.UMat)
        if umat:
            st = st.get()
            kp2 = kp2.get()

        st = st.reshape(st.shape[0])
        kp1 = px_ref[st == 1]
        kp2 = kp2[st == 1]

        return kp1, kp2

    def _match_features(self, featuresA, featuresB):
        kpsA, descriptorsA = featuresA
        kpsB, descriptorsB = featuresB

        matches = super(VisualOdometry2DEngine, self)._match_features(descriptorsA, descriptorsB, self._feature_type, self._ratio, self._distance_thresh, self._min_matches)

        if matches is None or not matches:
            return None

        ptsA = [kpsA[m.queryIdx].pt for m in matches]
        ptsB = [kpsB[m.trainIdx].pt for m in matches]
        mask = [0.5 < p[0] ** 2 + p[1] ** 2 < 200 * 200 for p in ((a[0] - b[0], a[1] - b[1]) for a, b in zip(ptsA, ptsB))]

        ptsA = np.float32([p for m, p in zip(mask, ptsA) if m])
        ptsB = np.float32([p for m, p in zip(mask, ptsB) if m])

        if len(ptsA) < self._min_matches:
            print "prune fail"
            return None

        return ptsA, ptsB