
from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4


class Message(BaseModel):
    role: str
    content: str

class ChatCompletion(BaseModel):
    id: str = Field(default_factory=lambda: "chatcmpl-" + str(uuid4()))
    object: str = "chat.completion"
    message: Message
