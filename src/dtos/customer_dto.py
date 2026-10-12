from models import Cliente


class CustomerDTO:
    @staticmethod
    def obj_to_dict(customer: Cliente) -> dict:
        return {
            "customer_key": str(customer.chave),
            "type": customer.tipo,
            "status": customer.status.codigo,
            "created_at": customer.criado_em.isoformat(),
        }
