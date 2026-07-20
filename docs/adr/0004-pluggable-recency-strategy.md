# ADR 0004: Estratégia de recência plugável

## Decisão

Ponderação temporal (recência) é uma **Strategy plugável** (`RecencyStrategy`).
A implementação padrão é uma janela deslizante com **N minutos configurável**
(nunca um valor fixo no código).

## Motivo

A disponibilidade spot varia ao longo do dia, a janela precisa ser ajustável
por ambiente/operação sem mudança de código. O padrão Strategy também funciona
como ponto de extensão para futuras regras de recência.

## Trade-off

O único método do `RecencyStrategy` (`select_window`) é um filtro binário: um
evento conta inteiramente ou não conta nada. Isso suporta genuinamente novas
estratégias do mesmo formato (um corte diferente, inclusão só em horário
comercial), mas não consegue expressar corretamente um peso contínuo por
evento (ex. decaimento exponencial). Uma estratégia desse segundo tipo
exigiria trocar a primitiva do protocolo — veja `docs/limitations.md`
("Evolução futura: peso contínuo de recência") para o que isso envolveria.

## Escopo

`src/pool_selector/domain/recency.py` e o `selector` que a consome.
