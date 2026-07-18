# ADR 0006: Stack e ferramental - dependências de produção e de dev

## Decisão

Todas as dependências definidas para o projeto:

**Produção** (`dependencies`):

- **FastAPI** - framework da API, async nativo, validação e serialização via
  Pydantic já integradas, gera `/docs` (OpenAPI) automaticamente
- **uvicorn** - servidor ASGI(Asynchronous Server Gateway Interface) que roda a app FastAPI, contraparte natural do
  framework escolhido
- **Pydantic** - validação e serialização tipada, base do `api/schemas.py` e
  de como o FastAPI valida request/response
- **pydantic-settings** - extensão do Pydantic para carregar configuração de
  variáveis de ambiente/`.env` (`settings.py`)
- **boto3** - SDK oficial da AWS

**Dev** (`dependency-groups.dev`):

- **mypy** (strict) - type checker
- **ruff** - lint + format
- **pytest** - testes
- **moto** - simula o S3 (sem AWS real)
- **pytest-asyncio** - necessário para testar as partes assíncronas do
  projeto (`RefreshTask.start()`, o `lifespan` da app FastAPI)
- **pytest-cov** - relatório de cobertura, usado no gate de build
- **httpx2** - exigido pelo `TestClient` do FastAPI/Starlette para simular
  requisições contra a app sem subir um servidor de verdade
- **pre-commit** - orquestra ruff/mypy como hook de git antes de cada commit

## Motivo

Do lado de produção, FastAPI/Pydantic/boto3 são as escolhas padrão do
ecossistema Python para este tipo de serviço (API REST assíncrona validando
dados tipados, consumindo S3). Do lado de dev, ecossistema maduro e bem
integrado a CI, `pytest-asyncio`, `pytest-cov` e `httpx2` não são escolhas
concorrentes, são exigências diretas de outras peças já decididas aqui
(testar código assíncrono, medir cobertura, e usar o `TestClient` do próprio
framework escolhido para a API).

## Trade-off

FastAPI/Pydantic prendem o projeto ao ecossistema deles (troca de framework
custaria reescrever schemas e validação), boto3 é um SDK genérico e pesado
para o pouco que este projeto usa dele (list/get de objetos), mas é o padrão
de fato e evita reimplementar chamadas HTTP a API do S3 manualmente. mypy é
mais lento que pyright em projetos grandes (não relevante na escala deste
projeto no momento).

## Escopo

O repositório inteiro: `pyproject.toml`, CI, pre-commit.
