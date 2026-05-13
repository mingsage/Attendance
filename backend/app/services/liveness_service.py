import os

os.environ["KERAS_BACKEND"] = "tensorflow"

import cv2
import numpy as np
from skimage.feature import local_binary_pattern


# ═══════════════════════════════════════════════════════════════
#  rPPG 脉搏波检测器
# ═══════════════════════════════════════════════════════════════

class rPPGDetector:
    """远程光电容积脉搏波：从连续帧面部 ROI 绿色通道中提取心率信号。

    原理：心跳 → 毛细血管血量周期性变化 → 皮肤反射率微变
    → 摄像头绿色通道像素均值波动 → FFT 提取 0.7-3.0 Hz 信号。
    照片/屏幕翻拍无法模拟此生物节律。
    """

    def __init__(self) -> None:
        self.signal_buffer: list[float] = []
        self.buffer_size = 90   # ~3 秒 × 30fps
        self.fs = 30.0
        self.low_freq = 0.7    # ≈42 bpm
        self.high_freq = 3.0   # ≈180 bpm

    def add_frame(self, face_roi: np.ndarray) -> None:
        g = face_roi[:, :, 1].astype(np.float32)  # BGR → G 通道
        self.signal_buffer.append(float(np.mean(g)))
        if len(self.signal_buffer) > self.buffer_size:
            self.signal_buffer.pop(0)

    def compute(self) -> tuple[float, str]:
        if len(self.signal_buffer) < 30:
            return 0.5, "rPPG 采样不足"
        signal = np.array(self.signal_buffer, dtype=np.float32)
        signal = signal - np.mean(signal)
        # 去线性趋势
        t = np.arange(len(signal))
        slope, intercept = np.polyfit(t, signal, 1)
        signal = signal - (slope * t + intercept)
        # FFT
        n = len(signal)
        fft = np.abs(np.fft.rfft(signal))
        freqs = np.fft.rfftfreq(n, 1.0 / self.fs)
        mask = (freqs >= self.low_freq) & (freqs <= self.high_freq)
        if not mask.any():
            return 0.0, "rPPG 无心率频段信号"
        band = fft[mask]
        noise = fft[~mask] if (~mask).any() else np.array([1.0])
        peak_idx = int(np.argmax(band))
        peak_freq = freqs[mask][peak_idx]
        peak_ratio = band[peak_idx] / (float(np.mean(noise)) + 1e-6)
        if peak_ratio > 3.0:
            return min(peak_ratio / 8.0, 1.0), f"rPPG 脉搏 {peak_freq * 60:.0f} bpm"
        if peak_ratio > 1.5:
            return 0.3, "rPPG 信号较弱"
        return 0.0, "rPPG 未检测到脉搏"


# ═══════════════════════════════════════════════════════════════
#  摩尔纹专项检测器
# ═══════════════════════════════════════════════════════════════

class MoireDetector:
    """专门检测翻拍电子屏幕时摄像头与屏幕像素叠加产生的莫尔纹。

    与通用 FFT 不同：本检测器搜索频谱中的局部异常尖峰
    （特定方向的周期性干涉条纹），而非径向能量分布。
    """

    def detect(self, gray: np.ndarray) -> tuple[float, str]:
        h, w = gray.shape
        fft = np.fft.fft2(gray.astype(np.float32))
        fft_shift = np.fft.fftshift(fft)
        magnitude = np.abs(fft_shift) + 1e-6
        cy, cx = h // 2, w // 2
        max_r = min(h, w) // 2
        mid_start = int(max_r * 0.15)
        mid_end = int(max_r * 0.60)
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt((Y - cy) ** 2 + (X - cx) ** 2)
        mask = (dist >= mid_start) & (dist <= mid_end)
        masked = magnitude * mask
        mean_val = float(np.mean(masked[mask])) if mask.any() else 0.0
        std_val = float(np.std(masked[mask])) if mean_val > 0 else 1.0
        peak_mask = (masked > mean_val + 4 * std_val) & mask
        peak_count = int(np.sum(peak_mask))
        if peak_count > 50:
            return 0.0, f"摩尔纹峰值 {peak_count}，疑似屏幕翻拍"
        if peak_count > 10:
            return 0.3, f"异常频率峰值 {peak_count}"
        return 1.0, "无摩尔纹"


# ═══════════════════════════════════════════════════════════════
#  时序一致性分析器
# ═══════════════════════════════════════════════════════════════

class TemporalConsistency:
    """多帧运动一致性分析。

    手持照片晃动 → 全脸刚体平移（器官无相对运动）。
    真人自然晃动 → 面部器官（眼、嘴）有独立微运动。
    """

    def __init__(self) -> None:
        self.prev_gray: np.ndarray | None = None
        self.prev_kps: np.ndarray | None = None

    def reset(self) -> None:
        self.prev_gray = None
        self.prev_kps = None

    def update(
        self, gray: np.ndarray, kps: np.ndarray | None
    ) -> tuple[float, str]:
        if self.prev_gray is None:
            self.prev_gray = gray.copy()
            self.prev_kps = kps.copy() if kps is not None else None
            return 0.5, "时序初始化"

        # 稠密光流
        flow = cv2.calcOpticalFlowFarneback(
            self.prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        h, w = gray.shape
        cy, cx = h // 2, w // 2
        r = min(h, w) // 4
        y1, y2 = max(0, cy - r), min(h, cy + r)
        x1, x2 = max(0, cx - r), min(w, cx + r)
        center_flow = flow[y1:y2, x1:x2]
        center_std = float(np.std(center_flow))

        # 关键点相对位移分散度
        kp_dispersion = 0.0
        if self.prev_kps is not None and kps is not None:
            if kps.shape[0] >= 5 and self.prev_kps.shape[0] >= 5:
                shifts = np.linalg.norm(
                    kps[:5].astype(np.float32)
                    - self.prev_kps[:5].astype(np.float32),
                    axis=1,
                )
                kp_dispersion = float(np.std(shifts))

        self.prev_gray = gray.copy()
        self.prev_kps = kps.copy() if kps is not None else None

        score = 0.5
        if center_std > 1.5:
            score += 0.3
        if kp_dispersion > 0.8:
            score += 0.2
        elif kp_dispersion < 0.2 and center_std < 0.5:
            score = 0.1

        if score < 0.3:
            return score, "面部运动异常一致，疑似照片晃动"
        return min(score, 1.0), "时序一致性正常"


# ═══════════════════════════════════════════════════════════════
#  活体检测主服务
# ═══════════════════════════════════════════════════════════════

class LivenessService:
    """11 维综合活体检测。

    维度组成：
      — DeepFace MiniFASNet（深度学习反欺骗）      40%
      — rPPG 脉搏波检测                             15%
      — 光流时序一致性分析                           12%
      — 摩尔纹专项检测                               10%
      — FFT 频域分析（通用频谱衰减）                  5%
      — LBP 纹理分析                                 5%
      — 色彩多样性分析                                3%
      — 清晰度（Laplacian）                           2%
      — 亮度                                         2%
      — 边缘纹理（Canny）                             2%
      — 动态阈值（根据光照/清晰度自动调整判定线）       —

    rPPG 一票否决规则：rPPG 得分 < 0.15 → 直接判为欺骗。
    """

    BASE_THRESHOLD = 0.55

    def __init__(self) -> None:
        self._deepface = None
        try:
            from deepface import DeepFace
            self._deepface = DeepFace
        except ImportError:
            pass

        self.rppg = rPPGDetector()
        self.moire = MoireDetector()
        self.temporal = TemporalConsistency()
        self._smile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_smile.xml"
        )

    # ── DeepFace 反欺骗 ─────────────────────────────────────

    def _deepface_spoof_score(self, image: np.ndarray) -> float | None:
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
                if "antispoof_score" in r:
                    return float(max(0.0, 1.0 - r["antispoof_score"]))
                return 0.9 if r.get("is_real", True) else 0.1
        except Exception:
            pass
        return None

    # ── 传统 CV 维度 ────────────────────────────────────────

    @staticmethod
    def _blur_score(gray: np.ndarray) -> float:
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return min(lap_var / 500.0, 1.0)

    @staticmethod
    def _brightness_val(gray: np.ndarray) -> float:
        return float(np.mean(gray))

    @staticmethod
    def _brightness_score(brightness: float) -> float:
        return 1.0 - min(abs(brightness - 120.0) / 130.0, 1.0)

    @staticmethod
    def _texture_score(gray: np.ndarray) -> float:
        edges = cv2.Canny(gray, 80, 160)
        return min(float(np.mean(edges > 0)) * 10.0, 1.0)

    def _frequency_score(self, gray: np.ndarray) -> float:
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
        low_energy = float(np.sum(mag_log * (dist <= low_r)))
        mid_energy = float(
            np.sum(mag_log * ((dist > low_r) & (dist <= mid_r)))
        )
        high_energy = float(
            np.sum(mag_log * ((dist > mid_r) & (dist <= high_r)))
        )
        total = low_energy + mid_energy + high_energy + 1e-6
        mid_ratio = mid_energy / total
        high_ratio = high_energy / total
        score = 0.0
        if 0.25 <= mid_ratio <= 0.55:
            score += 0.5
        if high_ratio >= 0.08:
            score += 0.5
        elif high_ratio >= 0.04:
            score += 0.3
        # 检测尖锐频率峰值
        seg_start = max(low_r, 2)
        seg_end = min(high_r, max_r - 1)
        if seg_end > seg_start:
            rings = 64
            radial = np.zeros(rings)
            for i in range(rings):
                r_min = int(max_r * i / rings)
                r_max = int(max_r * (i + 1) / rings)
                ring = (dist > r_min) & (dist <= r_max)
                if ring.any():
                    radial[i] = float(np.mean(mag_log[ring]))
            seg_slice = radial[
                seg_start * rings // max_r : seg_end * rings // max_r + 1
            ]
            if len(seg_slice) > 3:
                cv_val = float(np.std(seg_slice)) / (
                    float(np.mean(seg_slice)) + 1e-6
                )
                if cv_val > 0.3:
                    score *= 0.7
        return min(score, 1.0)

    @staticmethod
    def _lbp_score(gray: np.ndarray) -> float:
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
            return min(entropy / np.log(n_bins) * 1.5, 1.0)
        except Exception:
            return 0.5

    @staticmethod
    def _color_diversity_score(image: np.ndarray) -> float:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        s = hsv[:, :, 1].astype(np.float32)
        s_mean = float(np.mean(s))
        s_std = float(np.std(s))
        mean_score = min(s_mean / 50.0, 1.0) if s_mean > 5 else 0.1
        std_score = min(s_std / 30.0, 1.0)
        return min(0.5 * mean_score + 0.5 * std_score, 1.0)

    # ── 动态阈值 ────────────────────────────────────────────

    @staticmethod
    def _dynamic_threshold(
        base: float, brightness: float, blur_score: float
    ) -> float:
        brightness_error = abs(brightness - 120.0) / 120.0
        blur_penalty = max(0.0, 1.0 - blur_score)
        if brightness < 40 or brightness > 200:
            alpha = 0.15
        else:
            alpha = 0.08
        beta = 0.05
        adjusted = base + alpha * brightness_error + beta * blur_penalty
        return min(adjusted, 0.75)

    # ── 动作验证 ────────────────────────────────────────────

    def verify_action(
        self,
        image: np.ndarray,
        action: str,
        face_box: tuple[int, int, int, int],
        keypoints: np.ndarray | None = None,
    ) -> tuple[bool, str]:
        """验证用户是否完成指定活体动作。

        keypoints: InsightFace kps (5,2) 格式，为 None 时回退到 Haar。
        """
        if action == "smile":
            return self._verify_smile(image, face_box)
        if action in ("turn_left", "turn_right"):
            return self._verify_head_turn(image, face_box, action, keypoints)
        if action == "open_mouth":
            return self._verify_mouth_open(image, face_box, keypoints)
        return True, ""

    def _verify_smile(
        self, image: np.ndarray, box: tuple[int, int, int, int]
    ) -> tuple[bool, str]:
        x, y, w, h = box
        mouth_roi = image[
            y + int(h * 0.65) : y + h, x + int(w * 0.2) : x + int(w * 0.8)
        ]
        if mouth_roi.size == 0:
            return False, "未完成指定动作：请微笑后完成考勤"
        gray = cv2.cvtColor(mouth_roi, cv2.COLOR_BGR2GRAY)
        smiles = self._smile_cascade.detectMultiScale(
            gray, scaleFactor=1.3, minNeighbors=10, minSize=(18, 10)
        )
        if len(smiles) > 0:
            return True, ""
        return False, "未完成指定动作：请微笑后完成考勤"

    @staticmethod
    def _verify_head_turn(
        image: np.ndarray,
        box: tuple[int, int, int, int],
        action: str,
        keypoints: np.ndarray | None,
    ) -> tuple[bool, str]:
        action_text = "向左转头" if action == "turn_left" else "向右转头"
        x, y, w, h = box

        if keypoints is not None and keypoints.shape[0] >= 3:
            # InsightFace kps: [右眼, 左眼, 鼻尖, 右嘴角, 左嘴角]
            nose_x = float(keypoints[2, 0])
            left_eye_x = float(keypoints[0, 0])
            right_eye_x = float(keypoints[1, 0])
            eye_center_x = (left_eye_x + right_eye_x) / 2.0
            face_center_x = x + w / 2.0
            nose_offset = nose_x - eye_center_x
            norm_offset = nose_offset / (w + 1e-6)
            if action == "turn_left" and norm_offset > 0.08:
                return True, ""
            if action == "turn_right" and norm_offset < -0.08:
                return True, ""
            return False, f"未完成指定动作：请{action_text}后完成考勤"

        # 回退：鼻尖 x 相对脸框位置
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        nose_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_mcs_nose.xml"
        )
        face_roi = gray[y : y + h, x : x + w]
        noses = nose_cascade.detectMultiScale(
            face_roi, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20)
        )
        if len(noses) == 0:
            return False, f"未完成指定动作：请{action_text}后完成考勤"
        nx_rel = (noses[0][0] + noses[0][2] / 2) / w
        if action == "turn_left" and nx_rel > 0.55:
            return True, ""
        if action == "turn_right" and nx_rel < 0.45:
            return True, ""
        return False, f"未完成指定动作：请{action_text}后完成考勤"

    @staticmethod
    def _verify_mouth_open(
        image: np.ndarray,
        box: tuple[int, int, int, int],
        keypoints: np.ndarray | None,
    ) -> tuple[bool, str]:
        x, y, w, h = box

        if keypoints is not None and keypoints.shape[0] >= 5:
            # 嘴角关键点索引: 3=右嘴角, 4=左嘴角
            mouth_left = keypoints[3]
            mouth_right = keypoints[4]
            mouth_width = float(np.linalg.norm(mouth_right - mouth_left))
            mouth_center_y = float((mouth_left[1] + mouth_right[1]) / 2.0)
            nose_y = float(keypoints[2, 1])
            mouth_nose_dist = mouth_center_y - nose_y
            ratio = mouth_nose_dist / (mouth_width + 1e-6)
            if ratio > 0.55:
                return True, ""
            return False, "未完成指定动作：请张嘴后完成考勤"

        # 回退：嘴部区域亮度/面积判断
        mouth_roi = image[
            y + int(h * 0.6) : y + h, x + int(w * 0.2) : x + int(w * 0.8)
        ]
        if mouth_roi.size == 0:
            return False, "未完成指定动作：请张嘴后完成考勤"
        gray_mouth = cv2.cvtColor(mouth_roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_mouth, 40, 255, cv2.THRESH_BINARY_INV)
        dark_ratio = float(np.mean(thresh > 0))
        if dark_ratio > 0.25:
            return True, ""
        return False, "未完成指定动作：请张嘴后完成考勤"

    # ── 综合评分主入口 ──────────────────────────────────────

    def analyze(
        self,
        image: np.ndarray,
        face_box: tuple[int, int, int, int] | None = None,
        keypoints: np.ndarray | None = None,
    ) -> tuple[float, str]:
        """11 维综合活体评分。

        Parameters
        ----------
        image : 当前帧 BGR 图像
        face_box : 人脸边界框，用于裁剪面部 ROI 给 rPPG/时序分析
        keypoints : InsightFace 5 关键点，用于时序一致性分析
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # ── 基础维度 ──
        blur_s = self._blur_score(gray)
        brightness = self._brightness_val(gray)
        brightness_s = self._brightness_score(brightness)
        texture_s = self._texture_score(gray)
        freq_s = self._frequency_score(gray)
        lbp_s = self._lbp_score(gray)
        color_s = self._color_diversity_score(image)
        deepface_s = self._deepface_spoof_score(image)

        # ── 新增维度：从当前帧提取面部 ROI ──
        if face_box is not None:
            x, y, w, h = face_box
            face_roi = image[max(0, y) : y + h, max(0, x) : x + w]
            face_roi_gray = gray[max(0, y) : y + h, max(0, x) : x + w]
        else:
            face_roi = image
            face_roi_gray = gray

        # rPPG：累积信号并评分
        self.rppg.add_frame(face_roi)
        rppg_s, rppg_msg = self.rppg.compute()

        # 摩尔纹
        moire_s, moire_msg = self.moire.detect(face_roi_gray)

        # 时序一致性
        temporal_s, temporal_msg = self.temporal.update(face_roi_gray, keypoints)

        # ── 加权融合 ──
        if deepface_s is not None:
            score = (
                0.40 * deepface_s
                + 0.15 * rppg_s
                + 0.12 * temporal_s
                + 0.10 * moire_s
                + 0.05 * freq_s
                + 0.05 * lbp_s
                + 0.03 * color_s
                + 0.02 * blur_s
                + 0.02 * brightness_s
                + 0.02 * texture_s
            )
        else:
            total_w = 0.56  # 不含 DeepFace 的权重和
            score = (
                0.15 * rppg_s
                + 0.12 * temporal_s
                + 0.10 * moire_s
                + 0.05 * freq_s
                + 0.05 * lbp_s
                + 0.03 * color_s
                + 0.02 * blur_s
                + 0.02 * brightness_s
                + 0.02 * texture_s
            ) / total_w

        score = round(score, 3)

        # rPPG 一票否决
        if rppg_s < 0.15:
            return score, "活体检测失败：未检测到脉搏信号，疑似照片/屏幕"

        # 动态阈值
        threshold = self._dynamic_threshold(self.BASE_THRESHOLD, brightness, blur_s)

        if score < threshold:
            if deepface_s is not None and deepface_s < 0.30:
                return score, "活体检测失败：疑似照片/屏幕翻拍"
            if moire_s < 0.15:
                return score, f"活体检测失败：{moire_msg}"
            if rppg_s < 0.25:
                return score, f"活体检测失败：{rppg_msg}"
            return score, f"活体检测失败：综合得分 {score} 低于阈值 {threshold}"
        return score, "活体检测通过"


liveness_service = LivenessService()
