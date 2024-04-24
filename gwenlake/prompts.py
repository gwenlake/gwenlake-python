from __future__ import annotations

from typing import TYPE_CHECKING

from langchain.prompts import PromptTemplate


from .resource import Resource

if TYPE_CHECKING:
    from .client import Client


__all__ = ["Prompts"]



class Prompts(Resource):

    def __init__(self, client: Client) -> None:
        super().__init__(client)


    def list(self, ref: str):
        resp = self._client._request("GET", f"/prompts/{ ref }")
        obj = resp.json()
        return obj.get("data")

    def format_prompt(self, messages: list, input: list = []):
        messages_formated = []
        for message in messages:
            t = PromptTemplate.from_template(template=message["content"])
            if len(t.input_variables)>0:
                data = { i: input[i] for i in t.input_variables }
                text = t.format(**data)
                messages_formated.append({"role": message["role"], "content": text})
            else:
                messages_formated.append({"role": message["role"], "content": message["content"]})
        return messages_formated

    def get(self, ref: str, input: list = []):
        resp = self._client._request("GET", f"/prompts/{ ref }")
        obj = resp.json()
        if input:
            return self.format_prompt(obj["template"], input=input)
        return obj["template"]
