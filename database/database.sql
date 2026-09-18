CREATE TABLE sample_entity_status(
    id		                        SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO sample_entity_status (enumerator) VALUES
('created'),
('pending'),
('success'),
('failed');

CREATE TABLE sample_entity(
    id                              SERIAL PRIMARY KEY,
    sample_entity_key               CHAR(36) NOT NULL,
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    sample_entity_data              JSONB NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    birthdate                       DATE NOT NULL,
    counter                         INTEGER NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(sample_entity_key),
    UNIQUE(document_number),
    UNIQUE(email)
);

CREATE TABLE sample_entity_status_event(
    id                              SERIAL PRIMARY KEY,
    sample_entity_id                INTEGER NOT NULL REFERENCES sample_entity(id),
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    event_datetime                  TIMESTAMP NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW())
);

-- As tabelas de exemplo acima foram mantidas para não quebrar o projeto base.
-- No modelo bancário, todos os valores monetários são armazenados em centavos.

CREATE TABLE universidade(
    id                              BIGSERIAL PRIMARY KEY,
    chave                           UUID NOT NULL DEFAULT gen_random_uuid(),
    nome                            VARCHAR(255) NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unico_universidade_chave UNIQUE (chave),
    CONSTRAINT unico_universidade_nome UNIQUE (nome)
);

CREATE TABLE cliente(
    id                              BIGSERIAL PRIMARY KEY,
    chave                           UUID NOT NULL DEFAULT gen_random_uuid(),
    tipo                            VARCHAR(30) NOT NULL,
    situacao                        VARCHAR(20) NOT NULL DEFAULT 'ATIVO',
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unico_cliente_chave UNIQUE (chave),
    CONSTRAINT verifica_cliente_tipo CHECK (
        tipo IN ('ALUNO', 'ORGANIZACAO_ESTUDANTIL')
    ),
    CONSTRAINT verifica_cliente_situacao CHECK (
        situacao IN ('ATIVO', 'BLOQUEADO', 'ENCERRADO')
    )
);

CREATE TABLE aluno(
    cliente_id                      BIGINT PRIMARY KEY,
    universidade_id                 BIGINT NOT NULL,
    nome_completo                   VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    cpf                             CHAR(11) NOT NULL,
    data_nascimento                 DATE NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_aluno_cliente FOREIGN KEY (cliente_id)
        REFERENCES cliente(id) ON DELETE RESTRICT,
    CONSTRAINT fk_aluno_universidade FOREIGN KEY (universidade_id)
        REFERENCES universidade(id) ON DELETE RESTRICT,
    CONSTRAINT unico_aluno_email UNIQUE (email),
    CONSTRAINT unico_aluno_cpf UNIQUE (cpf),
    CONSTRAINT verifica_aluno_cpf CHECK (cpf ~ '^[0-9]{11}$')
);

CREATE TABLE organizacao_estudantil(
    cliente_id                      BIGINT PRIMARY KEY,
    universidade_id                 BIGINT NOT NULL,
    razao_social                    VARCHAR(255) NOT NULL,
    nome_fantasia                   VARCHAR(255) NOT NULL,
    cnpj                            CHAR(14) NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_organizacao_cliente FOREIGN KEY (cliente_id)
        REFERENCES cliente(id) ON DELETE RESTRICT,
    CONSTRAINT fk_organizacao_universidade FOREIGN KEY (universidade_id)
        REFERENCES universidade(id) ON DELETE RESTRICT,
    CONSTRAINT unico_organizacao_cnpj UNIQUE (cnpj),
    CONSTRAINT verifica_organizacao_cnpj CHECK (cnpj ~ '^[0-9]{14}$')
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
        papel IN ('MEMBRO', 'TESOUREIRO', 'PRESIDENTE')
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
    cliente_id                      BIGINT NOT NULL,
    saldo_centavos                  BIGINT NOT NULL DEFAULT 0,
    moeda                           CHAR(3) NOT NULL DEFAULT 'BRL',
    situacao                        VARCHAR(20) NOT NULL DEFAULT 'ATIVA',
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_conta_cliente FOREIGN KEY (cliente_id)
        REFERENCES cliente(id) ON DELETE RESTRICT,
    CONSTRAINT unico_conta_chave UNIQUE (chave),
    CONSTRAINT unico_conta_cliente UNIQUE (cliente_id),
    CONSTRAINT verifica_conta_saldo CHECK (saldo_centavos >= 0),
    CONSTRAINT verifica_conta_moeda CHECK (moeda = 'BRL'),
    CONSTRAINT verifica_conta_situacao CHECK (
        situacao IN ('ATIVA', 'BLOQUEADA', 'ENCERRADA')
    )
);

CREATE TABLE status_transferencia(
    id                              SERIAL PRIMARY KEY,
    codigo                          VARCHAR(30) NOT NULL,
    criado_em                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unico_status_transferencia_codigo UNIQUE (codigo)
);

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
    CONSTRAINT verifica_transferencia_tipo CHECK (
        tipo IN ('PIX', 'TED')
    ),
    CONSTRAINT verifica_transferencia_conclusao CHECK (
        concluido_em IS NULL OR concluido_em >= criado_em
    )
);

-- O saldo e suas movimentações devem ser gravados na mesma transação do banco.
CREATE TABLE movimentacao_conta(
    id                              BIGSERIAL PRIMARY KEY,
    chave                           UUID NOT NULL DEFAULT gen_random_uuid(),
    conta_id                        BIGINT NOT NULL,
    transferencia_id               BIGINT NULL,
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
        tipo IN ('APORTE_INICIAL', 'DEBITO', 'CREDITO', 'TARIFA')
    ),
    CONSTRAINT verifica_movimentacao_valor CHECK (valor_centavos > 0),
    CONSTRAINT verifica_movimentacao_origem CHECK (
        (tipo = 'APORTE_INICIAL' AND transferencia_id IS NULL)
        OR
        (tipo <> 'APORTE_INICIAL' AND transferencia_id IS NOT NULL)
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

CREATE INDEX indice_evento_status_transferencia
    ON evento_status_transferencia (transferencia_id, ocorrido_em, id);
