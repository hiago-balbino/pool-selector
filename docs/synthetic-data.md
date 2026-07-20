# Gerador de dados sintéticos

`tools/generate_data.py` produz um dataset JSON determinístico e
reproduzível, no formato exato que `ingestion/parser.py` espera ler do S3 ou de
um diretório local. Para o uso da CLI (`--seed`, `--num-events`, `--days`,
`--output-dir`), veja a seção
[Gerando dados sintéticos](../README.md#gerando-dados-sintéticos) do README.
Este documento cobre as *regras* de geração.

## Determinismo

Toda escolha aleatória vem de uma única instância `random.Random(seed)`, numa
ordem fixa, então a mesma `--seed` sempre produz a mesma sequência de eventos
(saída idêntica byte a byte). A única entrada externa é a data-âncora "hoje"
(`as_of`, com default interno para a data UTC atual), isso **não é exposto
como flag de CLI**, então rodar o gerador em dias diferentes com a mesma seed
produz o mesmo padrão estatístico, mas datas absolutas diferentes nas
partições de saída.

## Universo de pools

9 tipos de instância × 3 zonas de disponibilidade = 27 pools, `pool_id` no
formato `pool-<instance_type>-<az>` (parseável por
`domain/models.py::PoolId.parse`):

- **Tipos de instância**: `c5.xlarge`, `c6i.large`, `r5.xlarge`, `r6.xlarge`,
  `m5.large`, `m6.large`, `i3.xlarge`, `t3.medium`, `t3a.medium`
- **Zonas de disponibilidade**: `us-east-1a`, `us-east-1b`, `us-east-1c`

## Perfil por pool

Construído uma vez por execução (`_build_profiles`), a partir do mesmo RNG
(*Random Number Generator*, o `random.Random(seed)` mencionado em
[Determinismo](#determinismo)):

- **`volume_weight`**: `rng.uniform(0.2, 1.0)` por pool, é o que torna o
  volume de eventos desigual entre pools (alguns pools são sorteados com muito
  mais frequência que outros.
- **`base_failure_rate`**: a taxa base da AZ (abaixo).

## Disponibilidade por AZ

Algumas AZs são sistematicamente menos confiáveis que outras
(`_AZ_BASE_FAILURE_RATE`):

| AZ | Taxa de falha base |
| -- | -------------------- |
| `us-east-1a` | 0.05 (mais confiável) |
| `us-east-1b` | 0.15 |
| `us-east-1c` | 0.30 (menos confiável) |

## Variação ao longo do dia

`_hour_multiplier(hour)`: horário comercial (09:00-18:00 UTC) multiplica a
taxa de falha efetiva por **1.6**, fora do horário comercial multiplica por
**0.6**. Isso simula maior pressão sobre spot durante o expediente. A taxa
efetiva final é `min(0.95, base_failure_rate * hour_multiplier)`.

## Mix de reasons (só entre eventos de falha)

Quando um evento é gerado como falha, seu `reason` é amostrado a partir de
`_FAILURE_REASON_WEIGHTS`:

| Reason | Peso relativo                                                                  |
| ------ |--------------------------------------------------------------------------------|
| `SPOT_INSTANCE_TERMINATION` | 0.7 (dominante - bate com a categoria default `AVAILABILITY_FAILURE`) |
| `TIMED_OUT` | 0.2                                                                            |
| `SPARK_EXECUTION_ERROR` | 0.1                                                                            |

Eventos bem-sucedidos sempre têm `reason: null`.

## Campos do evento

Cada evento gerado: `finished_at` (ISO 8601, UTC), `job_id` (`job-00000000`,
índice sequencial com zero a esquerda), `pool_id`, `status` (`"SUCCESS"` ou
`"FAILED"`), `reason` (`null` em caso de sucesso).

## Layout de saída

Particionado como `dt=YYYY-MM-DD/hr=HH/events.json` sob `--output-dir`, um
objeto JSON por linha (NDJSON), imita o particionamento por data/hora de um
bucket S3. Rodar de novo com os mesmos argumentos sobrescreve cada
arquivo de partição no lugar (modo `"w"`) em vez de duplicar linhas.

## Orientação prática sobre a seed

O valor de `--seed` em si é arbitrário, o que importa é a *consistência*: use
a mesma seed entre execuções quando quiser dado reproduzível (testes, demos).