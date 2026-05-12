import os

# 必须在任何 Keras/DeepFace 导入前设置后端
os.environ["KERAS_BACKEND"] = "tensorflow"

import cv2
import numpy as np
from skimage.feature import local_binary_pattern


class LivenessService:
    """综合活体检测：融合传统图像特征与 DeepFace 深度学习反欺骗。

    多维度检测：
    - MiniFASNet 反欺骗模型（DeepFace 提供的深度学习反欺骗）
    - 频域 FFT 分析：真实人脸具有自然的 1/f 频谱衰减
    - LBP 纹理分析：翻拍照片／屏幕呈现周期性重复纹理
    - 色彩多样性：打印照片色彩饱和度不足且缺乏变化
    - 清晰度 / 亮度 / 边缘密度：基础图像质量快速过滤
    """

    def __init__(self) -> None:
        self._deepface = None
        try:
            from deepface import DeepFace

            self._deepface = DeepFace
        except ImportError:
            pass

    # ------------------------------------------------------------------
    #  深度学习反欺骗
    # ------------------------------------------------------------------

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

    def analyze(self, image: np.ndarray) -> tuple[float, str]:
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

        # ── 综合评分 ──
        if deepface_score is not None:
            score = (
                0.05 * blur_score
                + 0.04 * brightness_score
                + 0.04 * texture_score
                + 0.10 * freq_score
                + 0.14 * lbp_score_val
                + 0.07 * color_score
                + 0.56 * deepface_score
            )
            threshold = 0.38
        else:
            score = (
                0.20 * blur_score
                + 0.10 * brightness_score
                + 0.15 * texture_score
                + 0.25 * freq_score
                + 0.20 * lbp_score_val
                + 0.10 * color_score
            )
            threshold = 0.30

        score = round(score, 3)

        if score < threshold:
            detail = []
            if lap_var < 30:
                detail.append("画面模糊")
            if brightness < 30 or brightness > 220:
                detail.append("光照异常")
            if edge_density < 0.02:
                detail.append("缺乏纹理")
            if deepface_score is not None and deepface_score < 0.30:
                detail.append("疑似照片/屏幕翻拍")
            msg = f"活体检测失败：{'、'.join(detail) or f'综合得分过低（{score}）'}"
            return score, msg

        return score, "活体检测通过"


liveness_service = LivenessService()
