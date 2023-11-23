
from gwenlake.schema import Message
from gwenlake.utils import num_tokens_from_string


class ChatMemory:
 
    def __init__(self, messages: list[Message]):
        self.messages = messages

    def clear(self):
        self.messages = []

    def prune(self, max_token_limit):

        num_tokens = 0
        pruned_messages = []

        # add system message
        for message in self.messages:
            if message.role == "system":
                num_tokens += num_tokens_from_string(message.content)
                pruned_messages.append(message)
                break

        # filter other messages
        history = []
        for message in reversed(self.messages):
            if message.role != "system":
                if (num_tokens+num_tokens_from_string(message.content)) < max_token_limit:
                    history.append(message)
                    num_tokens += num_tokens_from_string(message.content)

        if len(history)>0:
            history.reverse()
            pruned_messages += history

        self.memory = pruned_messages

        return self.memory
