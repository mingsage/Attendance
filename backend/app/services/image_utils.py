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


async def read_image(file: UploadFile) -> np.ndarray:
    """读取上传图片并解码为 OpenCV BGR 矩阵。

    接受 jpg/png/webp/avif/bmp/tiff 格式，非 jpg/png 格式通过 Pillow 转为 PNG 后解码。
    """

    suffix = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED_TYPES and suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/webp/avif/bmp/tiff 图片")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")

    image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    if image is not None:
        return image

    # OpenCV 解码失败 → Pillow 转为 PNG 兜底
    try:
        pil_img = Image.open(BytesIO(content)).convert("RGB")
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)
        image = cv2.imdecode(np.frombuffer(buf.read(), np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        raise HTTPException(status_code=400, detail="图片解码失败，请上传有效的图片文件")
    if image is None:
        raise HTTPException(status_code=400, detail="图片解码失败，请上传有效的图片文件")
    return image


async def save_upload(file: UploadFile, target_dir: Path) -> str:
    """保存上传文件，返回相对路径，避免暴露临时文件名。"""

    suffix = Path(file.filename or "upload.jpg").suffix.lower() or ".jpg"
    filename = f"{uuid4().hex}{suffix}"
    path = target_dir / filename
    content = await file.read()
    path.write_bytes(content)
    return str(path)
