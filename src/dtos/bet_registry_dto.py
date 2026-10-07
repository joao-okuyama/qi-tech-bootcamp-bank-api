class BetRegistryDTO:
    @staticmethod
    def snapshot(snapshot):
        return {"company_count": snapshot.quantidade, "sha256": snapshot.resumo_conteudo,
                "updated_at": snapshot.atualizado_em.isoformat()}
