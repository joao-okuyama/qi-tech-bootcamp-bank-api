# Banco Universitário

API para alunos e organizações estudantis. Implementa cadastro, uma conta por
cliente, transferências internas PIX/TED, tarifas e extrato paginado. Alunos não
precisam participar de uma organização para usar sua conta.

PIX e TED são modalidades simuladas entre contas deste banco. Não há liquidação
no SPI, conexão bancária real ou envio para contas de outras instituições.

(Arquivos .png dos fluxos e ERD foram salvos nesse repositório. Para consulta, acessar "ERD.drawio.png" e " Fluxos (todos).drawio.png)

## Regras da entrega

- Valores em centavos inteiros: R$1,00 = 100.
- PF: PIX e TED gratuitos. PJ: PIX gratuito; TED de 1%, arredondado ao centavo mais
  próximo, com meio centavo para cima, limitado a 999 centavos.
- Débito, crédito, tarifa, receita do banco e histórico pertencem à mesma transação.
- Uma organização exige dois membros ou mais e exatamente dois aprovadores
  designados. Uma transferência exige um aprovador diferente do solicitante,
  não duas aprovações. Cargo institucional não concede autoridade automaticamente.
- A aprovação permanece válida quando falta saldo, mas a execução revalida
  membros, aprovador, contas e o cadastro BET.
- Chave de idempotência única por conta de origem. Repetição com o mesmo conteúdo
  retorna a operação existente; conteúdo diferente retorna 409.
- Destinos PJ com CNPJ listado no cadastro BET são bloqueados. Destinos PF não
  dependem desse cadastro.

## Arquitetura

`app.py → middlewares → schemas/resources → controllers → repositories → models/database`

Os DTOs formatam a resposta. Controllers decidem regras e fazem commit;
repositories consultam e persistem sem commit; connectors fazem HTTP externo.
Os middlewares autenticam a credencial e cuidam do contexto e rollback. A
autorização sobre cada conta é decidida no controller.

Clientes, contas e transferências guardam um `status_id` numérico. Tabelas de
status fornecem os nomes exibidos no JSON. Clientes e contas registram seu estado
inicial; transferências registram cada passo do fluxo implementado. Não existe
rota de mudança de estado de cliente/conta nesta versão.

Detalhes e caminhos dos requisitos: [organização do projeto](docs/como-o-projeto-e-organizado.md).

## Executar

```sh
docker compose up --build
```

API em http://localhost:3000. PostgreSQL persiste no volume `dados_banco`.
`GET /health_check` responde 204 e verifica somente que a API está viva.

Os valores padrão são exclusivamente de desenvolvimento, com portas vinculadas
ao localhost. Não publique esta configuração na internet. O arquivo
`.env.example` contém exemplos; não versione `.env` nem tokens reais.

### Banco existente

A inicialização SQL só roda em um volume novo. Para atualizar um banco da revisão
`3abaacb`, pare a API, valide um backup e execute uma única vez:

```sh
docker compose stop api
docker compose cp database/migrations/001_status_e_bets.sql db:/tmp/001_status_e_bets.sql
docker compose exec -T db psql -U bootcamp -d bootcamp -v ON_ERROR_STOP=1 -f /tmp/001_status_e_bets.sql
```

Depois execute `docker compose up --build -d api`. A migração preserva clientes,
email da organização, contas, saldos e histórico financeiro. Os eventos iniciais
da migração representam o estado observado, não um histórico reconstruído.
Não execute novamente `database.sql` sobre um banco existente nem apague seu
volume para aplicar essa alteração. A migração não é aplicada automaticamente.

## Atualizar o cadastro BET

Fonte configurável por `BET_REGISTRY_URL`:
[CSV oficial da SPA/MF](https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/transparencia-ativa-processos-de-autorizacao-de-apostas-de-quota-fixa/planilha-de-autorizacoes-1.csv).

`POST /bet_registry/sync`, com `INTERNAL-TOKEN` e corpo `{}`, baixa e valida
o CSV antes de substituir a tabela em uma transação. O arquivo não é gravado em
disco e não é baixado durante uma transferência. Não enviamos nosso token ao gov.br.

Para chamar pelo script, configure `INTERNAL_TOKEN` e `API_BASE_URL` no ambiente:

```sh
python scripts/sync_bet_registry.py
```

Esse comando pode ser chamado diariamente por um agendador externo. Não há
agendamento instalado automaticamente. Faça a primeira sincronização antes de
testar transferências para PJ.

Configuração:
- `BET_REGISTRY_TIMEOUT`: 20 segundos para o download.
- `BET_REGISTRY_MAX_BYTES`: 2 MiB.
- `BET_REGISTRY_MAX_AGE_HOURS`: 48 horas. É uma política operacional desta entrega,
  não uma exigência legal. Recomenda-se atualizar diariamente.

Download inválido, vazio ou falha de persistência preservam os registros e a data
do último sucesso. Uma lista ainda válida continua funcionando durante uma falha
de atualização. Sem lista válida, destinos PJ recebem 503, sem débito; PF continua
funcionando.

Uma atualização que remove CNPJs retorna 409 e o hash do novo conteúdo. Revise
o arquivo na fonte e somente depois envie `{"reviewed_sha256": "<hash revisado>"}`
ou use `--reviewed-sha256` no script. A confirmação vale somente para aquele
conteúdo. Não confirme o hash automaticamente num agendador.

O bloqueio consulta o CNPJ cadastrado do destinatário na criação e antes da
execução. A lista identifica empresas autorizadas presentes no arquivo; não
detecta todo operador ilegal, intermediário ou empresa ainda não listada.
Não é uma declaração de bloqueio legal universal.

## Autenticação e jornadas

`INTERNAL-TOKEN` é administrativo: cadastro, abertura de conta, credenciais,
depósitos simulados, configuração de membros e sincronização. Uma organização
é cadastrada por esse administrador e recebe vínculos em
`PUT /customer/{customer_key}/banking_access`; não há inferência automática do
aluno criador, pois a credencial administrativa não identifica um aluno.

O aluno recebe um token opaco em
`POST /customer/{customer_key}/credential`. O banco guarda somente seu hash.
Use `Authorization: Bearer <token>` para movimentar sua própria conta ou uma
organização onde tenha vínculo. Reemitir uma credencial invalida a anterior.
UUIDs identificam contas e operações; não substituem autenticação.

Principais rotas:

| Método / rota | Finalidade |
|---|---|
| POST /university | Cadastrar universidade |
| GET /university/{university_key} | Consultar universidade |
| POST /student | Cadastrar PF |
| POST /student_organization | Cadastrar PJ com email de contato |
| GET /customer/{customer_key} | Consultar cliente autorizado |
| POST /customer/{customer_key}/account | Abrir conta |
| POST /customer/{customer_key}/credential | Emitir/rotacionar token do aluno |
| PUT /customer/{customer_key}/banking_access | Configurar membros e dois aprovadores |
| GET /account/{account_key} | Consultar conta |
| GET /account/{account_key}/balance | Consultar saldo |
| GET /account/{account_key}/statement | Consultar extrato |
| POST /account/{account_key}/deposit | Registrar depósito simulado |
| POST /transfer | Solicitar transferência |
| GET /transfer/{transfer_key} | Consultar operação como participante autorizado |
| POST /transfer/{transfer_key}/approve | Aprovar e tentar executar |
| POST /transfer/{transfer_key}/reject | Recusar |
| POST /transfer/{transfer_key}/execute | Retomar uma operação aprovada |
| POST /bet_registry/sync | Atualizar cadastro BET |

Exemplo de transferência, usando chaves recebidas no cadastro:

```json
{
    "source_account_key": "<UUID da origem>",
    "destination_account_key": "<UUID do destino>",
    "amount_cents": 15000,
    "type": "PIX",
    "description": "Ajuda de custo",
    "idempotency_key": "operacao-001"
}
```

Descrição é opcional. PF pode concluir no POST; PJ retorna
`PENDENTE_APROVACAO`. Após aprovação sem saldo suficiente, `APROVADA` significa
aprovada, mas ainda não executada. Somente `CONCLUIDA` indica movimentação do saldo.

Extrato: `?limit=20&page=0` ou `?limit=20&cursor=<next_cursor>`.
Não combine page e cursor. O offset máximo é 10.000; use cursor para avançar
além disso. O cursor mantém a ordenação mesmo quando chegam novas movimentações.

Erros seguem `title, description, translation, code`: 400 para schema inválido,
403 para falta de permissão ou destino BET, 404 para entidade ausente, 409 para
conflito/saldo insuficiente, 422 para dados de domínio inválidos e 503 para
cadastro BET indisponível. Falhas inesperadas retornam 500 sem dados internos.

## Testar a entrega

Aceitação HTTP, PostgreSQL novo e CSV servido pelo MockServer:

```sh
docker compose -p banco-acceptance -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
```

Regressão completa, incluindo integridade SQL e migração:

```sh
docker compose -p banco-regression -f docker-compose.test.yml -f docker-compose.regression.yml up --build --abort-on-container-exit --exit-code-from tests
```

Encerre somente os projetos isolados de teste:

```sh
docker compose -p banco-acceptance -f docker-compose.test.yml down --volumes
docker compose -p banco-regression -f docker-compose.test.yml -f docker-compose.regression.yml down --volumes
```

Fora do Docker, com a API e o banco de teste configurados:
- `pytest`: aceitação HTTP, como definido em pytest.ini.
- `pytest tests/unit`: testes locais.
- `pytest tests`: regressão completa, exige banco dedicado terminado em
  `_test`, `APP_ENV=test` e `ALLOW_TEST_DATABASE_RESET=1`.
- `MOCKSERVER_URL`: endereço do MockServer controlado pelos testes;
  `BET_REGISTRY_URL` da API deve apontar para `/bets.csv` nesse mesmo servidor.

`scripts/verify_local.py --postgres-bin <pasta dos binários>` cria um PostgreSQL
descartável, inicia a API e usa um servidor HTTP local de CSV. Essa verificação
não substitui a execução Linux nem valida a imagem real do MockServer.

Os cenários verificam autorização, aprovação independente, saldo insuficiente,
idempotência, concorrência, reconciliação, rollback parcial, paginação e cadastro
BET. Os gatilhos recusam UPDATE/DELETE dos históricos; um administrador com
privilégios de DDL ainda pode alterar os gatilhos.

Antes da entrega, execute os dois projetos Compose no commit final, registre
`git rev-parse HEAD`, confirme a árvore limpa e guarde logs/CI associados ao SHA.
A publicação do repositório e a revisão da apresentação ficam a cargo do time.

## Limites

Não inclui investimentos, rendimento CDI/CDB, fundo de formatura, devoluções,
liquidação externa ou autenticação de um provedor real. Uso financeiro em produção
exigiria, entre outros controles, ciclo de vida de credenciais, permissões
restritas no banco, limites de recursos e processos de reconciliação operacional.
