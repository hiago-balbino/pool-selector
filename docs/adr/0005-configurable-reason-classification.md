# ADR 0005: Classificação configurável de reason para o score de disponibilidade

## Decisão

O score de disponibilidade (`score = 1 − taxa_de_falha_de_disponibilidade`) é
calculado sobre uma **categoria configurável de `reason`s**
(`AVAILABILITY_FAILURE`), não uma string fixa no código.
`SPOT_INSTANCE_TERMINATION` é só o membro default dessa categoria.

## Motivo

Novos `reason`s podem ser adicionados via configuração, sem
tocar a lógica central, o score precisa poder considerar mais de um reason no
cálculo.

## Trade-off

Exige uma tabela de classificação reason->categoria mantida em configuração,
em vez de uma comparação direta de string, uma pequena indireção a mais.

## Escopo

`src/pool_selector/domain/scoring.py`,
`src/pool_selector/domain/reason_classification.py`, e o gerador de dados
sintéticos (precisa produzir reasons consistentes com a classificação).
