from datetime import timezone


def timestamp(value):
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


class PaymentDTO:
    @staticmethod
    def transfer(transfer, status, source, destination, requester, approver):
        return {
            "transfer_key": str(transfer.chave),
            "source_account_key": str(source.chave),
            "destination_account_key": str(destination.chave),
            "requester_customer_key": str(requester.chave),
            "approver_customer_key": str(approver.chave) if approver else None,
            "amount_cents": transfer.valor_centavos,
            "fee_cents": transfer.tarifa_centavos,
            "type": transfer.tipo,
            "description": transfer.descricao,
            "status": status,
            "created_at": timestamp(transfer.criado_em),
            "completed_at": timestamp(transfer.concluido_em),
        }

    @staticmethod
    def deposit(deposit, account):
        return {
            "deposit_key": str(deposit.chave),
            "account_key": str(account.chave),
            "reference": deposit.referencia,
            "amount_cents": deposit.valor_centavos,
            "created_at": timestamp(deposit.criado_em),
        }
