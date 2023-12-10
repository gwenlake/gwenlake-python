import os
import logging
import uuid
import openai
from typing import Optional

from gwenlake.schema import Message, ChatCompletion, ChatCompletionChunk, Choice, ChoiceDelta, Usage
from gwenlake.utils import num_tokens_from_string, num_tokens_from_messages

logger = logging.getLogger(__name__)


class ChatOpenAI():
 
    def __init__(self, api_key: Optional[str] = None, api_version: Optional[str] = "2023-05-15", azure_endpoint: Optional[str] = None, model: str = "gpt-3.5-turbo-16k", temperature=0.0):

        self.temperature = temperature

        if os.environ.get("AZURE_OPENAI_API_KEY"):
            logger.warning("ChatOpenAI: Azure mode.")
            _endpoint    = azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
            _api_key     = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
            _api_version = api_version or os.environ.get("AZURE_OPENAI_API_VERSION")
            self.model   = os.environ.get("AZURE_OPENAI_API_MODEL") or model
            self.client = openai.AzureOpenAI(api_key=_api_key, api_version=_api_version, azure_endpoint=_endpoint)

        else:
            logger.warning("ChatOpenAI: OpenAI mode.")
            openai.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            if os.environ.get('OPENAI_API_ORGANIZATION'):
                openai.organization = os.environ.get('OPENAI_API_ORGANIZATION')
            self.model = model
            self.client = openai.OpenAI()


    def chat(self, messages: list[Message]):
        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages, temperature=self.temperature)
        except Exception as e:
            logger.error(e)
            return None
        if not response.choices[0].message.content:
            return None

        return ChatCompletion(
            model=self.model,
            system_fingerprint=response.system_fingerprint,
            choices=[ Choice(message=Message(role="assistant", content=response.choices[0].message.content)) ],
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
        )


    def stream(self, messages: list[Message]):
        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages, temperature=self.temperature, stream=True)
        except Exception as e:
            logger.error(e)
            yield ""
    
        _id = "chatcmpl-" + str(uuid.uuid4())
        _content = ""

        for chunk in response:
            if not chunk.choices[0].finish_reason:
                 if isinstance(chunk.choices[0].delta.content, str):
                    _content += chunk.choices[0].delta.content
                    yield chunk.choices[0].delta.content
                    # yield ChatCompletionChunk(
                    #     id=_id,
                    #     model=self.model,
                    #     choices=[ ChoiceDelta(delta=Message(role="assistant", content=chunk.choices[0].delta.content)) ],
                    #     finish_reason=None,
                    # )
            else:
                usage = Usage()
                usage.prompt_tokens = num_tokens_from_messages(messages)
                usage.completion_tokens = num_tokens_from_string(_content)
                usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                yield ChatCompletion(
                    id=_id,
                    model=self.model,
                    choices=[ Choice(message=Message(role="assistant", content=_content)) ],
                    finish_reason="stop",
                    usage=usage
                )

