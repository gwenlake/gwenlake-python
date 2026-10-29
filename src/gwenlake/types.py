"""Typed answers of the inference APIs, as plain dataclasses."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional
from uuid import uuid4


def _chat_id() -> str:
    return "chatcmpl-" + str(uuid4())


def _now() -> int:
    return int(round(datetime.now().timestamp()))


@dataclass
class ChatMessage:
    role: str
    content: Optional[str] = None


@dataclass
class Choice:
    message: ChatMessage
    index: Optional[int] = 0
    finish_reason: Optional[str] = "stop"


@dataclass
class ChoiceDelta:
    delta: ChatMessage
    index: Optional[int] = 0
    finish_reason: Optional[str] = None


@dataclass
class Usage:
    prompt_tokens: Optional[int] = 0
    completion_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0


@dataclass
class ChatCompletion:
    choices: List[Choice]
    id: str = field(default_factory=_chat_id)
    object: str = "chat.completion"
    created: int = field(default_factory=_now)
    model: Optional[str] = None
    system_fingerprint: Optional[str] = None
    usage: Optional[Usage] = None


@dataclass
class ChatCompletionChunk:
    choices: List[ChoiceDelta]
    id: str = field(default_factory=_chat_id)
    object: str = "chat.completion.chunk"
    created: int = field(default_factory=_now)
    model: Optional[str] = None
    system_fingerprint: Optional[str] = None


@dataclass
class Embedding:
    embedding: List[float]
    index: int
    object: Literal["embedding"] = "embedding"


@dataclass
class EmbeddingResponse:
    data: List[Embedding]
    model: str
    usage: Usage
    object: Literal["list"] = "list"


@dataclass
class FileMeta:
    title: Optional[str] = None
    source: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
