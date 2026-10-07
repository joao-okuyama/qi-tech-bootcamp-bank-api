-- No modelo bancário, todos os valores monetários são armazenados em centavos.

CREATE TABLE universidade(
    id                              BIGSERIAL PRIMARY KEY,
    chave                           UUID NOT NULL DEFAULT gen_random_uuid(),
    nome                            VARCHAR(255) NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unico_universidade_chave UNIQUE (chave),
    CONSTRAINT unico_universidade_nome UNIQUE (nome)
);

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

CREATE TABLE cliente(
    id                              BIGSERIAL PRIMARY KEY,
    chave                           UUID NOT NULL DEFAULT gen_random_uuid(),
    tipo                            VARCHAR(30) NOT NULL,
    status_id                       INTEGER NOT NULL DEFAULT 1 REFERENCES status_cliente(id) ON DELETE RESTRICT,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unico_cliente_chave UNIQUE (chave),
    CONSTRAINT unico_cliente_id_tipo UNIQUE (id, tipo),
    CONSTRAINT verifica_cliente_tipo CHECK (
        tipo IN ('ALUNO', 'ORGANIZACAO_ESTUDANTIL')
    )
);

CREATE TABLE aluno(
    cliente_id                      BIGINT PRIMARY KEY,
    tipo                            VARCHAR(30) GENERATED ALWAYS AS ('ALUNO'::VARCHAR) STORED,
    universidade_id                 BIGINT NOT NULL,
    nome_completo                   VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    cpf                             CHAR(11) NOT NULL,
    data_nascimento                 DATE NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_aluno_cliente FOREIGN KEY (cliente_id, tipo)
        REFERENCES cliente(id, tipo) ON DELETE RESTRICT,
    CONSTRAINT fk_aluno_universidade FOREIGN KEY (universidade_id)
        REFERENCES universidade(id) ON DELETE RESTRICT,
    CONSTRAINT unico_aluno_email UNIQUE (email),
    CONSTRAINT unico_aluno_cpf UNIQUE (cpf),
    CONSTRAINT verifica_aluno_cpf CHECK (cpf ~ '^[0-9]{11}$')
);

CREATE TABLE organizacao_estudantil(
    cliente_id                      BIGINT PRIMARY KEY,
    tipo                            VARCHAR(30) GENERATED ALWAYS AS ('ORGANIZACAO_ESTUDANTIL'::VARCHAR) STORED,
    universidade_id                 BIGINT NOT NULL,
    razao_social                    VARCHAR(255) NOT NULL,
    nome_fantasia                   VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    cnpj                            CHAR(14) NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_organizacao_cliente FOREIGN KEY (cliente_id, tipo)
        REFERENCES cliente(id, tipo) ON DELETE RESTRICT,
    CONSTRAINT fk_organizacao_universidade FOREIGN KEY (universidade_id)
        REFERENCES universidade(id) ON DELETE RESTRICT,
    CONSTRAINT unico_organizacao_cnpj UNIQUE (cnpj),
    CONSTRAINT verifica_organizacao_cnpj CHECK (cnpj ~ '^[A-Z0-9]{12}[0-9]{2}$')
);

CREATE TABLE vinculo_organizacao(
    id                              BIGSERIAL PRIMARY KEY,
    chave                           UUID NOT NULL DEFAULT gen_random_uuid(),
    organizacao_cliente_id          BIGINT NOT NULL,
    aluno_cliente_id                BIGINT NOT NULL,
    papel                           VARCHAR(20) NOT NULL,
    inicio_vigencia                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fim_vigencia                    TIMESTAMPTZ NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_vinculo_organizacao FOREIGN KEY (organizacao_cliente_id)
        REFERENCES organizacao_estudantil(cliente_id) ON DELETE RESTRICT,
    CONSTRAINT fk_vinculo_aluno FOREIGN KEY (aluno_cliente_id)
        REFERENCES aluno(cliente_id) ON DELETE RESTRICT,
    CONSTRAINT unico_vinculo_chave UNIQUE (chave),
    CONSTRAINT verifica_vinculo_papel CHECK (
        papel IN ('MEMBRO', 'TESOUREIRO', 'PRESIDENTE', 'VICE_PRESIDENTE')
    ),
    CONSTRAINT verifica_vinculo_vigencia CHECK (
        fim_vigencia IS NULL OR fim_vigencia >= inicio_vigencia
    )
);

-- Um aluno não pode ter dois vínculos ativos com a mesma organização.
CREATE UNIQUE INDEX unico_vinculo_organizacao_ativo
    ON vinculo_organizacao (organizacao_cliente_id, aluno_cliente_id)
    WHERE fim_vigencia IS NULL;

CREATE TABLE conta(
    id                              BIGSERIAL PRIMARY KEY,
    chave                           UUID NOT NULL DEFAULT gen_random_uuid(),
    cliente_id                      BIGINT NULL,
    finalidade                      VARCHAR(20) NOT NULL DEFAULT 'CLIENTE',
    saldo_centavos                  BIGINT NOT NULL DEFAULT 0,
    moeda                           CHAR(3) NOT NULL DEFAULT 'BRL',
    status_id                       INTEGER NOT NULL DEFAULT 1 REFERENCES status_conta(id) ON DELETE RESTRICT,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_conta_cliente FOREIGN KEY (cliente_id)
        REFERENCES cliente(id) ON DELETE RESTRICT,
    CONSTRAINT unico_conta_chave UNIQUE (chave),
    CONSTRAINT unico_conta_cliente UNIQUE (cliente_id),
    CONSTRAINT verifica_conta_finalidade CHECK (
        (finalidade = 'CLIENTE' AND cliente_id IS NOT NULL)
        OR (finalidade = 'RECEITA_TARIFAS' AND cliente_id IS NULL)
    ),
    CONSTRAINT verifica_conta_saldo CHECK (saldo_centavos >= 0),
    CONSTRAINT verifica_conta_moeda CHECK (moeda = 'BRL')
);

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

CREATE TABLE status_transferencia(
    id                              SERIAL PRIMARY KEY,
    codigo                          VARCHAR(30) NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unico_status_transferencia_codigo UNIQUE (codigo)
);

CREATE UNIQUE INDEX unico_conta_receita ON conta (finalidade)
    WHERE finalidade = 'RECEITA_TARIFAS';

-- Conta interna sem CPF/CNPJ fictício; não pode ser destino de transferências.
INSERT INTO conta (finalidade) VALUES ('RECEITA_TARIFAS');

INSERT INTO evento_status_conta (conta_id, status_id, motivo)
SELECT id, status_id, 'Criacao da conta interna de tarifas' FROM conta WHERE finalidade = 'RECEITA_TARIFAS';

CREATE TABLE credencial_aluno(
    aluno_cliente_id BIGINT PRIMARY KEY REFERENCES aluno(cliente_id) ON DELETE RESTRICT,
    resumo_token CHAR(64) NOT NULL UNIQUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE designacao_aprovador(
    id BIGSERIAL PRIMARY KEY,
    organizacao_cliente_id BIGINT NOT NULL REFERENCES organizacao_estudantil(cliente_id) ON DELETE RESTRICT,
    aluno_cliente_id BIGINT NOT NULL REFERENCES aluno(cliente_id) ON DELETE RESTRICT,
    inicio_vigencia TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fim_vigencia TIMESTAMPTZ NULL,
    CONSTRAINT verifica_designacao_vigencia CHECK (
        fim_vigencia IS NULL OR fim_vigencia >= inicio_vigencia
    )
);

CREATE UNIQUE INDEX unico_designacao_ativa
    ON designacao_aprovador (organizacao_cliente_id, aluno_cliente_id)
    WHERE fim_vigencia IS NULL;

INSERT INTO status_transferencia (codigo) VALUES
('CRIADA'),
('PENDENTE_APROVACAO'),
('APROVADA'),
('RECUSADA'),
('PROCESSANDO'),
('CONCLUIDA'),
('FALHOU');

-- O solicitante identifica quem operou a conta, mesmo quando ela pertence
-- a uma organização estudantil.
CREATE TABLE transferencia(
    id                              BIGSERIAL PRIMARY KEY,
    chave                           UUID NOT NULL DEFAULT gen_random_uuid(),
    conta_origem_id                 BIGINT NOT NULL,
    conta_destino_id                BIGINT NOT NULL,
    aluno_solicitante_cliente_id    BIGINT NOT NULL,
    aluno_aprovador_cliente_id      BIGINT NULL REFERENCES aluno(cliente_id) ON DELETE RESTRICT,
    valor_centavos                  BIGINT NOT NULL,
    tarifa_centavos                 BIGINT NOT NULL DEFAULT 0,
    tipo                            VARCHAR(10) NOT NULL,
    descricao                       VARCHAR(255) NULL,
    status_id                       INTEGER NOT NULL,
    chave_idempotencia              VARCHAR(255) NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    concluido_em                    TIMESTAMPTZ NULL,
    CONSTRAINT fk_transferencia_conta_origem FOREIGN KEY (conta_origem_id)
        REFERENCES conta(id) ON DELETE RESTRICT,
    CONSTRAINT fk_transferencia_conta_destino FOREIGN KEY (conta_destino_id)
        REFERENCES conta(id) ON DELETE RESTRICT,
    CONSTRAINT fk_transferencia_aluno_solicitante
        FOREIGN KEY (aluno_solicitante_cliente_id)
        REFERENCES aluno(cliente_id) ON DELETE RESTRICT,
    CONSTRAINT fk_transferencia_status FOREIGN KEY (status_id)
        REFERENCES status_transferencia(id) ON DELETE RESTRICT,
    CONSTRAINT unico_transferencia_chave UNIQUE (chave),
    CONSTRAINT unico_transferencia_idempotencia
        UNIQUE (conta_origem_id, chave_idempotencia),
    CONSTRAINT verifica_transferencia_contas_diferentes CHECK (
        conta_origem_id <> conta_destino_id
    ),
    CONSTRAINT verifica_transferencia_valor CHECK (valor_centavos > 0),
    CONSTRAINT verifica_transferencia_tarifa CHECK (tarifa_centavos >= 0),
    CONSTRAINT verifica_transferencia_autoaprovacao CHECK (
        aluno_aprovador_cliente_id IS NULL
        OR aluno_aprovador_cliente_id <> aluno_solicitante_cliente_id
    ),
    CONSTRAINT verifica_transferencia_tipo CHECK (
        tipo IN ('PIX', 'TED')
    ),
    CONSTRAINT verifica_transferencia_conclusao CHECK (
        concluido_em IS NULL OR concluido_em >= criado_em
    )
);

CREATE TABLE deposito(
    id BIGSERIAL PRIMARY KEY,
    chave UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    conta_id BIGINT NOT NULL REFERENCES conta(id) ON DELETE RESTRICT,
    referencia VARCHAR(255) NOT NULL UNIQUE,
    valor_centavos BIGINT NOT NULL CHECK (valor_centavos > 0),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- O saldo e suas movimentações devem ser gravados na mesma transação do banco.
CREATE TABLE movimentacao_conta(
    id                              BIGSERIAL PRIMARY KEY,
    chave                           UUID NOT NULL DEFAULT gen_random_uuid(),
    conta_id                        BIGINT NOT NULL,
    transferencia_id               BIGINT NULL,
    deposito_id                    BIGINT NULL UNIQUE REFERENCES deposito(id) ON DELETE RESTRICT,
    tipo                            VARCHAR(20) NOT NULL,
    valor_centavos                  BIGINT NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_movimentacao_conta FOREIGN KEY (conta_id)
        REFERENCES conta(id) ON DELETE RESTRICT,
    CONSTRAINT fk_movimentacao_transferencia FOREIGN KEY (transferencia_id)
        REFERENCES transferencia(id) ON DELETE RESTRICT,
    CONSTRAINT unico_movimentacao_chave UNIQUE (chave),
    CONSTRAINT unico_movimentacao_transferencia_tipo
        UNIQUE (transferencia_id, conta_id, tipo),
    CONSTRAINT verifica_movimentacao_tipo CHECK (
        tipo IN ('APORTE_INICIAL', 'DEPOSITO', 'DEBITO', 'CREDITO', 'TARIFA', 'RECEITA_TARIFA')
    ),
    CONSTRAINT verifica_movimentacao_valor CHECK (valor_centavos > 0),
    CONSTRAINT verifica_movimentacao_origem CHECK (
        (tipo = 'APORTE_INICIAL' AND transferencia_id IS NULL AND deposito_id IS NULL)
        OR
        (tipo = 'DEPOSITO' AND transferencia_id IS NULL AND deposito_id IS NOT NULL)
        OR
        (tipo IN ('DEBITO', 'CREDITO', 'TARIFA', 'RECEITA_TARIFA')
            AND transferencia_id IS NOT NULL AND deposito_id IS NULL)
    )
);

CREATE INDEX indice_movimentacao_extrato
    ON movimentacao_conta (conta_id, criado_em DESC, id DESC);

CREATE TABLE evento_status_transferencia(
    id                              BIGSERIAL PRIMARY KEY,
    transferencia_id               BIGINT NOT NULL,
    status_id                       INTEGER NOT NULL,
    aluno_responsavel_cliente_id    BIGINT NULL,
    ocorrido_em                     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_evento_transferencia FOREIGN KEY (transferencia_id)
        REFERENCES transferencia(id) ON DELETE RESTRICT,
    CONSTRAINT fk_evento_status FOREIGN KEY (status_id)
        REFERENCES status_transferencia(id) ON DELETE RESTRICT,
    CONSTRAINT fk_evento_aluno_responsavel
        FOREIGN KEY (aluno_responsavel_cliente_id)
        REFERENCES aluno(cliente_id) ON DELETE RESTRICT
);

CREATE TABLE empresas_bet_autorizadas(
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

CREATE INDEX indice_evento_status_transferencia
    ON evento_status_transferencia (transferencia_id, ocorrido_em, id);

CREATE FUNCTION impedir_alteracao_historico() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Histórico financeiro permite somente inclusão';
END;
$$;

CREATE TRIGGER preservar_movimentacao BEFORE UPDATE OR DELETE ON movimentacao_conta
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_historico();
CREATE TRIGGER preservar_evento BEFORE UPDATE OR DELETE ON evento_status_transferencia
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_historico();
CREATE TRIGGER preservar_deposito BEFORE UPDATE OR DELETE ON deposito
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_historico();
CREATE TRIGGER preservar_evento_cliente BEFORE UPDATE OR DELETE ON evento_status_cliente
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_historico();
CREATE TRIGGER preservar_evento_conta BEFORE UPDATE OR DELETE ON evento_status_conta
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_historico();
