import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..core.audit import write_audit
from ..core.deps import get_current_user
from ..db import get_db
from ..models import UploadedFile, User

router = APIRouter(prefix="/files", tags=["files"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@router.post("", status_code=201)
def upload(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "نوع فایل مجاز نیست (تصویر یا PDF)")
    data = file.file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"حداکثر حجم فایل {settings.max_upload_mb} مگابایت است")
    os.makedirs(settings.upload_dir, exist_ok=True)
    fid = uuid.uuid4()
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}.get(
        file.content_type, "")
    path = os.path.join(settings.upload_dir, f"{fid}{ext}")
    with open(path, "wb") as f:
        f.write(data)
    rec = UploadedFile(id=fid, filename=file.filename or "file", content_type=file.content_type,
                       size_bytes=len(data), storage_path=path, uploaded_by=user.id)
    db.add(rec)
    db.commit()
    return {"id": str(fid), "filename": rec.filename, "content_type": rec.content_type,
            "url": f"/api/v1/files/{fid}"}


@router.get("/{file_id}")
def download(file_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rec = db.get(UploadedFile, file_id)
    if rec is None or not os.path.exists(rec.storage_path):
        raise HTTPException(404, "فایل یافت نشد")
    return FileResponse(rec.storage_path, media_type=rec.content_type, filename=rec.filename)
