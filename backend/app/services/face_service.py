from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis


def encode_array(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def decode_array(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


class FaceService:
    """人脸检测与识别服务。

    使用 InsightFace SCRFD 检测 + ArcFace 512 维特征提取，
    替换原有的 OpenCV YuNet + SFace 方案。
    """

    MIN_FACE_SIZE = 80

    def __init__(self) -> None:
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self._app = None

    @property
    def app(self) -> FaceAnalysis:
        if self._app is None:
            self._app = FaceAnalysis(
                name="buffalo_l",
                providers=["CPUExecutionProvider"],
                allowed_modules=["detection", "recognition"],
            )
            self._app.prepare(ctx_id=-1, det_size=(640, 640), det_thresh=0.5)
        return self._app

    def _enhance_image(self, image: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    def _get_faces(self, image: np.ndarray, max_num: int = 0):
        """返回 InsightFace Face 对象列表。max_num=0 表示不限数量。"""
        enhanced = self._enhance_image(image)
        return self.app.get(enhanced, max_num=max_num)

    def check_face_quality(
        self, box: tuple[int, int, int, int], image_shape: tuple
    ) -> tuple[bool, str]:
        x, y, w, h = box
        if w < self.MIN_FACE_SIZE or h < self.MIN_FACE_SIZE:
            return False, f"人脸太小（{w}×{h}），请靠近摄像头"
        if x < 0 or y < 0 or x + w > image_shape[1] or y + h > image_shape[0]:
            return False, "人脸过于贴近画面边缘"
        return True, ""

    @staticmethod
    def _face_to_bbox(face) -> tuple[int, int, int, int]:
        b = face.bbox
        return (int(b[0]), int(b[1]), int(b[2] - b[0]), int(b[3] - b[1]))

    def center_face_box(self, image: np.ndarray) -> tuple[int, int, int, int]:
        h, w = image.shape[:2]
        size = int(min(h, w) * 0.72)
        return (w // 2 - size // 2, h // 2 - size // 2, size, size)

    # ── 检测 ────────────────────────────────────────────────

    def detect_faces(
        self, image: np.ndarray, allow_fallback: bool = False
    ) -> list[tuple[int, int, int, int]]:
        faces = self._get_faces(image)
        if faces:
            return [self._face_to_bbox(f) for f in faces]
        return [self.center_face_box(image)] if allow_fallback else []

    def detect_face_details(self, image: np.ndarray) -> list[dict]:
        """返回包含关键点和嵌入的详细信息，供活体动作验证使用。"""
        faces = self._get_faces(image)
        if not faces:
            return []
        return [
            {
                "bbox": self._face_to_bbox(f),
                "kps": f.kps.astype(np.float32) if f.kps is not None else None,
                "det_score": float(f.det_score),
                "embedding": f.normed_embedding,
            }
            for f in faces
        ]

    # ── 特征提取 ────────────────────────────────────────────

    def extract_feature(
        self, image: np.ndarray, box: tuple[int, int, int, int] | None = None
    ) -> np.ndarray | None:
        faces = self._get_faces(image, max_num=1)
        if faces:
            return faces[0].normed_embedding
        if box is None:
            box = self.center_face_box(image)
        x, y, w, h = box
        crop = image[max(0, y) : y + h, max(0, x) : x + w]
        faces = self._get_faces(crop, max_num=1)
        if faces:
            return faces[0].normed_embedding
        return None

    def extract_detected_feature(self, image: np.ndarray) -> np.ndarray | None:
        faces = self._get_faces(image)
        if not faces:
            return None
        face = max(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        )
        box = self._face_to_bbox(face)
        quality_ok, _ = self.check_face_quality(box, image.shape)
        if not quality_ok:
            return None
        return face.normed_embedding

    # ── 识别 ────────────────────────────────────────────────

    @staticmethod
    def _score(probe: np.ndarray, feature: np.ndarray) -> float | None:
        if feature.size == 0 or feature.shape != probe.shape:
            return None
        cosine = float(
            np.dot(probe, feature)
            / ((np.linalg.norm(probe) * np.linalg.norm(feature)) or 1.0)
        )
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

    def compare(
        self, probe: np.ndarray, candidates: list[tuple[int, np.ndarray]]
    ) -> tuple[int | None, float]:
        converted = [(sid, feature, None) for sid, feature in candidates]
        return self.identify(np.empty((0, 0, 3), dtype=np.uint8), probe, converted)


face_service = FaceService()
