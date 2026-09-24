# Como o projeto é organizado

Usamos FastAPI para HTTP e SQLAlchemy para persistência, mantendo as camadas do
projeto-base da QI Tech. A regra de negócio não fica em endpoints, middlewares,
models ou consultas SQL.

## Responsabilidades

| Camada | Responsabilidade | Não faz |
|---|---|---|
| `app.py` | Registrar rotas, middlewares e tratamento de erros | Regra de transferência |
| `middlewares/` | Contexto, logs, identificação da credencial e ciclo da sessão | Decidir saldo suficiente ou aprovação |
| `schemas/` | Validar estrutura, tipos e campos permitidos da entrada | Consultar saldo ou permissão |
| `resources/` | Receber parâmetros HTTP, aplicar schema, chamar controller e montar resposta HTTP | Consultas SQL e decisões de negócio |
| `controllers/` | Autorizar a operação, aplicar regras, coordenar repositories e confirmar transação | Manipular Request ou escrever consultas |
| `repositories/` | Consultar, bloquear e persistir dados | Autorizar usuário ou fazer commit |
| `models/` | Mapear tabelas e colunas | Processar pagamentos |
| `dtos/` | Converter dados no contrato de saída | Consultar banco |
| `errors/` | Definir erros e sua tradução para HTTP | Executar fluxo de negócio |
| `connectors/` | Encapsular chamadas externas | Controlar nosso banco |

`database/database.sql` define constraints, índices, estados e gatilhos.
`src/database.py` fornece o contexto e a sessão usados pelo controller e pelos
repositories. O contexto é isolado por requisição; os DTOs não acessam a sessão.

## Exemplo: criar uma transferência

1. [app.py](../src/app.py) registra `POST /transfer` no `PaymentResource`.
2. Os [middlewares](../src/middlewares) criam o contexto, registram o acesso e
   identificam o tipo da credencial. A sessão é criada sob demanda.
3. [post_transfer.json](../src/schemas/post_transfer.json), aplicado por
   `SchemaHandler`, rejeita campos inesperados e valores com tipos incorretos.
4. [PaymentResource](../src/resources/payment.py) chama `PaymentController.create`.
   Ele escolhe 201 para criação ou 200 para repetição idempotente.
5. [PaymentController](../src/controllers/payment_controller.py) identifica o
   aluno com [AccessPolicy](../src/controllers/access_policy.py), verifica
   autorização, idempotência, saldo e regras de aprovação.
   [payment_policy.py](../src/controllers/payment_policy.py) contém o cálculo
   inteiro da tarifa e a validação de valor.
6. [PaymentRepository](../src/repositories/payment_repository.py) bloqueia as
   contas em ordem de ID, consulta e grava pelos [models](../src/models).
   [AccessRepository](../src/repositories/access_repository.py) consulta
   credenciais, vínculos e designações.
7. [PaymentDTO](../src/dtos/payment_dto.py) monta a resposta. O controller confirma
   as alterações na mesma transação. Qualquer falha anterior ao commit desfaz
   saldo, movimentos e eventos; o middleware fecha a sessão ao final.

Em PF, a operação pode concluir na criação. Em PJ, a criação só registra a
solicitação pendente: outra pessoa precisa aprovar antes de movimentar saldo.
As regras completas estão em [Pagamentos](pagamentos.md).

## Sessão e ordem dos middlewares

A ordem de execução é contexto → log → credencial → sessão → rota.
No FastAPI, o último middleware registrado é o primeiro a executar; por isso
o registro em `app.py` aparece na ordem inversa.

O middleware de credenciais não consulta tabelas de negócio. A validação do token
individual e da permissão sobre a conta acontece pela política de acesso chamada
pelo controller. Schema válido e credencial presente não bastam para autorizar.

O repository pode fazer `flush` para obter IDs ou detectar constraints, mas não
faz `commit`. A confirmação pertence ao controller, que conhece a operação inteira.
Health checks não criam controller bancário nem dependem de uma sessão aberta.

## Testes

- `tests/acceptance`: contratos observados somente por HTTP.
- `tests/integration`: banco real, constraints, reconciliação e rollback.
- `tests/unit`: regras isoladas, DTOs, validação e limites das camadas.

Os testes de arquitetura verificam dependências entre camadas e algumas
restrições estruturais; não substituem a revisão da lógica de negócio.
