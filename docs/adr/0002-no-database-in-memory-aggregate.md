# ADR 0002: Sem banco de dados - agregado em memória reconstruído a partir do S3

## Decisão

Sem banco de dados na v1. O agregado por pool é mantido em memória
(`InMemoryStore`) e é totalmente reconstruível a partir dos eventos do S3 via
refresh periódico.

## Motivo

O volume é pequeno (tipos de instância × AZs), um banco de dados adicionaria
latência/operação sem ganho.

## Trade-off

Sem persistência entre reinícios, cada réplica reconstrói seu agregado do
zero ao subir, sem coordenação entre réplicas (veja o ADR 0001 para o
ponto de extensão futuro via Redis/DB).

## Escopo

`src/pool_selector/store/`.
