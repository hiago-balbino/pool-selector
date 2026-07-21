# ADR 0009: Monólito modular em vez de microsserviços

## Decisão

O serviço é um monólito modular (um único deployable), organizado em portas &
adapters, não uma coleção de microsserviços.

## Motivo

O domínio é pequeno e coeso (ingestão -> agregação -> ranking, servido por um
único endpoint principal), sem fronteiras de equipe ou de escala que
justifiquem serviços separados hoje. Um monólito modular já entrega o
benefício que normalmente motiva a quebra em microsserviços, trocar uma
implementação (fonte de dados, store) sem tocar o domínio via portas &
adapters (veja
[`docs/adr/0001-ports-and-adapters.md`](0001-ports-and-adapters.md)), sem
pagar o custo operacional de múltiplos deployables, contratos de rede entre
serviços e consistência distribuída.

## Trade-off

Escalar partes do sistema de forma independente (ex. ingestão vs. servir
requisições) exigiria escalar o processo inteiro. Veja "Evolução futura:
ingestão do S3 em escala maior" em [`docs/limitations.md`](../limitations.md) para outra abordagens possíveis.

## Escopo

Estrutura geral do repositório (`src/pool_selector/`) e decisão de
deployment (`Dockerfile`, `render.yaml`).
