
from pydantic import BaseModel, Field
from typing import Optional, Union
from uuid import uuid4
from datetime import datetime

class Message(BaseModel):
    role: str
    content: Optional[str] = None

class Choice(BaseModel):
    index: Optional[int] = 0 
    message: Message
    finish_reason: Optional[str] = "stop"

class ChoiceDelta(BaseModel):
    index: Optional[int] = 0 
    delta: Message
    finish_reason: Optional[str] = None

class Usage(BaseModel):
    prompt_tokens: Optional[int] = 0
    completion_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0

class ChatCompletion(BaseModel):
    id: str = Field(default_factory=lambda: "chatcmpl-" + str(uuid4()))
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(round(datetime.now().timestamp())))
    model: Optional[str] = None
    system_fingerprint: Optional[str] = None
    choices: list[Choice]
    usage: Optional[Usage] = None

class ChatCompletionChunk(BaseModel):
    id: str = Field(default_factory=lambda: "chatcmpl-" + str(uuid4()))
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(round(datetime.now().timestamp())))
    model: Optional[str] = None
    system_fingerprint: Optional[str] = None
    choices: list[ChoiceDelta]
