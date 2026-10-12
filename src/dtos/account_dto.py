from models import Conta, MovimentacaoConta


class AccountDTO:
    @staticmethod
    def obj_to_dict(account: Conta) -> dict:
        return {
            "account_key": str(account.chave),
            "currency": account.moeda,
            "status": account.status.codigo,
            "created_at": account.criado_em.isoformat(),
        }

    @staticmethod
    def statement(rows, limit, page=None, cursor=None):
        result = {"data": [AccountDTO.movement_to_dict(*row) for row in rows[:limit]],
                  "is_last_page": len(rows) <= limit}
        if len(rows) > limit:
            result["next_cursor"] = str(rows[limit - 1][0].chave)
        if page is not None:
            result.update({"limit": limit, "page": page})
        if cursor is not None:
            result.update({"limit": limit, "cursor": cursor})
        return result

    @staticmethod
    def balance_to_dict(account: Conta) -> dict:
        return {
            "account_key": str(account.chave),
            "balance_cents": account.saldo_centavos,
            "currency": account.moeda,
        }

    @staticmethod
    def movement_to_dict(movement: MovimentacaoConta, transfer_key, description) -> dict:
        direction = "DEBIT" if movement.tipo in ("DEBITO", "TARIFA") else "CREDIT"
        return {
            "movement_key": str(movement.chave),
            "transfer_key": str(transfer_key) if transfer_key else None,
            "type": movement.tipo,
            "direction": direction,
            "amount_cents": movement.valor_centavos,
            "description": description,
            "created_at": movement.criado_em.isoformat(),
        }
