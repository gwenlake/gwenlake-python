
from abc import ABC
from gwenlake.schema import Message
from gwenlake.utils import num_tokens_from_string


class ChatMemory(ABC):
 
    def __init__(self, system: str = None, max_token_limit=None):
        self.system = None
        self.messages = []
        if system:
            self.system = Message(role="system", content=system)
        self.max_token_limit = max_token_limit

    def __repr__(self):
        text = ""
        for message in self.get_messages():
            text += message["role"] + ": " + message["content"][:50] + "\n"
        return text

    def clear(self):
        self.messages = []

    def get_messages(self):
        messages = []
        if self.system:
            messages.append(self.system.dict())
        for message in self.messages:
            messages.append(message.dict())
        return messages

    def add_messages(self, messages: list[Message]):
        for message in messages:
            self.messages.append(Message(**message))
        self.prune()

    def add_message(self, message: Message):
        self.messages.append(Message(**message))
        self.prune()

    def prune(self):

        if not self.max_token_limit:
            return self.messages

        if not self.messages:
            return []

        # system
        num_tokens = 0
        if self.system:
            num_tokens += num_tokens_from_string(self.system.content)

        # parse messages in reverse order
        pruned_history = []
        for message in reversed(self.messages):
            n = num_tokens + num_tokens_from_string(message.content)
            if n > self.max_token_limit:
                break
            pruned_history.append(message)
            num_tokens += num_tokens_from_string(message.content)

        if len(pruned_history)>0:
            pruned_history.reverse()

        self.messages = pruned_history

        return self.messages
