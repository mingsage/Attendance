from pathlib import Path

import cv2
import numpy as np


def encode_array(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def decode_array(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


class FaceService:
    """人脸检测与识别服务。

    优先使用 OpenCV Zoo 的 YuNet + SFace 模型；模型缺失时才退回到传统
    Haar/HOG/LBP 特征。摄像头考勤必须先检测到真实人脸，不再使用中心裁剪。
    """

    MIN_FACE_SIZE = 80  # 最小人脸尺寸（像素），低于此值识别精度会显著下降

    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.detector_model = root / "models" / "face_detection_yunet_2023mar.onnx"
        self.recognizer_model = root / "models" / "face_recognition_sface_2021dec.onnx"
        self.use_sface = self.detector_model.exists() and self.recognizer_model.exists()

        self.haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self.hog = cv2.HOGDescriptor(
            _winSize=(128, 128),
            _blockSize=(16, 16),
            _blockStride=(8, 8),
            _cellSize=(8, 8),
            _nbins=9,
        )

        self.detector = None
        self.recognizer = None
        if self.use_sface:
            self.detector = cv2.FaceDetectorYN_create(
                str(self.detector_model),
                "",
                (320, 320),
                0.5,
                0.3,
                5000,
            )
            self.recognizer = cv2.FaceRecognizerSF_create(str(self.recognizer_model), "")

    def _enhance_image(self, image: np.ndarray) -> np.ndarray:
        """对亮度通道做 CLAHE 增强，改善不均匀光照下的检测/识别效果。"""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    def check_face_quality(self, box: tuple[int, int, int, int], image_shape: tuple) -> tuple[bool, str]:
        """检查人脸质量是否足够用于识别。

        Returns:
            (passed, message) — passed=False 时 message 说明问题。
        """
        x, y, w, h = box
        if w < self.MIN_FACE_SIZE or h < self.MIN_FACE_SIZE:
            return False, f"人脸太小（{w}×{h}），请靠近摄像头"
        if x < 0 or y < 0 or x + w > image_shape[1] or y + h > image_shape[0]:
            return False, "人脸过于贴近画面边缘"
        return True, ""

    def center_face_box(self, image: np.ndarray) -> tuple[int, int, int, int]:
        h, w = image.shape[:2]
        size = int(min(h, w) * 0.72)
        return (w // 2 - size // 2, h // 2 - size // 2, size, size)

    def _approx_sface_row(self, box: tuple[int, int, int, int]) -> np.ndarray:
        x, y, w, h = map(float, box)
        return np.array(
            [
                x,
                y,
                w,
                h,
                x + 0.35 * w,
                y + 0.38 * h,
                x + 0.65 * w,
                y + 0.38 * h,
                x + 0.50 * w,
                y + 0.55 * h,
                x + 0.38 * w,
                y + 0.75 * h,
                x + 0.62 * w,
                y + 0.75 * h,
                0.5,
            ],
            dtype=np.float32,
        )

    def _detect_sface_rows(self, image: np.ndarray) -> list[np.ndarray]:
        if not self.use_sface or self.detector is None:
            return []
        # 增强后检测，改善暗光/逆光下的检出率
        enhanced = self._enhance_image(image)
        h, w = enhanced.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(enhanced)
        if faces is None:
            return []
        return [face.astype(np.float32) for face in faces]

    def detect_sface_rows(self, image: np.ndarray) -> list[np.ndarray]:
        """检测人脸并返回完整的 YuNet 15 维行（含 5 个面部关键点）。

        每行格式：[x, y, w, h, re_x, re_y, le_x, le_y, n_x, n_y, rc_x, rc_y, lc_x, lc_y, roll]
        供活体检测动作验证使用。若 SFace 模型不可用或无检测结果，返回空列表。
        """
        return self._detect_sface_rows(image)

    def detect_faces(self, image: np.ndarray, allow_fallback: bool = False) -> list[tuple[int, int, int, int]]:
        sface_rows = self._detect_sface_rows(image)
        if sface_rows:
            return [tuple(map(int, face[:4])) for face in sface_rows]

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.haar.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(48, 48))
        if len(faces):
            return [tuple(map(int, face)) for face in faces]
        return [self.center_face_box(image)] if allow_fallback else []

    def _crop_face(self, image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
        x, y, w, h = box
        ih, iw = image.shape[:2]
        pad = int(max(w, h) * 0.18)
        x1, y1 = max(x - pad, 0), max(y - pad, 0)
        x2, y2 = min(x + w + pad, iw), min(y + h + pad, ih)
        face = image[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else image
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        gray = self.clahe.apply(gray)
        return cv2.GaussianBlur(gray, (3, 3), 0)

    @staticmethod
    def _lbp_hist(gray: np.ndarray) -> np.ndarray:
        center = gray[1:-1, 1:-1]
        code = np.zeros_like(center, dtype=np.uint8)
        neighbors = [
            gray[:-2, :-2],
            gray[:-2, 1:-1],
            gray[:-2, 2:],
            gray[1:-1, 2:],
            gray[2:, 2:],
            gray[2:, 1:-1],
            gray[2:, :-2],
            gray[1:-1, :-2],
        ]
        for bit, item in enumerate(neighbors):
            code |= ((item >= center).astype(np.uint8) << bit)
        hists = []
        for row in np.array_split(code, 4, axis=0):
            for cell in np.array_split(row, 4, axis=1):
                hist = np.bincount(cell.ravel(), minlength=256).astype(np.float32)
                hist /= hist.sum() or 1.0
                hists.append(hist)
        return np.concatenate(hists)

    def _manual_feature(self, image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
        gray = self._crop_face(image, box)
        hog_feature = self.hog.compute(gray).flatten().astype(np.float32)
        hog_feature /= np.linalg.norm(hog_feature) or 1.0
        lbp_feature = self._lbp_hist(gray)
        dct = cv2.dct(gray.astype(np.float32) / 255.0)[:16, :16].flatten()
        thumbnail = cv2.resize(gray, (24, 24), interpolation=cv2.INTER_AREA).flatten().astype(np.float32) / 255.0
        feature = np.concatenate([hog_feature * 0.55, lbp_feature * 0.30, dct * 0.10, thumbnail * 0.05])
        feature -= feature.mean()
        feature /= np.linalg.norm(feature) or 1.0
        return feature.astype(np.float32)

    def _sface_feature_from_row(self, image: np.ndarray, face: np.ndarray) -> np.ndarray:
        if self.recognizer is None:
            raise RuntimeError("SFace recognizer is not initialized")
        aligned = self.recognizer.alignCrop(image, face)
        # 对对齐后人脸做光照归一化（CLAHE），提升不同光照条件下的特征一致性
        lab = cv2.cvtColor(aligned, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        aligned = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        # 轻微锐化，补偿摄像头常见的轻微模糊
        sharpen = np.array([[-0.3, -0.3, -0.3],
                            [-0.3,  3.4, -0.3],
                            [-0.3, -0.3, -0.3]], dtype=np.float32)
        aligned = cv2.filter2D(aligned, -1, sharpen)
        feature = self.recognizer.feature(aligned).flatten().astype(np.float32)
        feature /= np.linalg.norm(feature) or 1.0
        return feature

    def extract_feature(self, image: np.ndarray, box: tuple[int, int, int, int] | None = None) -> np.ndarray:
        """提取特征；仅用于兼容旧接口（如合照识别），必要时会回退到中心区域。"""

        if self.use_sface and self.recognizer is not None:
            sface_rows = self._detect_sface_rows(image)
            face = sface_rows[0] if sface_rows else self._approx_sface_row(box or self.center_face_box(image))
            # 只用原始图像做 alignCrop，CLAHE 在 _sface_feature_from_row 内部对对齐后人脸做一次
            return self._sface_feature_from_row(image, face)
        return self._manual_feature(image, box or self.center_face_box(image))

    def extract_detected_feature(self, image: np.ndarray) -> np.ndarray | None:
        """只在检测到真实人脸时提取特征，供入库和摄像头考勤使用。"""

        if self.use_sface and self.recognizer is not None:
            sface_rows = self._detect_sface_rows(image)
            if not sface_rows:
                return None
            face = max(sface_rows, key=lambda item: float(item[2] * item[3]))

            box = tuple(map(int, face[:4]))
            quality_ok, _ = self.check_face_quality(box, image.shape)
            if not quality_ok:
                return None

            # 只用原始图像做 alignCrop，CLAHE 在 _sface_feature_from_row 内部对对齐后人脸做一次
            return self._sface_feature_from_row(image, face)

        faces = self.detect_faces(image, allow_fallback=False)
        if not faces:
            return None
        quality_ok, _ = self.check_face_quality(faces[0], image.shape)
        if not quality_ok:
            return None
        return self._manual_feature(image, faces[0])

    @staticmethod
    def _score(probe: np.ndarray, feature: np.ndarray) -> float | None:
        if feature.size == 0 or feature.shape != probe.shape:
            return None
        cosine = float(np.dot(probe, feature) / ((np.linalg.norm(probe) * np.linalg.norm(feature)) or 1.0))
        return (cosine + 1.0) / 2.0

    def identify(
        self,
        image: np.ndarray,
        probe: np.ndarray,
        candidates: list[tuple[int, np.ndarray, str | None]],
    ) -> tuple[int | None, float]:
        scored: list[tuple[int, float]] = []
        for student_id, feature, _image_path in candidates:
            score = self._score(probe, feature)
            if score is not None:
                scored.append((student_id, score))

        if not scored:
            return None, 0.0
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[0][0], round(scored[0][1], 3)

    def compare(self, probe: np.ndarray, candidates: list[tuple[int, np.ndarray]]) -> tuple[int | None, float]:
        """兼容集体照识别接口。"""

        converted = [(student_id, feature, None) for student_id, feature in candidates]
        return self.identify(np.empty((0, 0, 3), dtype=np.uint8), probe, converted)


face_service = FaceService()
