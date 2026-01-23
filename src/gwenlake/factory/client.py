import os
from typing import Optional

from gwenlake.factory.core.credentials import Credentials
from gwenlake.factory.datasets import DatasetsClient


class FactoryClient:

    def __init__(self, credentials: Optional[Credentials] = None):

        if credentials is None:
            credentials = Credentials()

        self.datasets = DatasetsClient(credentials=credentials)
