class AccessDTO:
    @staticmethod
    def credential(token):
        return {"access_token": token, "token_type": "Bearer"}

    @staticmethod
    def configuration(organization, member_count, approver_count):
        return {"customer_key": str(organization.chave),
                "members": member_count, "approvers": approver_count}
