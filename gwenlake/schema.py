
from pydantic import BaseModel, Field
from typing import Optional, Union
from uuid import uuid4


class Message(BaseModel):
    role: str
    content: str

class Choice(BaseModel):
    index: Optional[int] = 0 
    message: Message
    finish_reason: Optional[str] = "stop"

class ChoiceDelta(BaseModel):
    index: Optional[int] = 0 
    delta: Message
    finish_reason: Optional[str] = None

class ChatCompletion(BaseModel):
    id: str = Field(default_factory=lambda: "chatcmpl-" + str(uuid4()))
    object: str = "chat.completion"
    choices: list[ Union[Choice, ChoiceDelta] ]
