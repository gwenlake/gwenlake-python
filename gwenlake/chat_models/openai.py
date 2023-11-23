import os
import logging
import openai
from typing import Optional

from gwenlake.schema import Message, ChatCompletion


logger = logging.getLogger(__name__)


class ChatOpenAI():
 
    def __init__(self, api_key: Optional[str] = None, api_version: Optional[str] = "2023-05-15", azure_endpoint: Optional[str] = None, model: str = "gpt-3.5-turbo-16k", temperature=0.0):

        self.model = model
        self.temperature = temperature

        openai.api_key = api_key or os.environ.get("OPENAI_API_KEY")

        if os.environ.get("OPENAI_API_TYPE") == "azure":
            logger.warning("ChatOpenAI: Azure mode.")
            _version  = api_version or os.environ.get("OPENAI_API_VERSION")
            _endpoint = azure_endpoint or os.environ.get("OPENAI_API_BASE")
            self.client = openai.AzureOpenAI(api_version=_version, azure_endpoint=_endpoint)

        else:
            logger.warning("ChatOpenAI: OpenAI mode.")
            if os.environ.get('OPENAI_API_ORGANIZATION'):
                openai.organization = os.environ.get('OPENAI_API_ORGANIZATION')
            self.client = openai.OpenAI()


    def chat(self, messages: list[Message]):
        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages, temperature=self.temperature)
        except Exception as e:
            logger.error(e)
            return None
        if not response.choices[0].message.content:
            return None
        return ChatCompletion(message=Message(role="assistant", content=response.choices[0].message.content))


    def stream(self, messages: list[Message]):
        content = ""
        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages, temperature=self.temperature, stream=True)
        except Exception as e:
            logger.error(e)
            return None
        for chunk in response:
            if not chunk.choices[0].finish_reason:
                if chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content
                    yield chunk.choices[0].delta.content
            else:
                yield ChatCompletion(message=Message(role="assistant", content=content))
