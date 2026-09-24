# Banco universitário

API do bootcamp QI Tech para alunos e organizações estudantis. Alunos podem usar
sua conta sem participar de uma organização. PIX, TED e depósitos são simulados:
não há integração bancária externa nem movimentação de dinheiro real.

Este incremento acrescenta transferências com controle de saldo e cobrança de
tarifa ao cadastro de clientes e contas da Aula 2. O extrato passa a mostrar as
movimentações produzidas por esses fluxos.

## Escopo

| Requisito | Como está implementado |
|---|---|
| Cadastro de cliente | Universidade, aluno PF e organização estudantil PJ, com validação e unicidade dos documentos |
| Conta vinculada ao cliente | Uma conta por CPF/CNPJ, aberta com saldo zero |
| Transação com controle de saldo | Débito e crédito na mesma transação, bloqueios de concorrência e idempotência |
| Tarifa na transferência | TED de PJ: 1%, arredondamento de meio centavo para cima e teto de R$9,99 |
| Extrato paginado | Débitos, créditos, depósitos e tarifas; paginação por página ou cursor |

PF não paga tarifa em PIX ou TED; PJ não paga em PIX. Valores são inteiros em
centavos: `100` representa R$1,00.

Para sustentar esses fluxos, a API inclui credenciais individuais, depósitos
administrativos simulados e aprovação de transferências de organizações.
Cada organização tem pelo menos dois membros e exatamente dois aprovadores
designados. Uma transferência precisa da aprovação de outra pessoa; não exige
duas assinaturas. Cargo institucional e permissão de aprovação são independentes.

## Executar

Requisitos: Docker com Compose. Na pasta que contém este README:

```bash
docker compose up --build
```

A API atende em `http://127.0.0.1:3000`. `GET /health_check` retorna 204.
O PostgreSQL é inicializado por [database/database.sql](database/database.sql).

O `.env` é opcional. Para personalizar portas ou o token administrativo, copie
[.env.example](.env.example) para `.env` e ajuste os valores. Os padrões do Compose
servem somente para desenvolvimento local. Não use dados pessoais reais.

**Banco existente:** este incremento altera tabelas. O SQL de inicialização só
roda em um banco vazio; reiniciar containers não aplica migração. Os ambientes
de teste abaixo usam bancos próprios. Não execute `down -v` em um ambiente cujos
dados queira preservar. Este pacote não inclui migração dos dados da Aula 2.

## Autenticação e autorização

- O operador usa `INTERNAL-TOKEN` para cadastrar clientes, abrir contas,
  configurar membros/aprovadores, emitir credenciais e registrar depósitos.
- `POST /customer/{customer_key}/credential`, com corpo `{}`, emite uma
  credencial individual para um aluno ativo. Só o hash fica armazenado.
  Emitir outra credencial invalida a anterior.
- O aluno usa `Authorization: Bearer <access_token>`. O servidor identifica o
  aluno e verifica se ele pode agir sobre a conta. Conhecer um UUID não autoriza
  movimentar ou consultar a conta de outra pessoa.
- PJ não recebe uma credencial coletiva: cada membro age com sua própria identidade.
  Membros ativos podem consultar e solicitar; somente um aprovador designado,
  diferente do solicitante, pode aprovar.

Não há login, expiração automática de tokens ou MFA nesta versão. A emissão
administrativa simula o provisionamento de acesso; não é autenticação de produção.
O token administrativo é privilegiado e não deve ser entregue aos alunos.

## Rotas bancárias

| Método | Rota | Operação |
|---|---|---|
| POST / GET | `/university` / `/university/{key}` | Cadastrar / consultar universidade |
| POST | `/student` | Cadastrar aluno |
| POST | `/student_organization` | Cadastrar organização |
| GET | `/customer/{key}` | Consultar cliente |
| POST | `/customer/{key}/account` | Abrir conta; corpo `{}` |
| GET | `/account/{key}` | Consultar conta |
| GET | `/account/{key}/balance` | Consultar saldo |
| GET | `/account/{key}/statement` | Consultar extrato |
| POST | `/customer/{key}/credential` | Emitir ou rotacionar credencial; corpo `{}` |
| PUT | `/customer/{key}/banking_access` | Configurar membros e aprovadores |
| POST | `/account/{key}/deposit` | Registrar recebimento simulado |
| POST / GET | `/transfer` / `/transfer/{key}` | Criar / consultar transferência |
| POST | `/transfer/{key}/approve` | Aprovar; corpo `{}` |
| POST | `/transfer/{key}/reject` | Recusar; corpo `{}` |
| POST | `/transfer/{key}/execute` | Executar aprovação que aguardava saldo; corpo `{}` |

Os contratos, exemplos de payload e regras estão em [Pagamentos](docs/pagamentos.md).
As rotas de `sample_entity` do projeto-base foram mantidas para a regressão;
não representam produtos bancários.

## Testes

Aceitação por HTTP contra a API já iniciada:

```bash
pip install -r requirements-acceptance.txt
pytest
```

A suíte usa dados fictícios criados pela API, sem importar a aplicação ou acessar
SQL. Ela grava dados no ambiente apontado por `API_BASE_URL`; use apenas uma
instância de desenvolvimento/teste. Se mudar o token ou a porta da API, ajuste
também as variáveis do executor.

Para executar em containers isolados, sem usar o banco de desenvolvimento:

```bash
docker compose -p banco-acceptance -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
```

Regressão completa, incluindo testes unitários e de integridade no PostgreSQL:

```bash
docker compose -p banco-regression -f docker-compose.test.yml -f docker-compose.regression.yml up --build --abort-on-container-exit --exit-code-from tests
```

Os testes de integração recriam o schema de teste. Eles exigem `APP_ENV=test`,
`ALLOW_TEST_DATABASE_RESET=1` e nome de banco terminado em `_test`. Não rode os
arquivos em paralelo: os cenários de concorrência já coordenam suas requisições.

Após os testes, encerre apenas esses projetos descartáveis:

```bash
docker compose -p banco-acceptance -f docker-compose.test.yml down
docker compose -p banco-regression -f docker-compose.test.yml -f docker-compose.regression.yml down
```

O workflow [tests.yml](.github/workflows/tests.yml) executa as duas suítes em Linux.
Os resultados obtidos nesta cópia e as verificações ainda pendentes estão em
[Validação](docs/validacao.md).

## Organização do código

Mantemos as responsabilidades do projeto-base: `app.py → middlewares → schemas →
resources → controllers → repositories → models/database`; os DTOs montam a saída.
O controller decide o commit; repositories não confirmam transações e o middleware
desfaz falhas e fecha a sessão. O guia [Como o projeto é organizado](docs/como-o-projeto-e-organizado.md)
mostra os arquivos envolvidos em uma transferência.

Em relação à base local da Aula 2 (`85f92e2`), as mudanças principais são os fluxos
de pagamentos/acesso, seus contratos e models, as constraints do banco e os testes.
Não foram acrescentados investimentos, rendimento CDI, comissão de formatura,
boletos ou serviços externos.

Antes da entrega final, ainda é necessário validar os containers no ambiente
Linux, revisar as regras com o grupo e finalizar a apresentação em PDF.
