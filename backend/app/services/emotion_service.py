import cv2
import numpy as np


class EmotionService:
    """情绪分析服务：HSEmotion（主力）+ DeepFace（复核）+ OpenCV（保底）。"""

    # HSEmotion 8 类 → 项目 7 类标签映射
    HS_LABEL_MAP = {
        "Happiness": "happy",
        "Sadness": "sad",
        "Anger": "angry",
        "Surprise": "surprised",
        "Fear": "fearful",
        "Disgust": "disgusted",
        "Contempt": "disgusted",
        "Neutral": "neutral",
    }

    HS_CONFIDENCE_FLOOR = 0.6  # 低于此值进入 DeepFace 复核

    def __init__(self) -> None:
        self._hsemotion = None
        self.face_detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.smile_detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_smile.xml"
        )
        self.eye_detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye.xml"
        )

    @property
    def hsemotion(self):
        if self._hsemotion is None:
            from hsemotion.facial_emotions import HSEmotionRecognizer

            self._hsemotion = HSEmotionRecognizer(
                model_name="enet_b0_8_best_afew", device="cpu"
            )
        return self._hsemotion

    @staticmethod
    def _crop_face(
        image: np.ndarray, box: tuple[int, int, int, int] | None
    ) -> np.ndarray:
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
    def _to_rgb(bgr: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # ── 主入口 ─────────────────────────────────────────────

    def analyze(
        self, image: np.ndarray, box: tuple[int, int, int, int] | None = None
    ) -> tuple[str, float]:
        face = self._crop_face(image, box)

        # 第一层：HSEmotion（主力引擎）
        emotion, confidence = self._hs_analyze(face)
        if emotion is not None:
            return emotion, confidence

        # 第二层：DeepFace（复核引擎）
        emotion, confidence = self._deepface_analyze(face)
        if emotion is not None:
            return emotion, confidence

        # 第三层：OpenCV 启发式（保底）
        return self._fallback_analyze(face)

    # ── HSEmotion ──────────────────────────────────────────

    def _hs_analyze(self, face: np.ndarray) -> tuple[str | None, float]:
        try:
            label, scores = self.hsemotion.predict_emotions(
                self._to_rgb(face), logits=False
            )
            idx = int(np.argmax(scores))
            max_conf = round(float(scores[idx]), 3)
            if max_conf >= self.HS_CONFIDENCE_FLOOR:
                mapped = self.HS_LABEL_MAP.get(label, "neutral")
                return mapped, max_conf
        except Exception:
            pass
        return None, 0.0

    # ── DeepFace ───────────────────────────────────────────

    @staticmethod
    def _deepface_analyze(face: np.ndarray) -> tuple[str | None, float]:
        try:
            from deepface import DeepFace

            result = DeepFace.analyze(
                face, actions=["emotion"], enforce_detection=False, silent=True
            )
            if isinstance(result, list):
                result = result[0]
            emotion = result["dominant_emotion"]
            confidence = round(result["emotion"][emotion] / 100.0, 3)
            return emotion, confidence
        except Exception:
            pass
        return None, 0.0

    # ── OpenCV 回退 ────────────────────────────────────────

    @staticmethod
    def _softmax(scores: dict[str, float]) -> dict[str, float]:
        labels = list(scores)
        values = np.array([scores[label] for label in labels], dtype=np.float32)
        values -= values.max()
        exp = np.exp(values)
        probs = exp / (exp.sum() or 1.0)
        return {label: float(prob) for label, prob in zip(labels, probs)}

    def _fallback_analyze(self, face: np.ndarray) -> tuple[str, float]:
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        gray = cv2.equalizeHist(gray)

        mean = float(np.mean(gray)) / 255.0
        contrast = min(float(np.std(gray)) / 80.0, 1.5)
        edges = cv2.Canny(gray, 80, 160)
        edge_density = float(np.mean(edges > 0))

        upper = gray[:64, :]
        lower = gray[64:, :]
        upper_grad = (
            float(np.mean(np.abs(cv2.Sobel(upper, cv2.CV_32F, 1, 0)))) / 80.0
        )
        lower_grad = (
            float(np.mean(np.abs(cv2.Sobel(lower, cv2.CV_32F, 1, 0)))) / 80.0
        )

        lower_face = gray[70:124, 16:112]
        smiles = self.smile_detector.detectMultiScale(
            lower_face, scaleFactor=1.3, minNeighbors=10, minSize=(18, 10)
        )
        eyes = self.eye_detector.detectMultiScale(
            gray[:72, :], scaleFactor=1.1, minNeighbors=5, minSize=(12, 12)
        )
        smile_strength = min(len(smiles), 2) / 2.0
        eye_strength = min(len(eyes), 2) / 2.0

        mouth_brightness = float(np.mean(lower_face)) / 255.0
        brow_mouth_gap = upper_grad - lower_grad

        scores = {
            "happy": 1.4 * smile_strength + 0.35 * lower_grad + 0.15 * mean,
            "sad": 0.65 * (1.0 - mean)
            + 0.35 * max(brow_mouth_gap, 0.0)
            + 0.2 * (1.0 - smile_strength),
            "angry": 0.55 * upper_grad
            + 0.45 * contrast
            + 0.25 * edge_density
            - 0.25 * smile_strength,
            "surprised": 0.55 * edge_density
            + 0.35 * contrast
            + 0.25 * mouth_brightness
            + 0.15 * eye_strength,
            "fearful": 0.35 * contrast + 0.25 * eye_strength + 0.2 * edge_density,
            "disgusted": 0.35 * lower_grad
            + 0.25 * contrast
            + 0.2 * (1.0 - mouth_brightness),
            "neutral": 0.85
            - abs(mean - 0.5)
            - 0.25 * contrast
            - 0.25 * smile_strength,
        }
        probs = self._softmax(scores)
        emotion = max(probs, key=probs.get)
        confidence = round(0.45 + min(probs[emotion] * 1.4, 0.5), 3)
        return emotion, confidence


emotion_service = EmotionService()
