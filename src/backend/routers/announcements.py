"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreate(BaseModel):
    title: str
    message: str
    start_date: Optional[str] = None  # ISO date string YYYY-MM-DD, optional
    expiration_date: str              # ISO date string YYYY-MM-DD, required


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None


def _serialize(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


def _require_teacher(username: str) -> dict:
    """Verify teacher exists; raise 401 if not."""
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    return teacher


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Return all currently active announcements (public)."""
    today = datetime.now(timezone.utc).date().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": today}},
        ],
    }
    return [_serialize(doc) for doc in announcements_collection.find(query).sort("expiration_date", 1)]


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(username: str) -> List[Dict[str, Any]]:
    """Return ALL announcements including expired ones (teachers only)."""
    _require_teacher(username)
    return [_serialize(doc) for doc in announcements_collection.find().sort("expiration_date", 1)]


@router.post("", response_model=Dict[str, Any])
def create_announcement(announcement: AnnouncementCreate, username: str) -> Dict[str, Any]:
    """Create a new announcement (teachers only)."""
    _require_teacher(username)

    doc = {
        "title": announcement.title.strip(),
        "message": announcement.message.strip(),
        "start_date": announcement.start_date or None,
        "expiration_date": announcement.expiration_date,
        "created_by": username,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = announcements_collection.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(announcement_id: str, update: AnnouncementUpdate, username: str) -> Dict[str, Any]:
    """Update an existing announcement (teachers only)."""
    _require_teacher(username)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    existing = announcements_collection.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")

    changes: Dict[str, Any] = {}
    if update.title is not None:
        changes["title"] = update.title.strip()
    if update.message is not None:
        changes["message"] = update.message.strip()
    if update.start_date is not None:
        changes["start_date"] = update.start_date if update.start_date else None
    if update.expiration_date is not None:
        changes["expiration_date"] = update.expiration_date

    if changes:
        announcements_collection.update_one({"_id": oid}, {"$set": changes})

    updated = announcements_collection.find_one({"_id": oid})
    return _serialize(updated)


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, username: str) -> Dict[str, Any]:
    """Delete an announcement (teachers only)."""
    _require_teacher(username)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
