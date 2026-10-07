import time
from urllib.parse import urlsplit

import requests
from urllib3.exceptions import HTTPError

from constants import APP_ENV, BET_REGISTRY_MAX_BYTES, BET_REGISTRY_TIMEOUT, BET_REGISTRY_URL
from errors.bet_errors import BetRegistryUnavailable
from utils.logger import get_logger


class BetRegistryConnector:
    def __init__(self):
        self.url = BET_REGISTRY_URL
        self.timeout = BET_REGISTRY_TIMEOUT
        self.max_bytes = BET_REGISTRY_MAX_BYTES
        self.logger = get_logger(self.__class__.__name__)

    def download(self):
        url = urlsplit(self.url)
        if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
                or url.fragment or (url.scheme != "https" and APP_ENV != "test")):
            raise BetRegistryUnavailable()
        started = time.monotonic()
        try:
            # O CSV e publico. Nao envia a credencial administrativa do banco.
            with requests.get(self.url, headers={"Accept": "text/csv", "Accept-Encoding": "identity"},
                              timeout=self.timeout, stream=True, allow_redirects=False) as response:
                if response.status_code != 200:
                    raise BetRegistryUnavailable()
                mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if mime not in ("text/csv", "application/csv", "text/plain"):
                    raise BetRegistryUnavailable()
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise BetRegistryUnavailable()
                length = response.headers.get("Content-Length")
                if length is not None and (not length.isdecimal() or int(length) > self.max_bytes):
                    raise BetRegistryUnavailable()
                content = bytearray()
                while True:
                    if time.monotonic() - started > self.timeout:
                        raise BetRegistryUnavailable()
                    chunk = response.raw.read1(65536, decode_content=False)
                    if not chunk:
                        break
                    content.extend(chunk)
                    if len(content) > self.max_bytes:
                        raise BetRegistryUnavailable()
                if length is not None and len(content) != int(length):
                    raise BetRegistryUnavailable()
                self.logger.info("BET registry downloaded: %s bytes", len(content))
                return bytes(content)
        except (requests.RequestException, HTTPError, OSError, ValueError) as error:
            self.logger.warning("BET registry download failed: %s", type(error).__name__)
            raise BetRegistryUnavailable() from None
