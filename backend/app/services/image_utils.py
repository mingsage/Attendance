from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/pjpeg"}
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}


async def read_image(file: UploadFile) -> np.ndarray:
    """读取上传图片并解码为 OpenCV BGR 矩阵。"""

    suffix = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED_TYPES and suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png 图片")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")
    image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
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
