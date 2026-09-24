# Pagamentos: contratos e decisões

## Objetivo e escopo

Uma API para alunos e organizações estudantis. Um aluno pode abrir e usar sua
conta sem pertencer a qualquer organização. Cada CPF/CNPJ possui no máximo uma
conta. Nesta versão, PIX/TED são operações simuladas entre contas deste banco:
não há integração com SPI, STR, bancos externos ou dinheiro real.

O fluxo preserva as camadas do projeto: middleware → JSON Schema → Resource →
Controller → Repository → Model; DTOs definem a resposta. O controller confirma
a transação, o repository não faz commit e o middleware desfaz falhas.

| Critério obrigatório | Implementação e demonstração |
|---|---|
| Cadastro de cliente | POST /student e /student_organization; documentos e e-mails válidos e únicos |
| Conta vinculada ao cliente | POST /customer/{customer_key}/account; saldo inicial zero, uma conta por cliente |
| Transação com controle de saldo | POST /transfer; débito/crédito atômicos, bloqueios ordenados e idempotência |
| Tarifa na transferência | PJ TED: 1%, máximo 999 centavos; crédito rastreável na conta interna de receita |
| Extrato paginado | GET /account/{account_key}/statement; movimentos reais, paginação por página ou cursor |

## Identidade e autorização

INTERNAL-TOKEN é um segredo administrativo: cadastra clientes, abre contas,
provisiona/rotaciona credenciais, configura organizações e registra depósitos
simulados. Mantém acesso administrativo de leitura para compatibilidade com o
starter e testes. Quem possui esse segredo é um operador privilegiado.

POST /customer/{customer_key}/credential, com corpo {}, emite um token opaco
para um aluno ativo. A resposta contém access_token e token_type. O token aparece
uma única vez; só seu SHA-256 fica no banco. Emitir outro invalida o anterior.
Não existe login por CPF nem autorização obtida enviando o ID de outro aluno.

O estudante envia Authorization: Bearer <token> para consultar sua conta ou
solicitar transferências. Pode ler contas organizacionais das quais é membro
ativo. Não pode acessar as rotas administrativas, nem mesmo acrescentando um
INTERNAL-TOKEN junto ao Bearer. A emissão de credencial de PJ é recusada.

Esta identidade simulada não substitui autenticação de produção: faltam login,
expiração automática, MFA, limitação de tentativas e recuperação de conta.
Não exponha este ambiente à internet nem use dados pessoais reais.

## Contratos adicionados

| Método e rota | Credencial | Corpo e resultado |
|---|---|---|
| POST /customer/{key}/credential | Administrativa | {}; 201 com novo token |
| PUT /customer/{key}/banking_access | Administrativa | members e approvers; 200 |
| POST /account/{key}/deposit | Administrativa | amount_cents, reference; 201, ou 200 no replay |
| POST /transfer | Bearer | Contrato abaixo; 201, ou 200 no replay |
| GET /transfer/{key} | Bearer | Titular/membro de uma das contas; 200 |
| POST /transfer/{key}/approve | Bearer | {}; 200 com status resultante |
| POST /transfer/{key}/reject | Bearer | {}; 200, status RECUSADA |
| POST /transfer/{key}/execute | Bearer | {}; retoma APROVADA, 200 |

Corpo de uma transferência:

```json
{
  "source_account_key": "<UUID da conta de origem>",
  "destination_account_key": "<UUID da conta de destino>",
  "amount_cents": 10000,
  "type": "TED",
  "description": "Material para o evento",
  "idempotency_key": "<identificador estável desta solicitação>"
}
```

description é opcional/nula. Campos adicionais, inclusive solicitante, tarifa,
status e aprovador, são rejeitados. A identidade vem da credencial; tarifa e
estado são calculados pelo servidor. Valores monetários devem ser inteiros reais
no JSON: 100 é aceito, 100.0 não. O limite é o BIGINT positivo de 64 bits.

A chave de idempotência é única por conta de origem. Repetir a mesma operação com
a mesma chave devolve a transferência existente; mudar destino, valor, tipo,
descrição ou solicitante produz 409. Uma chave nova representa outra ordem, mesmo
com valor e destino iguais. O consumidor deve guardar e reutilizar a chave em
retentativas de rede; não é uma proteção contra um usuário autorizado criando
intencionalmente novas ordens.

Erros seguem o envelope QI: 400 para schema/UUID/parâmetro, 403 para autorização,
404 para recurso inexistente, 409 para conflito ou saldo insuficiente e 422 para
operação inválida. Falha inesperada retorna 500 genérico, sem SQL ou dados pessoais.

## Política financeira

- PF: PIX e todas as TEDs gratuitas, sem franquia mensal.
- PJ: PIX gratuito; TED com 1% do valor, limitado a R$9,99.
- Cálculo exclusivamente inteiro: meio centavo arredonda para cima. Uma tarifa
  calculada como zero não gera movimentação de tarifa.
- Saldo suficiente significa valor + tarifa. Destino recebe somente o valor.
- A tarifa debita a origem e credita uma conta interna de receita, sem inventar
  um CPF/CNPJ de cliente. Essa conta não aceita depósitos nem transferências
  comuns. Nesta versão não há endpoint de consulta da conta interna; sua
  reconciliação é verificada pelos testes de integração.
- Origem, destino e clientes precisam estar ativos; origem e destino distintos.
- Aprovações pendentes não reservam dinheiro. Saldo e permissões são revalidados
  na execução. Não há fila global que ordene todas as transferências do banco.

O saldo, os movimentos, o status e seus eventos são confirmados juntos. As contas
são bloqueadas por ID crescente, inclusive em transferências em sentidos opostos.
A conta de receita é bloqueada depois das contas dos clientes. O CHECK de saldo
não negativo continua como última barreira, sem substituir o bloqueio transacional.
Créditos acima do limite BIGINT são recusados antes de alterar o saldo.

## Aprovação organizacional

PUT /customer/{key}/banking_access recebe:

```json
{
  "members": [
    {"customer_key": "<aluno A>", "role": "PRESIDENTE"},
    {"customer_key": "<aluno B>", "role": "MEMBRO"}
  ],
  "approvers": ["<aluno A>", "<aluno B>"]
}
```

Há pelo menos dois membros diferentes e exatamente dois aprovadores designados,
ambos alunos ativos e membros. O cargo não concede autoridade automaticamente:
um MEMBRO designado pode aprovar; um PRESIDENTE não designado não pode.
As alterações encerram as vigências anteriores, preservando o histórico.
Os cargos disponíveis são MEMBRO, TESOUREIRO, PRESIDENTE e VICE_PRESIDENTE.
Configuração e transferência compartilham o bloqueio do cliente organizacional.

Qualquer membro ativo pode solicitar e consultar o extrato. A execução sempre
exige outra pessoa: se A solicita, apenas B aprova; se um terceiro membro solicita,
A ou B aprova. São dois aprovadores disponíveis, não duas aprovações obrigatórias
por transferência. Mudança na lista exige nova verificação de autoridade.

```text
PF: CRIADA → PROCESSANDO → CONCLUIDA
PJ: CRIADA → PENDENTE_APROVACAO → RECUSADA
                              → APROVADA → PROCESSANDO → CONCLUIDA
```

Se faltar saldo, a aprovação permanece APROVADA e não há movimento financeiro.
Após receber fundos, o solicitante ou aprovador registrado pode chamar /execute.
É necessário que o solicitante ainda seja membro ativo e o aprovador continue
designado. Uma aprovação de alguém removido não é reutilizada. Nesta versão,
esse caso requer nova solicitação e aprovação; não há edição do payload aprovado.

Repetir aprovação/execução não duplica movimentos. RECUSADA é terminal. Falhas
antes do commit desfazem a transação; a API não promete gravar FALHOU em uma
transação que foi integralmente revertida.

## Depósitos e extrato

O depósito representa uma liquidação simulada comunicada por um operador
administrativo, não uma permissão para o aluno inventar saldo. reference identifica
o recebimento externo e é única globalmente. Mesmo valor/conta/referência retorna
o mesmo depósito; uma reutilização diferente retorna 409. Repetições simultâneas
são serializadas por essa referência e pela conta. Depósito e crédito no extrato
são confirmados juntos.

Integração real precisaria autenticar o provedor, verificar liquidação, moeda,
unidade monetária e conciliar eventos. Ela não está implementada.

GET /account/{key}/statement?limit=20&page=0 mantém o contrato antigo.
O offset máximo continua 10000. Quando houver outra página, next_cursor contém
a chave do último movimento retornado; use ?limit=20&cursor=<next_cursor>.
Não combine page e cursor. O cursor deve pertencer à conta consultada.
A ordem é criado_em DESC, id DESC. Novos movimentos não deslocam as páginas
seguintes do percurso por cursor; eles aparecem em uma nova consulta inicial.

## Integridade e limites do banco

O tipo gerado nas tabelas aluno/organizacao_estudantil participa da FK composta
com cliente: não se pode cadastrar uma especialização incompatível com o pai.
O fluxo de cadastro cria pai e especialização na mesma transação; isso não impede
um administrador SQL de criar manualmente um pai sem especialização.

Movimentos, eventos de status e depósitos rejeitam UPDATE/DELETE por gatilhos.
Não é uma promessa de inviolabilidade contra o proprietário/superusuário do banco:
ele pode alterar estruturas. A aplicação não possui rotas para editar o histórico.
Extrato não é um livro contábil completo de uma instituição financeira.

database.sql inicializa somente um banco vazio. Esta versão altera o DDL:
um volume existente não será atualizado automaticamente. Para validar sem perder
dados, use os composes de teste abaixo. Não execute down -v em uma base a preservar.
Migração de uma base existente fica fora deste pacote.

## Execução e verificação

Todos os testes abaixo usam dados fictícios. A aceitação é caixa-preta: requests
contra a API real, sem importar src, sem SQL nem credencial de banco.
pytest sem argumentos executa somente essa suíte.

```bash
docker compose up --build
pip install -r requirements-acceptance.txt
pytest
```

Aceitação isolada e regressão completa, cada uma com PostgreSQL novo:

```bash
docker compose -p banco-acceptance -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
docker compose -p banco-regression -f docker-compose.test.yml -f docker-compose.regression.yml up --build --abort-on-container-exit --exit-code-from tests
```

A regressão adicional acessa SQL para testar constraints, saldo versus movimentos
e falha induzida no meio da transação. Ela exige APP_ENV=test,
ALLOW_TEST_DATABASE_RESET=1 e banco com sufixo _test. Não execute em dados reais.
Os testes não devem rodar em paralelo entre arquivos: a regressão do starter
recria o schema. Os testes específicos de concorrência coordenam suas próprias
requisições simultâneas.

Alternativa de validação local, com binários PostgreSQL já disponíveis e as
dependências de requirements-dev.txt:

```text
python scripts/verify_local.py --postgres-bin "<diretório bin do PostgreSQL>" tests
```

O script cria um banco exclusivo em .local, publica apenas em 127.0.0.1,
escolhe portas livres, executa testes e encerra seus processos. Não instala
serviço nem altera outro banco. Logs e JUnit ficam nesse diretório ignorado
por Git/Docker. No Windows, o sandbox do executor pode impedir pg_ctl de iniciar.
Os resultados estão em [validacao.md](validacao.md).

## Adiado

Integração real PIX/TED, bets, comissão de formatura, investimentos, pagamentos
recorrentes, verificação externa de matrícula/e-mail e autenticação de produção.
Não foram adicionados serviços, filas ou cron jobs para esses produtos.
O grupo ainda precisa finalizar a apresentação em PDF e validar o build Linux/Docker
antes da entrega. Ter testes locais aprovados não comprova esses dois itens.
