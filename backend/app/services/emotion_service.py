import cv2
import numpy as np


class EmotionService:
    """情绪分析服务：先裁剪人脸区域，再尝试 DeepFace；失败时回退到 OpenCV 启发式分类。"""

    def __init__(self) -> None:
        self.face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.smile_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")
        self.eye_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

    @staticmethod
    def _crop_face(image: np.ndarray, box: tuple[int, int, int, int] | None) -> np.ndarray:
        """从图像中裁剪人脸区域，附带 40% 边距。"""
        if box is not None:
            x, y, w, h = box
        else:
            ih, iw = image.shape[:2]
            size = int(min(iw, ih) * 0.72)
            x, y, w, h = (iw // 2 - size // 2, ih // 2 - size // 2, size, size)
        ih, iw = image.shape[:2]
        pad = int(max(w, h) * 0.40)
        x1 = max(x - pad, 0)
        y1 = max(y - pad, 0)
        x2 = min(x + w + pad, iw)
        y2 = min(y + h + pad, ih)
        face = image[y1:y2, x1:x2]
        return face if face.size > 0 else image

    @staticmethod
    def _softmax(scores: dict[str, float]) -> dict[str, float]:
        labels = list(scores)
        values = np.array([scores[label] for label in labels], dtype=np.float32)
        values -= values.max()
        exp = np.exp(values)
        probs = exp / (exp.sum() or 1.0)
        return {label: float(prob) for label, prob in zip(labels, probs)}

    def analyze(self, image: np.ndarray, box: tuple[int, int, int, int] | None = None) -> tuple[str, float]:
        # 先裁剪人脸区域
        face = self._crop_face(image, box)

        # 优先 DeepFace（仅在裁剪后的人脸上运行）
        try:
            from deepface import DeepFace

            result = DeepFace.analyze(face, actions=["emotion"], enforce_detection=False, silent=True)
            if isinstance(result, list):
                result = result[0]
            emotion = result["dominant_emotion"]
            confidence = round(result["emotion"][emotion] / 100.0, 3)
            # DeepFace 返回 fear/disgust，归一化到 fearful/disgusted
            _normalize = {"fear": "fearful", "disgust": "disgusted"}
            return _normalize.get(emotion, emotion), confidence
        except Exception:
            pass

        return self._fallback_analyze(face)

    def _fallback_analyze(self, face: np.ndarray) -> tuple[str, float]:
        """OpenCV 启发式情绪分类（仅在 DeepFace 不可用或失败时使用）。"""
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        gray = cv2.equalizeHist(gray)

        mean = float(np.mean(gray)) / 255.0
        contrast = float(np.std(gray)) / 80.0
        contrast = min(contrast, 1.5)
        edges = cv2.Canny(gray, 80, 160)
        edge_density = float(np.mean(edges > 0))

        upper = gray[:64, :]
        lower = gray[64:, :]
        upper_grad = float(np.mean(np.abs(cv2.Sobel(upper, cv2.CV_32F, 1, 0)))) / 80.0
        lower_grad = float(np.mean(np.abs(cv2.Sobel(lower, cv2.CV_32F, 1, 0)))) / 80.0

        lower_face = gray[70:124, 16:112]
        smiles = self.smile_detector.detectMultiScale(lower_face, scaleFactor=1.3, minNeighbors=10, minSize=(18, 10))
        eyes = self.eye_detector.detectMultiScale(gray[:72, :], scaleFactor=1.1, minNeighbors=5, minSize=(12, 12))
        smile_strength = min(len(smiles), 2) / 2.0
        eye_strength = min(len(eyes), 2) / 2.0

        mouth_brightness = float(np.mean(lower_face)) / 255.0
        brow_mouth_gap = upper_grad - lower_grad

        scores = {
            "happy": 1.4 * smile_strength + 0.35 * lower_grad + 0.15 * mean,
            "sad": 0.65 * (1.0 - mean) + 0.35 * max(brow_mouth_gap, 0.0) + 0.2 * (1.0 - smile_strength),
            "angry": 0.55 * upper_grad + 0.45 * contrast + 0.25 * edge_density - 0.25 * smile_strength,
            "surprised": 0.55 * edge_density + 0.35 * contrast + 0.25 * mouth_brightness + 0.15 * eye_strength,
            "fearful": 0.35 * contrast + 0.25 * eye_strength + 0.2 * edge_density,
            "disgusted": 0.35 * lower_grad + 0.25 * contrast + 0.2 * (1.0 - mouth_brightness),
            "neutral": 0.85 - abs(mean - 0.5) - 0.25 * contrast - 0.25 * smile_strength,
        }
        probs = self._softmax(scores)
        emotion = max(probs, key=probs.get)
        confidence = probs[emotion]
        display_confidence = round(0.45 + min(confidence * 1.4, 0.5), 3)
        return emotion, display_confidence


emotion_service = EmotionService()
