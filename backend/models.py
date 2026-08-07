import time
import uuid
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class CitizenSubmission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["shikoyat", "murojaat", "taklif"] # Shikoyat, Murojaat, Taklif
    full_name: str
    phone: str
    mahalla: str
    address: Optional[str] = ""
    topic: str
    description: str
    status: str = "Yangi" # Yangi, Ko'rib chiqilmoqda, Hal etildi
    timestamp: float = Field(default_factory=time.time)

class KnowledgeDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    category: str # "shahar", "mahalla", "xizmatlar", "umumiy"
    content: str
    created_at: float = Field(default_factory=time.time)

class ChatMessage(BaseModel):
    sender: Literal["user", "assistant"]
    text: str
    timestamp: float = Field(default_factory=time.time)
