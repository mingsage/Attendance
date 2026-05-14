from io import BytesIO
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/pjpeg",
                 "image/webp", "image/avif", "image/bmp", "image/tiff"}
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp", ".tiff"}

MAX_SIZE = 1000 * 1024 * 1024  # 1000MB for group photos


async def read_image(file: UploadFile, max_size: int = 10 * 1024 * 1024) -> np.ndarray:
    """读取上传图片并解码为 OpenCV BGR 矩阵。

    支持 JPEG/PNG/WebP/AVIF/BMP/TIFF，非 JPEG/PNG 格式通过 Pillow 转为 PNG 后解码。
    """
    suffix = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED_TYPES and suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"不支持图片格式：{suffix}")
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"图片大小不能超过 {max_size // 1024 // 1024}MB")
    image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    if image is not None:
        return image
    # OpenCV 解码失败（如 WebP/AVIF）→ Pillow 兜底
    try:
        pil_img = Image.open(BytesIO(content)).convert("RGB")
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)
        image = cv2.imdecode(np.frombuffer(buf.read(), np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        raise HTTPException(status_code=400, detail="图片解码失败，请使用 jpg/png/webp/avif 格式")
    if image is None:
        raise HTTPException(status_code=400, detail="图片解码失败")
    return image


async def save_upload(file: UploadFile, target_dir: Path) -> str:
    """保存上传文件，返回相对路径，避免暴露临时文件名。"""

    suffix = Path(file.filename or "upload.jpg").suffix.lower() or ".jpg"
    filename = f"{uuid4().hex}{suffix}"
    path = target_dir / filename
    content = await file.read()
    path.write_bytes(content)
    return str(path)
