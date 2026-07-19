# ADR 0008: Os dois adapters de `DataSource` fazem pruning de leitura pelas partições da janela de recência

## Decisão

Nenhum adapter de `DataSource` lê tudo sob seu diretório/prefixo configurado
a cada ciclo de refresh. Uma função auxiliar compartilhada
(`_relevant_partitions(now, window_minutes)`) calcula as partições de hora
`dt=YYYY-MM-DD/hr=HH/` que caem
dentro de `[now - window_minutes, now]`, tanto o `S3Source` quanto o
`LocalFileSource` só leem essas.

O `S3Source` também cacheia em memória as partições cuja hora já fechou em
relação a `now`, nunca re-buscando-as, a partição da hora corrente de `now`
(ainda sendo escrita) é sempre re-buscada, já que pode continuar recebendo
eventos novos. Entradas de cache são descartadas assim que a partição sai da
janela numa chamada posterior, assim a memória fica limitada ao tamanho da
janela, nunca ao histórico completo do bucket.

O `LocalFileSource` faz o mesmo pruning de quais subdiretórios ler, mas
**não** cacheia partições fechadas: uma releitura local é barata o
suficiente (sem round-trip de rede) para que a complexidade do cache não se
pague ali. Os dois adapters usam `now` com o mesmo significado, só o
`S3Source`, além disso, lembra estado entre chamadas.

## Motivo

Ler tudo sob o prefixo (`list_objects_v2` sobre tudo, depois `get_object` em
cada resultado) a cada ciclo de `RefreshTask`, independente de
`REFRESH_INTERVAL_SECONDS` ou de quanto daquele dado a `RecencyStrategy`
ativa realmente usaria, desperdiça I/O, só uma fatia do tamanho de
`RECENCY_WINDOW_MINUTES` dos eventos afeta o agregado, e esse desperdício
cresce sem limite conforme um bucket real de produção acumula histórico ao
longo dos meses.

## Trade-off

- `DataSource.iter_events()` tem a assinatura `iter_events(now: datetime)` -
  os dois adapters usam `now` genuinamente, com o mesmo significado.
- x`LocalFileSource` exige o mesmo layout particionado `dt=/hr=` que o
  `S3Source` - não suporta um diretório plano/arbitrário de arquivos `.json`.
  Isso bate com o que `tools/generate_data.py` já produz por padrão.
- A janela de pruning dos dois adapters vem do mesmo
  `Settings.recency_window_minutes` que alimenta o `SlidingWindowStrategy`,
  para evitar noções configuradas independentemente de "quanto passado
  importa" divergindo entre si. Um chamador que injeta uma `RecencyStrategy`
  com uma janela diferente da que passa como `window_minutes` é responsável
  por manter essa consistência, nada garante isso em nível de tipo.

## Escopo

`src/pool_selector/ingestion/source.py`, `src/pool_selector/store/refresh.py`
(passa `now` para a fonte e para o aggregator a partir de uma única leitura
de relógio por ciclo), `src/pool_selector/api/app.py` (injeta
`window_minutes` a partir das settings).

## Outros cenários considerados (não implementados agora)

Veja a seção "Evolução futura: ingestão do S3 em escala maior" em
`docs/limitations.md` para outras opções (busca incremental via ETags,
desacoplar a ingestão do processo que serve requisições, S3 Select/Athena)
que foram julgadas fora de escopo para o volume de
dado atual.
