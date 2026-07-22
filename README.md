# Pool Selector

Uma API que recomenda o pool de instâncias EC2 spot com maior probabilidade de
executar um job Apache Spark até o fim sem perder a instância por
`SPOT_INSTANCE_TERMINATION`, com base no histórico recente de execuções de jobs
armazenado como JSON (S3 ou sistema de arquivos local).

Veja [`docs/architecture.md`](docs/architecture.md) para a arquitetura e
[`docs/adr/`](docs/adr/) para as decisões de design por trás dela.

## Pré-requisitos

- Python 3.14
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) - gerenciador de
  pacotes e executor de tarefas usado em todo o projeto
- Docker + Docker Compose - necessário só para o caminho containerizado

## Configuração inicial

O `uv` cuida do ambiente virtual, não há um passo separado de `pip install` em
nenhuma plataforma.

**macOS / Linux**

```bash
uv sync
```

**Windows (PowerShell)**

```powershell
uv sync
```

Instale o próprio `uv` primeiro, se ainda não estiver disponível (veja as
[instruções oficiais de instalação](https://docs.astral.sh/uv/getting-started/installation/)
para sua plataforma).

O `uv sync` já instala o `pre-commit` (é uma dependência de dev) - nenhum passo de
instalação separado é necessário. Para que ele de fato rode lint/format/type-check
antes de cada commit, ative o hook do git uma vez por clone:

```bash
uv run pre-commit install
```

## Executando

O projeto sobe com um único comando, containerizado ou não, e responde em
`http://localhost:5050/get-pools`.

**Sem container**

```bash
make run
```

Passos manuais equivalentes:

```bash
uv sync
uv run python -m tools.generate_data --seed 42 --num-events 2000 --days 3 --output-dir ./data
uv run uvicorn pool_selector.api.app:app --host 0.0.0.0 --port 5050
```

**Containerizado (Docker)**

```bash
make docker-up
make docker-down
```

Passo manual equivalente:

```bash
docker compose up --build
docker compose down
```

Os dois caminhos leem configuração de variáveis de ambiente (veja
[Configuração](#configuração) abaixo), e os dois geram um dataset sintético em
`LOCAL_DATA_DIR` (default `./data`) automaticamente antes de subir o servidor - um
único comando já é suficiente para ter uma resposta funcional em `/get-pools`, sem
passo de setup separado. Veja
[Gerando dados sintéticos](#gerando-dados-sintéticos) para customizar ou desligar
isso.

## Configuração

Todas as variáveis estão documentadas em [`.env.example`](.env.example), copie-o
para `.env` para sobrescrever qualquer default:

| Variável | Default | Significado                                                                                                                                                                                                                                                                                                                                                            |
| -------- | ------- |------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `PORT` | `5050` | Porta do servidor da API. Lida diretamente pelo comando de shell que inicia o `uvicorn` (`Makefile`, `docker-entrypoint.sh`) ou pela substituição de variáveis do Docker Compose, não faz parte do loader `Settings`/`pydantic-settings` abaixo, então o `make run` só a lê do `.env` porque o `Makefile` carrega o `.env` explicitamente antes de iniciar o `uvicorn` |
| `DATA_SOURCE` | `local` | `local` ou `s3`                                                                                                                                                                                                                                                                                                                                                        |
| `LOCAL_DATA_DIR` | `./data` | Diretório de onde o `LocalFileSource` lê, precisa estar organizado como `dt=YYYY-MM-DD/hr=HH/*.json` (veja [`docs/synthetic-data.md`](docs/synthetic-data.md)) (só as partições dentro da janela de recência são lidas)                                                                                                                                                |
| `S3_BUCKET` / `S3_PREFIX` | *(vazio)* | Bucket/prefixo de onde o `S3Source` lê quando `DATA_SOURCE=s3`. Mesmo requisito de particionamento `dt=/hr=`                                                                                                                                                                                                                                                           |
| `RECENCY_WINDOW_MINUTES` | `60` | Janela deslizante de recência, em minutos                                                                                                                                                                                                                                                                                                                              |
| `LOW_CONFIDENCE_THRESHOLD` | `5` | Tamanho de amostra abaixo do qual um pool é marcado com `confidence: "low"`                                                                                                                                                                                                                                                                                            |
| `REFRESH_INTERVAL_SECONDS` | `60` | Intervalo entre atualizações do agregado em background                                                                                                                                                                                                                                                                                                                 |
| `GENERATE_SAMPLE_DATA` | `false` | Se `true`, gera um dataset sintético em `LOCAL_DATA_DIR` logo antes do servidor subir (veja [Gerando dados sintéticos](#gerando-dados-sintéticos))                                                                                                                                                                                                                     |
| `SAMPLE_DATA_SEED` | `42` | Seed usada quando `GENERATE_SAMPLE_DATA=true`                                                                                                                                                                                                                                                                                                                          |
| `SAMPLE_DATA_NUM_EVENTS` | `2000` | Quantidade de eventos usada quando `GENERATE_SAMPLE_DATA=true`                                                                                                                                                                                                                                                                                                         |
| `SAMPLE_DATA_DAYS` | `3` | Intervalo de dias usado quando `GENERATE_SAMPLE_DATA=true`                                                                                                                                                                                                                                                                                                             |

## Exemplos de uso da API

```bash
# Melhor pool disponível, sem filtro
curl http://localhost:5050/get-pools

# Filtrar por tipo de instância / família / categoria de workload exatos
curl "http://localhost:5050/get-pools?instance_type=r6.xlarge"
curl "http://localhost:5050/get-pools?family=r6"
curl "http://localhost:5050/get-pools?category=memory"

# Lista ranqueada com os 3 melhores pools
curl "http://localhost:5050/get-pools?top_n=3"

# Liveness / readiness
curl http://localhost:5050/health
curl http://localhost:5050/ready
```

Exemplo de resposta de `GET /get-pools` (um único pool):

```json
{
  "pool_id": "pool-r6.xlarge-us-east-1a",
  "instance_type": "r6.xlarge",
  "az": "us-east-1a",
  "score": 0.98,
  "sample_size": 42,
  "confidence": "normal",
  "window": "60m sliding"
}
```

Exemplo de resposta de `GET /get-pools?top_n=2`:

```json
{
  "pools": [
    { "pool_id": "pool-r6.xlarge-us-east-1a", "instance_type": "r6.xlarge", "az": "us-east-1a", "score": 0.98, "sample_size": 42, "confidence": "normal", "window": "60m sliding" },
    { "pool_id": "pool-c5.xlarge-us-east-1b", "instance_type": "c5.xlarge", "az": "us-east-1b", "score": 0.95, "sample_size": 30, "confidence": "normal", "window": "60m sliding" }
  ]
}
```

Quando nenhum pool casa com o filtro, ou não há dado nenhum na janela, os dois
casos retornam HTTP 404 com um corpo explicativo: `{"detail": "..."}`. Um pool
cujo `sample_size` está abaixo de `LOW_CONFIDENCE_THRESHOLD` ainda retorna HTTP
200, com `"confidence": "low"`.

## Testes

```bash
make test
```

equivalente a `uv run pytest --cov=src --cov-report=term-missing`.

## Lint & checagem de tipos

```bash
make lint
```

equivalente a `uv run ruff check . && uv run ruff format --check . && uv run mypy src`.

## Estratégia de CI/CD

O workflow [`ci.yml`](.github/workflows/ci.yml) roda em toda `push` para `main`
e em toda pull request (contra qualquer branch): instala as dependências via
`uv`, roda lint/format/type-check (`ruff` + `mypy`) e a suíte de testes com
cobertura, numa matriz de 3 sistemas operacionais (Ubuntu, macOS, Windows).

O deploy no Render (veja [Deploy no Render](#deploy-no-render)) é disparado
automaticamente assim que esses checks passam (`autoDeployTrigger:
checksPass` em [`render.yaml`](render.yaml)), sem nenhum job ou passo manual
de deploy:

- **Pull requests**: toda PR aberta contra `main` ganha um ambiente de
  preview efêmero, provisionado depois que os checks passam. O Render expõe
  um botão na própria PR apontando para essa URL, que também segue um padrão
  previsível: `https://pool-selector-pr-<numero-da-pr>.onrender.com/health`.
- **Produção**: ao mergear a PR em `main`, o mesmo mecanismo dispara o deploy
  de produção, em https://pool-selector.onrender.com/health.

A estratégia segue o padrão de **deploy contínuo** (*continuous deployment*), não existindo um passo manual para o deploy acontecer.

Os ambientes do Render (plano free) são short-lived: depois de um período
ocioso a instância dorme, e a primeira requisição seguinte pode levar alguns
segundos para reiniciar a infraestrutura (cold start).

### Evolução futura: rollout e rollback mais robustos

Para um fluxo de produção real, com garantias mais fortes do que "deploy
direto assim que o CI passa", rollout progressivo (canary ou blue/green)
combinado com rollback automático, disparado por health checks falhando ou
métricas fora de um threshold estabelecido, seria o caminho mais robusto.

### Deploy no Render

O repositório inclui um Blueprint [`render.yaml`](render.yaml) para um Web
Service de runtime Docker:

```bash
# O Render lê o render.yaml e provisiona o serviço automaticamente.
```

Ele constrói a partir do `Dockerfile` existente e define
`healthCheckPath: /health`.

O filesystem do Render é efêmero entre deploys, então não existe um `./data`
pré-existente como há num checkout local. O Blueprint define
`GENERATE_SAMPLE_DATA=true`, então o `docker-entrypoint.sh` gera um dataset
sintético novo a cada boot antes de iniciar o servidor, os timestamps ficam
ancorados em "agora" a cada início, então a janela de recência default de 60
minutos sempre encontra dado para recomendar. Uma vez que um `DATA_SOURCE=s3`
real seja configurado, defina `GENERATE_SAMPLE_DATA=false` (ou remova a
variável) para não sobrescrever dado real.

## Arquitetura

Veja [`docs/architecture.md`](docs/architecture.md) para o diagrama de
componentes e a descrição do fluxo de requisição.

## Decisões de design

Veja [`docs/adr/`](docs/adr/) para os registros de decisão de arquitetura por
trás das escolhas principais deste projeto (limite inferior de Wilson,
estratégia de recência plugável, classificação configurável de reason, ports &
adapters, sem banco de dados, ferramental, catálogo estático de instâncias,
pruning de partição no S3, monólito modular em vez de microsserviços).

## Fora de escopo & limitações

Veja [`docs/limitations.md`](docs/limitations.md) para o que este projeto não cobre, e por quê.

## Gerando dados sintéticos

O refresh em background da API precisa de dados de eventos em `LOCAL_DATA_DIR`
(default `./data`) para ter algo a recomendar. **`make run` e `make docker-up`
geram isso automaticamente** (via `GENERATE_SAMPLE_DATA` ligado por padrão). Veja
[`docs/synthetic-data.md`](docs/synthetic-data.md) para as regras de geração
(taxas de falha por AZ, variação por horário, mix de reasons, volume desigual por
pool) por trás das flags de CLI abaixo.

Para gerar explicitamente (ex. para inspecionar a saída, ou regenerar sem subir o
servidor):

```bash
make generate-data
```

Passo manual equivalente:

```bash
uv run python -m tools.generate_data --seed 42 --num-events 2000 --days 3 --output-dir ./data
```

- `--seed` (`SAMPLE_DATA_SEED`) - a mesma seed sempre reproduz exatamente os
  mesmos eventos (saída idêntica byte a byte)
- `--num-events` (`SAMPLE_DATA_NUM_EVENTS`) - número total de eventos a gerar
- `--days` (`SAMPLE_DATA_DAYS`) - quantos dias atrás, a partir de hoje, os
  eventos se espalham
- `--output-dir` (`LOCAL_DATA_DIR`) - onde os arquivos JSON particionados por
  data/hora são escritos

**Desligando a geração automática:** `GENERATE_SAMPLE_DATA` tem default `true`
especificamente para `make run` e `make docker-up`, então um único comando é
sempre uma demo funcional.

Um container construído diretamente a partir deste `Dockerfile` (sem
`docker-compose`, ex. no Render) usa `false` como default para
`GENERATE_SAMPLE_DATA`, a escolha mais segura quando a imagem é usada fora dos
wrappers de desenvolvimento local deste repositório, já que um deploy real pode
ter `LOCAL_DATA_DIR` apontando para dado real e curado, que nunca deve ser
sobrescrito silenciosamente. O [`render.yaml`](render.yaml) reabilita
explicitamente (`GENERATE_SAMPLE_DATA: "true"`) porque o filesystem lá é efêmero
e não há dataset real a proteger. `SAMPLE_DATA_SEED` / `SAMPLE_DATA_NUM_EVENTS` /
`SAMPLE_DATA_DAYS` sobrescrevem os defaults do gerador em todos esses caminhos.
