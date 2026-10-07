# Como o projeto é organizado

## Responsabilidades

| Camada | Responsabilidade |
|---|---|
| app.py | Registrar rotas e ordem dos middlewares |
| middlewares | Identificar credencial, request ID, sessão, rollback e limpeza |
| schemas | Validar formato dos corpos e parâmetros |
| resources | Adaptar HTTP, chamar um controller e escolher status da resposta |
| controllers | Autorizar, aplicar regras e fazer commit |
| repositories | Consultar, bloquear e persistir, sem commit |
| models/database.sql | Mapear tabelas, chaves e restrições |
| DTOs | Formatar respostas sem consultar ou modificar o banco |
| connectors | Fazer chamadas HTTP externas com limites |
| utils | Validação e ferramentas reutilizáveis |
| errors | Erros de domínio e resposta padronizada |

Middlewares rodam em ordem inversa ao registro no FastAPI. O request ID fica por
fora do logger; autenticação precede o contexto de sessão. ContextVars são
restauradas ao encerrar o trabalho, inclusive em falhas.

## Caminho de cada requisito

| Requisito | Resource / schema | Controller | Repository | Tabelas / DTO |
|---|---|---|---|---|
| Cadastro PF/PJ | customer.py; post_student.json / post_student_organization.json | CustomerController | CustomerRepository / UniversityRepository | cliente, aluno, organizacao_estudantil, status_cliente, evento_status_cliente / CustomerDTO |
| Conta vinculada | account.py; post_account.json | AccountController | AccountRepository | conta, status_conta, evento_status_conta / AccountDTO |
| Transferência | payment.py; post_transfer.json | PaymentController / AccessPolicy | PaymentRepository / AccessRepository | transferencia, movimentacao_conta, status_transferencia, evento_status_transferencia / PaymentDTO |
| Tarifa | mesmo fluxo da transferência | payment_policy.calculate_fee | PaymentRepository | conta de receita e movimentos TARIFA / RECEITA_TARIFA |
| Extrato paginado | account.py; get_account_statement.json | AccountController | AccountRepository | movimentacao_conta com transferência opcional / AccountDTO |
| Bloqueio BET | transferência; bet_registry.py na sincronização | PaymentController / BetRegistryController | BetRepository | empresas_bet_autorizadas, sincronizacao_empresas_bet / BetRegistryDTO |

## Transações e estados

Conta e cliente armazenam status_id; seus relacionamentos carregam o código para
o DTO. Repositories carregam esses relacionamentos antes de devolver registros.
Não há coluna textual situacao nem API para mudar o estado dessas entidades.

O cadastro e a abertura de conta incluem o evento inicial na mesma transação.
Os eventos da migração não inventam datas antigas. Transferências registram
cada transição aplicada pelo controller.

Uma transferência bloqueia contas em ordem crescente de ID, depois clientes.
Para destino PJ, adquire leitura compartilhada na linha única do cadastro BET.
A sincronização baixa/valida antes de adquirir o bloqueio exclusivo nessa linha
e nunca bloqueia contas. A consulta e a movimentação enxergam uma lista consistente.

A autorização e as verificações financeiras ficam dentro do mesmo trabalho.
Falha desfaz todo o saldo e os movimentos; repository.flush não significa commit.
Uma repetição concluída não movimenta saldo nem reaplica a política BET.

## Cadastro BET

Apenas o connector acessa o gov.br. O parser interpreta o CSV sem SQL. O
controller valida a permissão, rejeita uma lista incompleta e exige revisão do
hash para remover CNPJs. O repository substitui linhas e metadados atomicamente.
O script de sincronização chama a API, não o repository.

Nenhuma transferência baixa o CSV. Uma lista válida continua sendo usada após
falha de download; destinos PJ falham com 503 quando a lista expira ou não existe.
PF não depende da lista. A identificação usa o CNPJ da organização cadastrada,
não dados adicionais enviados no pedido de transferência.

## Testes

A aceitação percorre HTTP com clientes, contas, depósitos e credenciais reais
do ambiente de teste. MockServer controla a resposta CSV. A integração verifica
também saldo versus ledger, rollback injetado, restrições e upgrade de schema.

Os testes locais de parser, tarifa e arquitetura apoiam essas jornadas. Não
substituem PostgreSQL, concorrência HTTP ou Docker/Linux. Os dois comandos de
entrega estão no README.
