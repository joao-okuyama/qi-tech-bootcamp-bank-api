# Banco Universitário — API de Serviços Bancários

API REST desenvolvida em **Python + FastAPI**, com banco de dados **PostgreSQL**, seguindo rigorosamente a **Arquitetura QI Tech** (Base Service).

O sistema provê infraestrutura de conta digital para estudantes universitários e organizações estudantis (centros acadêmicos, atléticas e diretórios), suportando abertura de contas, emissão de credenciais de acesso, depósitos simulados, transferências PIX e TED, cálculo de tarifas, aprovação em duas etapas para pessoas jurídicas e emissão de extratos paginados.

---

## 1. O Problema e Funcionalidades Suportadas

O Banco Universitário atende a dois perfis de clientes vinculados a instituições de ensino superior:
- **Alunos (PF)**: Estudantes com CPF válido e data de nascimento que abrem e movimentam contas individuais.
- **Organizações Estudantis (PJ)**: Entidades com CNPJ válido e vínculo com alunos (membros e aprovadores designados).

### Principais Funcionalidades:
1. **Cadastro Institucional e de Clientes**:
   - Criação de universidades (`POST /university`).
   - Cadastro de alunos (`POST /student`) e organizações estudantis (`POST /student_organization`).
   - Validação estrita de documentos (CPF e CNPJ com verificação dos dígitos verificadores e rejeição de caracteres de controle).
2. **Conta Corrente Digital**:
   - Uma conta por cliente (`POST /customer/{customer_key}/account`), com saldo inicial zero em BRL.
   - Chave pública UUID (`account_key`) desacoplada do ID numérico interno do banco de dados.
3. **Identidade e Autorização**:
   - **Administrativa (`INTERNAL-TOKEN`)**: Provisionamento de entidades, abertura de contas, emissão de credenciais, configuração de acessos e liquidação de depósitos.
   - **Estudante (`Authorization: Bearer <token>`)**: Acesso individual emitido para o aluno (`POST /customer/{customer_key}/credential`). O token é gerado com entropia criptográfica (`secrets.token_urlsafe`) e armazenado no banco exclusivamente como hash SHA-256.
4. **Política Financeira e Tarifação**:
   - Valores monetários manipulados e persistidos **exclusivamente em centavos** (`BIGINT`), eliminando erros de precisão de ponto flutuante.
   - **PF**: PIX e TED gratuitos e ilimitados.
   - **PJ**: PIX gratuito; TED com tarifa de 1% (arredondamento para cima, com teto de R$ 9,99 / 999 centavos).
   - A tarifa é debitada da conta de origem e creditada atomicamente na conta interna do banco (`RECEITA_TARIFAS`).
5. **Governança Organizacional (Dupla Aprovação)**:
   - Configuração de membros e aprovadores (`PUT /customer/{customer_key}/banking_access`).
   - Exigência de pelo menos 2 membros ativos e exatamente 2 aprovadores designados.
   - Transferências de organizações nascem em `PENDENTE_APROVACAO` e exigem aprovação de um aprovador distinto do solicitante (**autoaprovação proibida**).
6. **Extrato e Auditoria Imutável**:
   - Consulta de extrato (`GET /account/{account_key}/statement`) com suporte a paginação por página/offset e por cursor.
   - Gatilhos de banco de dados (`BEFORE UPDATE OR DELETE`) que asseguram a imutabilidade absoluta de movimentações, depósitos e eventos de status.

---

## 2. Arquitetura do Projeto

O projeto segue a separação em camadas unidirecionais estabelecida no Bootcamp QI Tech:

$$\text{Middlewares} \longrightarrow \text{Schemas (JSON Schema)} \longrightarrow \text{Resources} \longrightarrow \text{Controllers} \longrightarrow \text{Repositories} \longrightarrow \text{Models (SQLAlchemy)}$$

Na volta da requisição:
$$\text{Models} \longrightarrow \text{DTOs (Data Transfer Objects)} \longrightarrow \text{JSON Response}$$

```
src/
├── app.py                     # Montagem da aplicação e registro de rotas
├── constants.py               # Variáveis de ambiente e constantes operacionais
├── database.py                # Engine SQLAlchemy e contexto de sessão por requisição
├── connectors/                # Comunicação com serviços externos (RestConnector)
├── controllers/               # Regras de negócio, autorização e controle de transação (commit)
├── dtos/                      # Mapeamento de objetos internos para dicionários de resposta
├── errors/                    # Exceções de domínio e envelope padrão QI (title, desc, translation, code)
├── middlewares/               # Request ID, Logging, Sessão e Autenticação (INTERNAL / Bearer)
├── models/                    # Modelos declarativos SQLAlchemy (tabelas do banco)
├── repositories/              # Consultas, bloqueios e persistência no banco (sem commit)
├── resources/                 # Endpoints HTTP (status code, validação de schema e chamada ao controller)
├── schemas/                   # Contratos de payload em JSON Schema (Draft 7)
└── utils/                     # Utilitários (validação de CPF/CNPJ, logger, schema handler)
```

Para uma explicação detalhada das responsabilidades e regras de cada pasta, consulte [docs/como-o-projeto-e-organizado.md](docs/como-o-projeto-e-organizado.md).

---

## 3. Como Rodar a Aplicação

### Pré-requisitos
- **Docker e Docker Compose**
- **Git**
- **Python 3.11 ou 3.12** (para execução local dos testes)

### Inicialização Rápida via Docker Compose
Para subir a API e o banco de dados PostgreSQL:

```bash
docker compose up
```

A API estará disponível em:
👉 **http://localhost:3000**

Verificação de saúde (health check):
```bash
curl -i http://localhost:3000/health_check
# HTTP/1.1 204 No Content
```

---

## 4. Variáveis de Ambiente

As variáveis possuem valores padrão preenchidos para execução via Docker no `docker-compose.yml`. Para personalizar o ambiente local:

```bash
cp .env.example .env
```

| Variável | Descrição | Padrão Local |
|---|---|---|
| `APP_ENV` | Ambiente de execução (`local`, `test`, `production`) | `local` |
| `SERVICE_NAME` | Identificador do microsserviço | `banco-universitario-api` |
| `DATABASE_URL` | String de conexão SQLAlchemy PostgreSQL | `postgresql+psycopg2://bootcamp:bootcamp@localhost:5432/bootcamp` |
| `INTERNAL_TOKEN` | Token compartilhado para rotas administrativas | `default_token` |
| `API_BASE_URL` | URL base utilizada pela suíte de testes de aceitação | `http://127.0.0.1:3000` |

---

## 5. Como Rodar os Testes

Os testes são executados contra o banco e a API com isolamento transacional:

```bash
# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate

# Instalar dependências de desenvolvimento
pip install -r requirements-dev.txt

# Executar testes unitários (incluindo testes de arquitetura AST)
pytest tests/unit

# Executar suíte completa de regressão
pytest tests
```

---

## 6. Principais Endpoints e Contratos

Todos os corpos de resposta de erro seguem o envelope padrão QI Tech:
```json
{
  "title": "Registration conflict",
  "description": "A registration already exists for this CPF.",
  "translation": "Já existe um cadastro para o identificador informado.",
  "code": "QIT002002"
}
```

### 1. Criar Universidade (Administrativo)
```bash
curl -X POST http://localhost:3000/university \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Universidade de São Paulo"}'
```
*Resposta `201 Created`*: `{"university_key": "..."}`

### 2. Cadastrar Estudante (Administrativo)
```bash
curl -X POST http://localhost:3000/student \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{
    "university_key": "<UUID_UNIVERSIDADE>",
    "full_name": "Mariana Souza",
    "email": "mariana.souza@usp.br",
    "cpf": "52998224725",
    "birthdate": "2001-08-14"
  }'
```
*Resposta `201 Created`*: Retorna `CustomerDTO` com `customer_key`.

### 3. Abrir Conta (Administrativo)
```bash
curl -X POST http://localhost:3000/customer/<CUSTOMER_KEY>/account \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{}'
```
*Resposta `201 Created`*: `{"account_key": "...", "currency": "BRL", "status": "ATIVA", "created_at": "..."}`

### 4. Emitir Credencial de Aluno (Administrativo)
```bash
curl -X POST http://localhost:3000/customer/<CUSTOMER_KEY>/credential \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{}'
```
*Resposta `201 Created`*: `{"access_token": "...", "token_type": "Bearer"}`

### 5. Depósito Simulado (Administrativo)
```bash
curl -X POST http://localhost:3000/account/<ACCOUNT_KEY>/deposit \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_cents": 50000,
    "reference": "DEP-2026-09-001"
  }'
```
*Resposta `201 Created`* (ou `200 OK` na repetição idempotente).

### 6. Transferência PIX/TED (Autenticação Bearer do Estudante)
```bash
curl -X POST http://localhost:3000/transfer \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_key": "<CONTA_ORIGEM>",
    "destination_account_key": "<CONTA_DESTINO>",
    "amount_cents": 15000,
    "type": "PIX",
    "description": "Ajuda de custo",
    "idempotency_key": "TX-998811"
  }'
```
*Resposta `201 Created`* com status `CONCLUIDA` (PF) ou `PENDENTE_APROVACAO` (PJ).

### 7. Consultar Saldo e Extrato (Autenticação Bearer ou Administrativa)
```bash
# Saldo
curl http://localhost:3000/account/<ACCOUNT_KEY>/balance \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# Extrato Paginado
curl "http://localhost:3000/account/<ACCOUNT_KEY>/statement?limit=10&page=0" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

## 7. Decisões Técnicas e Financeiras

- **Estratégia de Chave Dupla**: O identificador sequencial `id` é estritamente interno e utilizado em índices e foreign keys relacionais. Todas as rotas públicas, referências em JSON e URLs operam exclusivamente com chaves UUIDv4 (`..._key`).
- **Prevenção de Deadlocks**: Em transferências financeiras simultâneas entre duas contas (ex: $A \to B$ e $B \to A$), o repositório bloqueia as linhas via `SELECT ... FOR UPDATE` ordenando os registros sempre pelo `id` numérico crescente (`order_by(Conta.id)`).
- **Idempotência**: `idempotency_key` única por conta de origem. Retentativas idênticas de rede retornam o recurso existente (`200 OK`) sem duplicar débitos.
- **Tratamento de Sessão e ACID**: O middleware `session_manager.py` gerencia o ciclo de vida da sessão via `contextvars`. O commit da transação é responsabilidade exclusiva do controller após validação integral das regras.
