from datetime import datetime, timezone
from csv import Error as CSVError
from hashlib import sha256

from connectors.bet_registry_connector import BetRegistryConnector
from controllers.access_policy import AccessPolicy
from controllers.base_controller import BaseController
from dtos.bet_registry_dto import BetRegistryDTO
from errors.bet_errors import BetRegistryInvalid, BetRegistryReviewRequired, BetRegistryUnavailable
from errors.base_error import QIException
from repositories.bet_repository import BetRepository
from utils.bet_registry import parse_bet_registry


class BetRegistryController(BaseController):
    def __init__(self):
        super().__init__(self.__class__.__name__)
        self.access = AccessPolicy(self.context)
        self.connector = BetRegistryConnector()
        self.repository = BetRepository(self.context)

    def sync(self, payload):
        self.access.require_internal()
        content = self.connector.download()
        digest = sha256(content).hexdigest()
        try:
            companies = parse_bet_registry(content)
        except (ValueError, UnicodeError, CSVError, QIException):
            raise BetRegistryInvalid() from None
        # A chamada HTTP e a validacao terminam antes de bloquear a linha do cadastro.
        snapshot = self.repository.snapshot(exclusive=True)
        if snapshot is None:
            raise BetRegistryUnavailable()
        incoming = {company["cnpj"] for company in companies}
        removed = self.repository.cnpjs() - incoming
        if removed and payload.get("reviewed_sha256") != digest:
            raise BetRegistryReviewRequired(digest, len(removed))
        self.repository.replace_all(companies, snapshot, digest, datetime.now(timezone.utc))
        result = BetRegistryDTO.snapshot(snapshot)
        self.session.commit()
        return result
