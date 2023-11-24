
from abc import ABC
from gwenlake.schema import Message
from gwenlake.utils import num_tokens_from_string


class ChatMemory(ABC):
 
    def __init__(self, messages: list[Message], max_token_limit=None):
        self.messages = []
        for message in messages:
            self.messages.append(Message(**message))
        self.max_token_limit = max_token_limit
        self.prune()

    def __repr__(self):
        text = ""
        for message in self.messages:
            text += message.role + ": " + message.content[:50] + "\n"
        return text

    def get_messages(self):
        messages = []
        for message in self.messages:
            messages.append(message.dict())
        return messages

    def add_message(self, message: Message):
        self.messages.append(Message(**message))
        self.prune()

    def clear(self):
        self.messages = []

    def prune(self):

        if not self.max_token_limit:
            return self.messages

        num_tokens = 0
        pruned_messages = []

        # add system message
        for message in self.messages:
            if message.role == "system":
                num_tokens += num_tokens_from_string(message.content)
                pruned_messages.append(message)
                break

        # filter other messages in reverse order
        history = []
        for message in reversed(self.messages):
            if message.role != "system":
                current_tokens = num_tokens+num_tokens_from_string(message.content)
                if current_tokens > self.max_token_limit:
                    break
                history.append(message)
                num_tokens += num_tokens_from_string(message.content)

        if len(history)>0:
            history.reverse()
            pruned_messages += history

        self.messages = pruned_messages

        return self.messages
