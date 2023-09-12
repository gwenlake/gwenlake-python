import os
from typing import Optional
# from langchain.chat_models import AzureChatOpenAI
# from langchain.schema import SystemMessage, HumanMessage
import openai


class ChatOpenAI():
 
    def __init__(self, api_base: Optional[str] = None, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo-16k", stream: bool = False, system: str = "You are a large language model designed to support users in their work."):
        self.model = model
        self.stream = stream
        self.system = system
        if os.environ.get("OPENAI_API_TYPE") == "azure":
            print("OpenAI Azure mode.")
            openai.api_key     = api_key or os.environ.get("OPENAI_API_KEY")
            openai.api_base    = api_base or os.environ.get("OPENAI_API_BASE")
            openai.api_type    = "azure"
            openai.api_version = "2023-05-15" 
            # self.model = AzureChatOpenAI(
            #     openai_api_base = self.api_base,
            #     openai_api_version="2023-05-15",
            #     deployment_name=model,
            #     openai_api_key=api_key,
            #     openai_api_type="azure",
            # )
        else:
            openai.api_key = api_key or os.environ.get('OPENAI_API_KEY')
            if os.environ.get('OPENAI_API_ORGANIZATION'):
                openai.organization = os.environ.get('OPENAI_API_ORGANIZATION')

    def chat(self, messages, temperature=0.0):
        all_messages = [{"role": "system", "content": self.system}]
        all_messages += messages
        try:
            response = openai.ChatCompletion.create(model=self.model, messages=all_messages, temperature=temperature, stream=self.stream)
        except Exception as e:
            print(str(e))
            return None
        return response
