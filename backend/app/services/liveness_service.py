import os
from pathlib import Path
from threading import Lock

# 必须在任何 Keras/DeepFace 导入前设置后端
os.environ["KERAS_BACKEND"] = "tensorflow"

import cv2
import numpy as np
from skimage.feature import local_binary_pattern


class LivenessService:
    """综合活体检测：融合传统图像特征与轻量反欺骗模型。

    多维度检测：
    - MiniFASNet-V2 ONNX 反欺骗模型：识别 live / print / replay
    - DeepFace 反欺骗模型（可选兜底）
    - 频域 FFT 分析：真实人脸具有自然的 1/f 频谱衰减
    - LBP 纹理分析：翻拍照片／屏幕呈现周期性重复纹理
    - 色彩多样性：打印照片色彩饱和度不足且缺乏变化
    - 清晰度 / 亮度 / 边缘密度：基础图像质量快速过滤
    """

    def __init__(self) -> None:
        self._deepface = None
        self._minifasnet = None
        self._minifasnet_lock = Lock()
        self.minifasnet_model = (
            Path(__file__).resolve().parents[2] / "models" / "minifasnet_v2.onnx"
        )
        self.smile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_smile.xml"
        )
        if self.minifasnet_model.exists():
            try:
                self._minifasnet = cv2.dnn.readNetFromONNX(str(self.minifasnet_model))
            except Exception:
                self._minifasnet = None
        if self._minifasnet is None:
            try:
                from deepface import DeepFace

                self._deepface = DeepFace
            except ImportError:
                pass

    # ------------------------------------------------------------------
    #  深度学习反欺骗
    # ------------------------------------------------------------------

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        values = values.astype(np.float32)
        values = values - np.max(values)
        exp = np.exp(values)
        return exp / (np.sum(exp) + 1e-6)

    @staticmethod
    def _scaled_face_crop(
        image: np.ndarray,
        face_box: tuple[int, int, int, int] | None,
        scale: float = 2.7,
        size: int = 80,
    ) -> np.ndarray | None:
        """按 MiniFASNet 训练方式，从人脸框中心扩大 2.7 倍裁剪 BGR 图像。"""
        ih, iw = image.shape[:2]
        if face_box is None:
            side = int(min(iw, ih) * 0.72)
            x = (iw - side) // 2
            y = (ih - side) // 2
            w = h = side
        else:
            x, y, w, h = face_box

        if w <= 0 or h <= 0:
            return None

        cx = float(x) + float(w) / 2.0
        cy = float(y) + float(h) / 2.0
        side = max(float(w), float(h)) * scale
        x1 = max(int(round(cx - side / 2.0)), 0)
        y1 = max(int(round(cy - side / 2.0)), 0)
        x2 = min(int(round(cx + side / 2.0)), iw)
        y2 = min(int(round(cy + side / 2.0)), ih)

        if x2 <= x1 or y2 <= y1:
            return None

        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        return cv2.resize(crop, (size, size), interpolation=cv2.INTER_LINEAR)

    def _minifasnet_spoof_scores(
        self,
        image: np.ndarray,
        face_box: tuple[int, int, int, int] | None = None,
    ) -> tuple[float, float, float] | None:
        """MiniFASNet-V2 ONNX 推理，返回 live / print_attack / replay_attack 概率。"""
        if self._minifasnet is None:
            return None

        crop = self._scaled_face_crop(image, face_box)
        if crop is None:
            return None

        blob = crop.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))[np.newaxis, ...]
        blob = np.ascontiguousarray(blob, dtype=np.float32)

        try:
            with self._minifasnet_lock:
                self._minifasnet.setInput(blob)
                raw = self._minifasnet.forward().reshape(-1)
            if raw.size < 3:
                return None
            if np.all(raw >= 0.0) and abs(float(np.sum(raw[:3])) - 1.0) < 1e-3:
                probs = raw[:3].astype(np.float32)
            else:
                probs = self._softmax(raw[:3])
            return float(probs[0]), float(probs[1]), float(probs[2])
        except Exception:
            return None

    def _deepface_spoof_score(self, image: np.ndarray) -> float | None:
        """使用 DeepFace 集成的 MiniFASNet 反欺骗模型，返回 [0,1] 真实人脸得分。"""
        if self._deepface is None:
            return None
        try:
            results = self._deepface.extract_faces(
                img_path=image,
                anti_spoofing=True,
                enforce_detection=False,
                silent=True,
            )
            if results and len(results) > 0:
                r = results[0]
                # antispoof_score: MiniFASNet 输出的 spoof 概率，低分 = 真实
                if "antispoof_score" in r:
                    return float(max(0.0, 1.0 - r["antispoof_score"]))
                return 0.9 if r.get("is_real", True) else 0.1
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    #  频域分析
    # ------------------------------------------------------------------

    def _frequency_score(self, gray: np.ndarray) -> float:
        """频域分析：真实人脸频谱能量平滑衰减，翻拍常有规则尖峰。"""
        h, w = gray.shape
        dft = cv2.dft(np.float32(gray), flags=cv2.DFT_COMPLEX_OUTPUT)
        dft_shift = np.fft.fftshift(dft)
        magnitude = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1]) + 1e-6
        mag_log = 20 * np.log(magnitude)

        cy, cx = h // 2, w // 2
        max_r = min(h, w) // 2
        low_r = int(max_r * 0.10)
        mid_r = int(max_r * 0.30)
        high_r = int(max_r * 0.50)

        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt((Y - cy) ** 2 + (X - cx) ** 2)

        low_mask = dist <= low_r
        mid_mask = (dist > low_r) & (dist <= mid_r)
        high_mask = (dist > mid_r) & (dist <= high_r)

        low_energy = float(np.sum(mag_log * low_mask))
        mid_energy = float(np.sum(mag_log * mid_mask))
        high_energy = float(np.sum(mag_log * high_mask))
        total = low_energy + mid_energy + high_energy + 1e-6

        mid_ratio = mid_energy / total
        high_ratio = high_energy / total

        # 真实人脸：中高频占比较为均衡
        score = 0.0
        if 0.25 <= mid_ratio <= 0.55:
            score += 0.5
        if high_ratio >= 0.08:
            score += 0.5
        elif high_ratio >= 0.04:
            score += 0.3

        # 检测尖锐频率峰值（屏幕翻拍常有周期性条纹）
        seg_start = max(low_r, 2)
        seg_end = min(high_r, max_r - 1)
        if seg_end > seg_start:
            # 将 2D 频谱折叠为 1D 径向分布
            rings = 64
            radial = np.zeros(rings)
            for i in range(rings):
                r_min = int(max_r * i / rings)
                r_max = int(max_r * (i + 1) / rings)
                ring = (dist > r_min) & (dist <= r_max)
                if ring.any():
                    radial[i] = float(np.mean(mag_log[ring]))
            segment = radial[seg_start * rings // max_r : seg_end * rings // max_r + 1]
            if len(segment) > 3:
                cv_val = float(np.std(segment)) / (float(np.mean(segment)) + 1e-6)
                if cv_val > 0.3:
                    score *= 0.7
        return min(score, 1.0)

    # ------------------------------------------------------------------
    #  LBP 纹理分析
    # ------------------------------------------------------------------

    @staticmethod
    def _lbp_score(gray: np.ndarray) -> float:
        """LBP 纹理分析：翻拍材料表面存在规则纹理周期，熵较低。"""
        try:
            radius = 2
            n_points = 8 * radius
            lbp = local_binary_pattern(gray, n_points, radius, method="uniform")
            n_bins = n_points + 2
            hist, _ = np.histogram(lbp.ravel(), bins=n_bins, range=(0, n_bins))
            hist = hist.astype(np.float32)
            hist_sum = hist.sum()
            if hist_sum == 0:
                return 0.5
            hist /= hist_sum
            entropy = -float(np.sum(hist * np.log(hist + 1e-6)))
            max_entropy = np.log(n_bins)
            return min(entropy / max_entropy * 1.5, 1.0)
        except Exception:
            return 0.5

    # ------------------------------------------------------------------
    #  色彩多样性分析
    # ------------------------------------------------------------------

    @staticmethod
    def _color_diversity_score(image: np.ndarray) -> float:
        """色彩多样性分析：打印照片色彩饱和度低且均匀，真实人脸肤色有自然变化。"""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        s = hsv[:, :, 1].astype(np.float32)
        s_mean = float(np.mean(s))
        s_std = float(np.std(s))
        mean_score = min(s_mean / 50.0, 1.0) if s_mean > 5 else 0.1
        std_score = min(s_std / 30.0, 1.0)
        return min(0.5 * mean_score + 0.5 * std_score, 1.0)

    # ------------------------------------------------------------------
    #  综合判断
    # ------------------------------------------------------------------

    def analyze(
        self,
        image: np.ndarray,
        face_box: tuple[int, int, int, int] | None = None,
    ) -> tuple[float, float, str]:
        """执行多维度活体检测。

        Returns:
            (score, threshold, message)
            score — [0,1] 综合得分
            threshold — 本次使用的阈值（有/无 DeepFace 不同）
            message — 检测结果描述
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 1. 清晰度（Laplacian 方差）
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(lap_var / 500.0, 1.0)

        # 2. 亮度
        brightness = float(np.mean(gray))
        brightness_score = 1.0 - min(abs(brightness - 120.0) / 130.0, 1.0)

        # 3. 边缘纹理
        edges = cv2.Canny(gray, 80, 160)
        edge_density = float(np.mean(edges > 0))
        texture_score = min(edge_density * 10.0, 1.0)

        # 4. 频域
        freq_score = self._frequency_score(gray)

        # 5. LBP
        lbp_score_val = self._lbp_score(gray)

        # 6. 色彩
        color_score = self._color_diversity_score(image)

        # 7. DeepFace 反欺骗（深度学习）
        deepface_score = self._deepface_spoof_score(image)

        # 8. MiniFASNet-V2 ONNX 反欺骗（live / print / replay）
        minifasnet_scores = self._minifasnet_spoof_scores(image, face_box)
        minifasnet_score = (
            minifasnet_scores[0] if minifasnet_scores is not None else None
        )

        rule_score = (
            0.20 * blur_score
            + 0.10 * brightness_score
            + 0.15 * texture_score
            + 0.25 * freq_score
            + 0.20 * lbp_score_val
            + 0.10 * color_score
        )

        # ── 综合评分 ──
        # MiniFASNet 对不同摄像头、曝光和裁剪很敏感。这里不让单帧模型“一票否决”
        # 真人，而是只有模型极高置信为 spoof 且传统规则也偏低时才强拦截。
        hard_model_fail = False
        model_spoof_prob = 0.0
        if minifasnet_score is not None:
            live_prob, print_prob, replay_prob = minifasnet_scores
            model_spoof_prob = max(print_prob, replay_prob)
            if deepface_score is not None:
                score = (
                    0.35 * minifasnet_score + 0.15 * deepface_score + 0.50 * rule_score
                )
            else:
                score = 0.35 * minifasnet_score + 0.65 * rule_score
            score = max(score, rule_score)
            threshold = 0.40
            hard_model_fail = (
                minifasnet_score < 0.08
                and model_spoof_prob > 0.92
                and rule_score < 0.35
            )
        elif deepface_score is not None:
            score = (
                0.03 * blur_score
                + 0.03 * brightness_score
                + 0.03 * texture_score
                + 0.07 * freq_score
                + 0.10 * lbp_score_val
                + 0.04 * color_score
                + 0.70 * deepface_score
            )
            threshold = 0.55
        else:
            score = rule_score
            threshold = 0.45

        score = float(round(float(score), 3))

        if score < threshold or hard_model_fail:
            detail = []
            if lap_var < 30:
                detail.append("画面模糊")
            if brightness < 30 or brightness > 220:
                detail.append("光照异常")
            if edge_density < 0.008:
                detail.append("缺乏纹理")
            if minifasnet_scores is not None:
                live_prob, print_prob, replay_prob = minifasnet_scores
                if hard_model_fail and replay_prob >= 0.80 and replay_prob >= print_prob:
                    detail.append("疑似视频重放")
                elif hard_model_fail and print_prob >= 0.80:
                    detail.append("疑似照片/屏幕翻拍")
                elif live_prob < 0.15 and model_spoof_prob > 0.90:
                    detail.append("疑似伪造人脸")
            if deepface_score is not None and deepface_score < 0.30:
                detail.append("疑似照片/屏幕翻拍")
            msg = f"活体检测失败：{'、'.join(detail) or f'综合得分过低（{score}）'}"
            return score, threshold, msg

        return score, threshold, "活体检测通过"

    # ------------------------------------------------------------------
    #  动作验证（配合挑战动作强制执行）
    # ------------------------------------------------------------------

    def action_metrics(self, image: np.ndarray, face_row: np.ndarray) -> dict[str, float]:
        """提取动作验证用的连续指标，供有状态挑战判断“从基线到动作”的变化。"""
        x, w = float(face_row[0]), float(face_row[2])
        n_x = float(face_row[8])
        nose_ratio = (n_x - x) / float(w or 1)
        return {
            "nose_ratio": nose_ratio,
            "mouth_open": self._mouth_open_score(image, face_row),
            "smile": self._smile_score(image, face_row),
        }

    def verify_action(
        self, image: np.ndarray, action: str, face_row: np.ndarray
    ) -> tuple[bool, str]:
        """验证用户是否完成了指定挑战动作。

        Args:
            image: BGR 图像。
            action: 挑战动作代码（smile/turn_left/turn_right/open_mouth）。
            face_row: YuNet 返回的 15 维人脸行，包含 5 个面部关键点。

        Returns:
            (passed, failure_message) — passed=True 表示动作验证通过。
        """
        if action in ("", "none", "blink"):
            return True, ""

        x, y, w, h = (
            float(face_row[0]),
            float(face_row[1]),
            float(face_row[2]),
            float(face_row[3]),
        )
        n_x, n_y = float(face_row[8]), float(face_row[9])
        rc_x, rc_y = float(face_row[10]), float(face_row[11])
        lc_x, lc_y = float(face_row[12]), float(face_row[13])

        if action in ("turn_head", "turn_left", "turn_right"):
            # 向左转：鼻尖右移 | 向右转：鼻尖左移
            turned_left = n_x > x + 0.55 * w
            turned_right = n_x < x + 0.45 * w
            if turned_left or turned_right:
                return True, ""
            return False, "请左右转头"

        if action == "open_mouth":
            return self._check_mouth_open(image, face_row)

        if action == "smile":
            return self._check_smile(image, face_row)

        return False, f"未知动作：{action}"

    def _mouth_roi(self, image: np.ndarray, face_row: np.ndarray) -> np.ndarray | None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        ih, iw = gray.shape

        n_y = int(face_row[9])
        rc_x, rc_y = int(face_row[10]), int(face_row[11])
        lc_x, lc_y = int(face_row[12]), int(face_row[13])
        face_h = int(face_row[3])
        face_w = int(face_row[2])

        # 根据关键点划定嘴部 ROI，附加 15% 上下、10% 左右的 padding
        mouth_top = max(n_y, 0)
        mouth_bottom = min(max(rc_y, lc_y) + int(face_h * 0.15), ih)
        mouth_left = max(min(lc_x, rc_x) - int(face_w * 0.10), 0)
        mouth_right = min(max(lc_x, rc_x) + int(face_w * 0.10), iw)

        if mouth_bottom <= mouth_top or mouth_right <= mouth_left:
            return None

        mouth_roi = gray[mouth_top:mouth_bottom, mouth_left:mouth_right]
        if mouth_roi.size == 0:
            return None
        return mouth_roi

    def _smile_score(self, image: np.ndarray, face_row: np.ndarray) -> float:
        """微笑检测得分：Haar 检出时为 1，否则为 0。"""
        mouth_roi = self._mouth_roi(image, face_row)
        if mouth_roi is None:
            return 0.0

        smiles = self.smile_cascade.detectMultiScale(
            mouth_roi, scaleFactor=1.5, minNeighbors=8, minSize=(20, 20)
        )
        return 1.0 if len(smiles) > 0 else 0.0

    def _check_smile(self, image: np.ndarray, face_row: np.ndarray) -> tuple[bool, str]:
        """使用 Haar smile 级联分类器在嘴部 ROI 检测微笑。"""
        if self._mouth_roi(image, face_row) is None:
            return False, "无法定位嘴部区域"
        if self._smile_score(image, face_row) >= 1.0:
            return True, ""
        return False, "请微笑"

    def _mouth_open_score(self, image: np.ndarray, face_row: np.ndarray) -> float:
        """张嘴连续得分：结合口腔暗区和边缘密度，范围约为 0~1。"""
        mouth_roi = self._mouth_roi(image, face_row)
        if mouth_roi is None:
            return 0.0

        h, w = mouth_roi.shape
        dark_score = 0.0
        if w >= 6:
            left = float(np.mean(mouth_roi[:, : w // 3]))
            center = float(np.mean(mouth_roi[:, w // 3 : 2 * w // 3]))
            right = float(np.mean(mouth_roi[:, 2 * w // 3 :]))
            side_mean = max((left + right) / 2.0, 1.0)
            contrast = max((side_mean - center) / side_mean, 0.0)
            dark_score = min(contrast / 0.20, 1.0)

        edges = cv2.Canny(mouth_roi, 50, 150)
        edge_density = float(np.mean(edges > 0))
        edge_score = min(edge_density / 0.18, 1.0)
        return max(dark_score, edge_score)

    def _check_mouth_open(
        self, image: np.ndarray, face_row: np.ndarray
    ) -> tuple[bool, str]:
        """张嘴检测：基于嘴部 ROI 中间 vs 两侧的灰度反差判断。
        张嘴时口腔内部比嘴唇/皮肤暗很多 → 中间区域显著暗于两侧。
        相对比较，对光照不敏感。
        """
        if self._mouth_roi(image, face_row) is None:
            return False, "无法定位嘴部区域"
        if self._mouth_open_score(image, face_row) >= 0.55:
            return True, ""

        return False, "请张嘴"


liveness_service = LivenessService()
