# ADR 0007: Catálogo estático e versionado de instâncias, com fallback pela convenção AWS

## Decisão

`domain/catalog.py::category_for_family` resolve uma família de instância
(ex. `r6`, `c5`) para uma `WorkloadCategory`
(compute/memory/general/storage/burstable) via um **dict estático,
versionado no repositório** (`_CATALOG`), populado manualmente a partir do
[`instances.vantage.sh`](https://instances.vantage.sh) em tempo de design, não consultado pela rede em runtime. Famílias ausentes do `_CATALOG` caem no
fallback pela convenção de nomenclatura da AWS (primeira letra da família:
`c`->compute, `r`->memory, `m`->general, `i`->storage, `t`->burstable). Uma
família que não casa com nenhum dos dois resolve para
`WorkloadCategory.UNKNOWN` em vez de lançar erro.

## Motivo

O conjunto de famílias de instância que este serviço precisa categorizar é
pequeno e muda raramente (a AWS adiciona novas famílias algumas vezes por
ano, não todo dia). Uma consulta em runtime contra o Vantage (ou a API da
AWS) adicionaria uma dependência de rede e um modo de falha
(`category_for_family` precisa responder de forma síncrona, em todo filtro
de `/get-pools`, com mínimo ou zero I/O no caminho de leitura) para algo que é efetivamente dado
de referência estático. O fallback pela convenção AWS garante que uma
família não reconhecida ainda recebe uma categoria razoável, em vez de
quebrar o filtro por completo.

## Trade-off

Famílias fora tanto do catálogo explícito quanto da cobertura da convenção
de primeira letra resolvem para `UNKNOWN`, impreciso, mas nunca errado no
sentido de lançar erro ou bloquear uma resposta. Novas famílias de instância
da AWS (ou famílias cuja primeira letra não bate com a convenção, ex. uma
hipotética família de GPU) exigem uma mudança manual de código no `_CATALOG`
para serem categorizadas com precisão, em vez de cair no fallback.

## Evolução futura: catálogo atualizado periodicamente por uma fonte externa

A alternativa a edição manual do `_CATALOG` não é necessariamente uma
consulta síncrona por requisição (o modo de falha que o "Motivo" acima
descarta), é o mesmo padrão já usado para o `StatsStore`: um `CatalogSource`
(porta, análoga a `DataSource`) consultado por uma tarefa periódica em
background (análoga a `RefreshTask`), que atualiza um catálogo em memória a
cada N minutos/horas a partir do Vantage ou da API `DescribeInstanceTypes`
da AWS. O caminho de leitura (`category_for_family`) continuaria síncrono e
sem I/O, lendo só o último catálogo já resolvido. Se a fonte externa falhar,
o catálogo anterior continua servindo (mesma degradação graciosa do
`RefreshTask` atual [`docs/adr/0002-no-database-in-memory-aggregate.md`](0002-no-database-in-memory-aggregate.md)).

## Estendendo o catálogo

Adicione uma entrada `"<família>": WorkloadCategory.<CATEGORIA>` no
`_CATALOG` em `domain/catalog.py` quando uma nova família de instância
precisar de categorização precisa, a ordem de busca do
`category_for_family` (entrada explícita -> fallback por primeira letra ->
`UNKNOWN`) não exige nenhuma outra mudança de código.

## Escopo

`src/pool_selector/domain/catalog.py`.
