-- Aplicar uma unica vez ao banco da versao 3abaacb, com a API parada e backup validado.
BEGIN;

CREATE TABLE status_cliente(
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE
);

INSERT INTO status_cliente (id, codigo) VALUES
(1, 'ATIVO'), (2, 'BLOQUEADO'), (3, 'ENCERRADO');
SELECT setval(pg_get_serial_sequence('status_cliente', 'id'), 3);

CREATE TABLE status_conta(
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE
);

INSERT INTO status_conta (id, codigo) VALUES
(1, 'ATIVA'), (2, 'BLOQUEADA'), (3, 'ENCERRADA');
SELECT setval(pg_get_serial_sequence('status_conta', 'id'), 3);


ALTER TABLE cliente ADD COLUMN status_id INTEGER;
UPDATE cliente c SET status_id = s.id FROM status_cliente s WHERE s.codigo = c.situacao;
ALTER TABLE cliente ALTER COLUMN status_id SET NOT NULL;
ALTER TABLE cliente ALTER COLUMN status_id SET DEFAULT 1;
ALTER TABLE cliente ADD CONSTRAINT cliente_status_id_fkey
    FOREIGN KEY (status_id) REFERENCES status_cliente(id) ON DELETE RESTRICT;
ALTER TABLE cliente DROP COLUMN situacao;

ALTER TABLE conta ADD COLUMN status_id INTEGER;
UPDATE conta c SET status_id = s.id FROM status_conta s WHERE s.codigo = c.situacao;
ALTER TABLE conta ALTER COLUMN status_id SET NOT NULL;
ALTER TABLE conta ALTER COLUMN status_id SET DEFAULT 1;
ALTER TABLE conta ADD CONSTRAINT conta_status_id_fkey
    FOREIGN KEY (status_id) REFERENCES status_conta(id) ON DELETE RESTRICT;
ALTER TABLE conta DROP COLUMN situacao;

CREATE TABLE evento_status_cliente(
    id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL REFERENCES cliente(id) ON DELETE RESTRICT,
    status_anterior_id INTEGER NULL REFERENCES status_cliente(id) ON DELETE RESTRICT,
    status_id INTEGER NOT NULL REFERENCES status_cliente(id) ON DELETE RESTRICT,
    aluno_responsavel_cliente_id BIGINT NULL REFERENCES aluno(cliente_id) ON DELETE RESTRICT,
    motivo VARCHAR(255) NOT NULL,
    ocorrido_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX indice_evento_cliente ON evento_status_cliente (cliente_id, ocorrido_em, id);

CREATE TABLE evento_status_conta(
    id BIGSERIAL PRIMARY KEY,
    conta_id BIGINT NOT NULL REFERENCES conta(id) ON DELETE RESTRICT,
    status_anterior_id INTEGER NULL REFERENCES status_conta(id) ON DELETE RESTRICT,
    status_id INTEGER NOT NULL REFERENCES status_conta(id) ON DELETE RESTRICT,
    aluno_responsavel_cliente_id BIGINT NULL REFERENCES aluno(cliente_id) ON DELETE RESTRICT,
    motivo VARCHAR(255) NOT NULL,
    ocorrido_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX indice_evento_conta ON evento_status_conta (conta_id, ocorrido_em, id);


-- Nao inventa transicoes anteriores: registra somente o estado observado na migracao.
INSERT INTO evento_status_cliente (cliente_id, status_id, motivo)
SELECT id, status_id, 'Estado observado na migracao; historico anterior indisponivel' FROM cliente;
INSERT INTO evento_status_conta (conta_id, status_id, motivo)
SELECT id, status_id, 'Estado observado na migracao; historico anterior indisponivel' FROM conta;

CREATE TABLE IF NOT EXISTS empresas_bet_autorizadas(
    id                              SERIAL PRIMARY KEY,
    cnpj                            CHAR(14) NOT NULL,
    razao_social                    VARCHAR(255) NOT NULL,

    CONSTRAINT unico_bet_cnpj UNIQUE (cnpj),
    CONSTRAINT verifica_bet_cnpj CHECK (cnpj ~ '^[A-Z0-9]{12}[0-9]{2}$')
);

-- A linha unica coordena a leitura das transferencias com a substituicao da lista.
CREATE TABLE sincronizacao_empresas_bet(
    id INTEGER PRIMARY KEY CHECK (id = 1),
    atualizado_em TIMESTAMPTZ NULL,
    resumo_conteudo CHAR(64) NULL,
    quantidade INTEGER NOT NULL DEFAULT 0 CHECK (quantidade >= 0),
    CONSTRAINT verifica_sincronizacao_bet CHECK (
        (atualizado_em IS NULL AND resumo_conteudo IS NULL AND quantidade = 0)
        OR (atualizado_em IS NOT NULL AND resumo_conteudo IS NOT NULL AND quantidade > 0)
    )
);

INSERT INTO sincronizacao_empresas_bet (id) VALUES (1);


CREATE TRIGGER preservar_evento_cliente BEFORE UPDATE OR DELETE ON evento_status_cliente
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_historico();
CREATE TRIGGER preservar_evento_conta BEFORE UPDATE OR DELETE ON evento_status_conta
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_historico();

COMMIT;
