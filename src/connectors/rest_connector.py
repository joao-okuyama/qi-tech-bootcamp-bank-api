import json
import time
from abc import ABCMeta

import requests

from utils.logger import get_logger


class RestConnector(metaclass=ABCMeta):

    def __init__(self, class_name: str, base_url: str, timeout: int, internal_token: str) -> None:
        self.logger = get_logger(class_name)
        self.base_url = base_url
        self.timeout = timeout
        self.internal_token = internal_token

    def send(self, endpoint: str, method: str, payload: dict = None, headers: dict = None):
        if headers is None:
            headers = {}

        headers["INTERNAL-TOKEN"] = self.internal_token

        url = f"{self.base_url}{endpoint}"

        self.logger.info(f"OUTGOING REQUEST {method} {url}")
        started_at = time.perf_counter()

        response = requests.request(
            method.upper(),
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        self.logger.info(f"INCOMING RESPONSE {response.status_code} {method} {url} - {elapsed_ms:.1f} ms")

        return BaseConnectorResponse(endpoint, method, response)


class BaseConnectorResponse:

    def __init__(self, endpoint: str, method: str, response: requests.Response) -> None:
        self.endpoint = endpoint
        self.method = method
        self.status = response.status_code

        self.json = None
        try:
            self.json = json.loads(response.content)
        except ValueError:
            pass
