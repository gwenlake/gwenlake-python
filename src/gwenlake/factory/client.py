import os
from typing import Optional

from gwenlake.core.credentials import Credentials
from gwenlake.factory.datasets import DatasetsClient


class FactoryClient:

    def __init__(self, credentials: Optional[Credentials] = None):

        if credentials is None:
            credentials = Credentials.from_profile("default")

        self.datasets = DatasetsClient(credentials=credentials)
