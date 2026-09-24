# Validação do incremento de pagamentos

Execução em 24/09/2026, nesta cópia do projeto, em banco novo.
Ambiente: Windows, Python 3.12.14, PostgreSQL 16.15 e API real via Uvicorn.

## Resultado

**275 testes aprovados, sem falhas, erros ou testes pulados.**

| Suíte | Aprovados | Verificação |
|---|---:|---|
| Aceitação | 81 | Contratos por HTTP e dados criados pela API |
| Integração | 64 | PostgreSQL real, constraints, reconciliação e rollback |
| Unitária | 130 | Regras isoladas, DTOs, controllers, schemas e camadas |

A aceitação também foi executada sozinha em outro banco novo:
**81 aprovados, sem avisos**.

A regressão completa apresentou dois avisos de depreciação das dependências
Starlette/httpx e AnyIO usadas pelo TestClient. Não foram suprimidos.
Eles não apareceram na execução exclusivamente HTTP.

## Reprodução e evidência local

Com as dependências de `requirements-dev.txt` e binários PostgreSQL disponíveis:

```text
python scripts/verify_local.py --postgres-bin "<diretório bin do PostgreSQL>" tests
python scripts/verify_local.py --postgres-bin "<diretório bin do PostgreSQL>" tests/acceptance
```

Relatórios JUnit e logs desta execução:

- Completa: `.local/verification-b31ce6a46d26/results.xml`.
- Aceitação isolada: `.local/verification-416e5251d63f/results.xml`.

Esses artefatos são locais e ignorados pelo Git. O script cria novos relatórios
a cada execução e encerra sua API e seu PostgreSQL ao terminar. Os bancos
descartáveis desta rodada foram removidos após o encerramento; logs e relatórios
foram preservados. Executar o script novamente recria os dados de teste. O primeiro ensaio
foi impedido pelo sandbox do Windows; os resultados acima são da execução
autorizada fora dele, sem tocar em bancos existentes.

## Cenários cobertos

- PF sem vínculo organizacional transfere e não paga tarifa, inclusive após três TEDs.
- PJ TED cobra 1%, com arredondamento inteiro e teto de 999 centavos; PIX é gratuito.
- Saldo inclui valor e tarifa; destino recebe o valor e a conta interna recebe a tarifa.
- Saldo de cada conta reconcilia com seus movimentos.
- Falha induzida no crédito desfaz toda a transferência, incluindo o débito.
- Repetição idempotente, inclusive simultânea, não duplica transferências ou depósitos.
- Débitos concorrentes não gastam mais que o saldo disponível.
- Transferências em sentidos opostos concluem sem deadlock no cenário testado.
- Solicitante não aprova a própria transferência; cargo não concede aprovação.
- Aprovação sem saldo é preservada; execução posterior não duplica movimentos.
- Aprovação revogada não permite executar enquanto a designação estiver revogada.
- Token rotacionado é invalidado e só seu hash é armazenado.
- Conta alheia e rotas administrativas recusam a credencial de um aluno sem permissão.
- PJ, aluno inativo e cadastro incompleto não recebem credencial individual.
- E-mail da organização é obrigatório, normalizado e único sem diferença entre maiúsculas e minúsculas.
- Bearer não verificado não acessa as rotas legadas de `sample_entity`.
- Histórico financeiro rejeita UPDATE/DELETE; especialização incompatível é recusada.
- Extrato preenchido aceita paginação por cursor sem repetir itens após novo movimento.
- Créditos acima do BIGINT são recusados sem alterar saldos.
- JSON Schemas passam por `Draft7Validator.check_schema`; dependências entre camadas
  e separação de SQL/HTTP são verificadas pelos testes de arquitetura.

## Correção encontrada na preparação

A recusa de emissão de credencial usava `BankingAccessDenied` sem importá-lo.
Quatro testes de regressão reproduziram o `NameError` antes da correção. A
importação foi corrigida e foram adicionadas verificações por HTTP e PostgreSQL:
retorno 403 para PJ/inativos e preservação da credencial anterior após recusa.

As respostas de credencial e configuração de acesso agora passam por `AccessDTO`.
A política de permissões, as tarifas e os contratos HTTP não foram ampliados.

## Pendências antes de considerar a entrega final validada

- Executar o build e as duas suítes Docker/Linux do [workflow](../.github/workflows/tests.yml).
  Docker não está disponível neste host; testes Windows não comprovam esses passos.
- Revisar as regras com o grupo e finalizar a apresentação em PDF.
- Se houver dados da Aula 2 a preservar, planejar uma migração: a validação acima
  inicializa um banco vazio, não atualiza volumes existentes.

Testes aprovados não demonstram ausência de qualquer defeito ou segurança de produção.
PIX/TED e depósitos continuam simulados. Login, expiração de token, MFA, integração
externa, investimentos e rendimento não fazem parte deste incremento.
