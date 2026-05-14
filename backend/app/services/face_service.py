from __future__ import annotations

import cv2
import numpy as np


def encode_array(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def decode_array(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


class FaceService:
    """人脸检测与识别服务——基于 DeepFace。

    检测：DeepFace.extract_faces（yunet 快速 / retinaface 精确）
    识别：DeepFace.represent(model_name='Buffalo_L') → 512d
    """

    MIN_FACE_SIZE = 80
    MODEL_NAME = "Buffalo_L"  # 与 InsightFace buffalo_l 同款，512d ArcFace

    def __init__(self) -> None:
        self._deepface = None
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    @property
    def df(self):
        if self._deepface is None:
            from deepface import DeepFace
            self._deepface = DeepFace
        return self._deepface

    def _enhance(self, image: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    # ── 检测 ────────────────────────────────────────────────

    def detect(self, image: np.ndarray, backend: str = "opencv") -> list[dict]:
        """人脸检测，返回 [{"bbox": [x,y,w,h], "confidence": float}]。"""
        try:
            results = self.df.extract_faces(
                img_path=image,
                detector_backend=backend,
                enforce_detection=False,
                align=False,
            )
        except Exception:
            return []
        faces = []
        for r in results:
            area = r.get("facial_area", {})
            if area:
                faces.append({
                    "bbox": [area["x"], area["y"], area["w"], area["h"]],
                    "confidence": r.get("confidence", 0) or 0,
                })
        return faces

    def detect_faces(
        self, image: np.ndarray, allow_fallback: bool = False
    ) -> list[tuple[int, int, int, int]]:
        """兼容旧接口：返回 [(x, y, w, h)]。"""
        faces = self.detect(image, backend="retinaface")
        if faces:
            return [tuple(f["bbox"]) for f in faces]
        return [self.center_face_box(image)] if allow_fallback else []

    def detect_face_details(self, image: np.ndarray) -> list[dict]:
        """返回含嵌入的详细信息（兼容 check-in 旧调用）。"""
        faces = self.detect(image, backend="retinaface")
        results = []
        for f in faces:
            x, y, w, h = f["bbox"]
            crop = image[max(0, y):y+h, max(0, x):x+w]
            embedding = self._get_embedding(crop)
            results.append({
                "bbox": f["bbox"],
                "kps": None,
                "det_score": f["confidence"],
                "embedding": embedding,
            })
        return results

    def center_face_box(self, image: np.ndarray) -> tuple[int, int, int, int]:
        h, w = image.shape[:2]
        size = int(min(h, w) * 0.72)
        return (w // 2 - size // 2, h // 2 - size // 2, size, size)

    def check_face_quality(
        self, box: tuple[int, int, int, int], image_shape: tuple
    ) -> tuple[bool, str]:
        x, y, w, h = box
        if w < self.MIN_FACE_SIZE or h < self.MIN_FACE_SIZE:
            return False, f"人脸太小（{w}×{h}），请靠近摄像头"
        if x < 0 or y < 0 or x + w > image_shape[1] or y + h > image_shape[0]:
            return False, "人脸过于贴近画面边缘"
        return True, ""

    # ── 特征提取 ────────────────────────────────────────────

    def _get_embedding(self, face_crop: np.ndarray) -> np.ndarray | None:
        """从裁剪后的人脸区域提取 512d 嵌入。"""
        try:
            emb = self.df.represent(
                img_path=face_crop,
                model_name=self.MODEL_NAME,
                detector_backend="skip",
                enforce_detection=False,
                align=False,
            )
        except Exception:
            return None
        if emb and "embedding" in emb[0]:
            vec = np.array(emb[0]["embedding"], dtype=np.float32)
            vec = vec / (np.linalg.norm(vec) or 1.0)
            return vec
        return None

    def extract_feature(
        self, image: np.ndarray, box: tuple[int, int, int, int] | None = None
    ) -> np.ndarray | None:
        """提取 512d 特征。有 box 时先裁剪。"""
        if box is not None:
            x, y, w, h = box
            image = image[max(0, y):y+h, max(0, x):x+w]
        return self._get_embedding(image)

    def extract_detected_feature(self, image: np.ndarray) -> np.ndarray | None:
        """检测最大人脸后提取特征，带质量检查。"""
        faces = self.detect(image, backend="retinaface")
        if not faces:
            return None
        face = max(faces, key=lambda f: f["bbox"][2] * f["bbox"][3])
        box = tuple(face["bbox"])
        quality_ok, _ = self.check_face_quality(box, image.shape)
        if not quality_ok:
            return None
        x, y, w, h = box
        crop = image[max(0, y):y+h, max(0, x):x+w]
        return self._get_embedding(crop)

    # ── 识别 ────────────────────────────────────────────────

    @staticmethod
    def _score(probe: np.ndarray, feature: np.ndarray) -> float | None:
        if feature.size == 0 or feature.shape != probe.shape:
            return None
        cosine = float(np.dot(probe, feature) /
                      ((np.linalg.norm(probe) * np.linalg.norm(feature)) or 1.0))
        return (cosine + 1.0) / 2.0

    def identify(
        self,
        image: np.ndarray,
        probe: np.ndarray,
        candidates: list[tuple[int, np.ndarray, str | None]],
    ) -> tuple[int | None, float]:
        scored = [(sid, s) for sid, feat, _ in candidates
                  if (s := self._score(probe, feat)) is not None]
        if not scored:
            return None, 0.0
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0], round(scored[0][1], 3)

    def compare(
        self, probe: np.ndarray, candidates: list[tuple[int, np.ndarray]]
    ) -> tuple[int | None, float]:
        converted = [(sid, feat, None) for sid, feat in candidates]
        return self.identify(np.empty((0, 0, 3), dtype=np.uint8), probe, converted)


face_service = FaceService()
