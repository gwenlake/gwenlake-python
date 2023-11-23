import os
import logging
import uuid
import openai
from typing import Optional

from gwenlake.schema import Message, ChatCompletion, Choice, ChoiceDelta


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
        return ChatCompletion(choices=[ Choice(message=Message(role="assistant", content=response.choices[0].message.content)) ])


    def stream(self, messages: list[Message]):
        content = ""
        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages, temperature=self.temperature, stream=True)
        except Exception as e:
            logger.error(e)
            return None
        _id = "chatcmpl-" + str(uuid.uuid4())
        for chunk in response:
            if not chunk.choices[0].finish_reason:
                if chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content
                    yield ChatCompletion(id=_id, choices=[ ChoiceDelta(delta=Message(role="assistant", content=chunk.choices[0].delta.content)) ])
            else:
                yield ChatCompletion(id=_id, choices=[ Choice(message=Message(role="assistant", content=content)) ])
