import os
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_random_exponential
import gwenlake
from langchain.prompts import PromptTemplate

TIMEOUT  = 20

logger = logging.getLogger(__name__)


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def pull(repo):

    api_key  = gwenlake.api_key
    api_base = gwenlake.api_base
    if not api_key or not api_base:
        return None
    url = f"{api_base}/hub/{repo}"
    headers = { "Authorization": f"Bearer {api_key}" }

    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    if r.status_code != 200:
        logger.exception("An error occurred on pull.")
        raise Exception
    data = r.json()

    if data.get("object") == "prompt" and data.get("template"):
        return PromptTemplate.from_template(data["template"])

    return data


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def push(repo, file):

    api_key  = gwenlake.api_key
    api_base = gwenlake.api_base
    if not api_key or not api_base:
        return None
    url = f"{api_base}/hub/{repo}/push"
    headers = { "Authorization": f"Bearer {api_key}" }

    if not isinstance(file, str):
        raise ValueError("file must be a string")    
    file_ = {"file": open(file, "rb")}

    return requests.post(url, headers=headers, files=file_)
