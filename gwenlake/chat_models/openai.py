import os
import logging
import openai
from typing import Optional
from gwenlake.schema import Message


logger = logging.getLogger(__name__)


class ChatOpenAI():
 
    def __init__(self, api_base: Optional[str] = None, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo-16k", temperature=0.0):
        self.model = model
        self.temperature = temperature
        if os.environ.get("OPENAI_API_TYPE") == "azure":
            logger.warning("ChatOpenAI: Azure mode.")
            openai.api_key     = api_key or os.environ.get("OPENAI_API_KEY")
            openai.api_base    = api_base or os.environ.get("OPENAI_API_BASE")
            openai.api_type    = "azure"
            openai.api_version = "2023-05-15" 
        else:
            logger.warning("ChatOpenAI: OpenAI mode.")
            openai.api_key = api_key or os.environ.get('OPENAI_API_KEY')
            if os.environ.get('OPENAI_API_ORGANIZATION'):
                openai.organization = os.environ.get('OPENAI_API_ORGANIZATION')

    def chat(self, messages: list[Message], stream=False):
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(model=self.model, messages=messages, temperature=self.temperature, stream=stream)
        except Exception as e:
            logger.error(e)
            return None
        return response

    def stream(self, messages: list[Message]):
        response = self.chat(messages=messages, stream=True)
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
