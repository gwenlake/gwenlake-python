import logging
import requests
from tenacity import retry, stop_after_attempt, wait_random_exponential
import gwenlake
from langchain.prompts import PromptTemplate

TIMEOUT  = 20

logger = logging.getLogger(__name__)


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def pull(path):

    api_key  = gwenlake.api_key
    api_base = gwenlake.api_base
    if not api_key or not api_base:
        return None
    url = f"{api_base}/hub/{path}"
    headers = { "Authorization": f"Bearer {api_key}" }

    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    if r.status_code != 200:
        logger.exception("An error occurred on pull.")
        raise Exception
    data = r.json()

    if data["object"] == "prompt":
        prompt_template = PromptTemplate.from_template(data["content"])
        return prompt_template

    return data
