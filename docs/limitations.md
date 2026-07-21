# Fora de escopo & limitações

## Reativo por construção

Esta solução é **reativa por construção**: ela recomenda pools com base no
histórico de eventos passados de jobs, ou seja, depois que as falhas já
aconteceram. Ela não prevê indisponibilidade antes de qualquer sinal aparecer
nos dados. Isso é inerente ao problema como declarado: o único sinal disponível
é o histórico de execução no S3, não há acesso a sinais de disponibilidade spot
da AWS em tempo real.

A aposta em que a abordagem se apoia é a **autocorrelação temporal de curto
prazo** da disponibilidade spot: se uma AZ está terminando instâncias agora,
ela tende a continuar fazendo isso nos próximos minutos. É por isso que a
**recência** é o parâmetro central, com uma janela curta e recente, "passado
observado" se aproxima de "presente". Duas mitigações dentro dos dados
disponíveis:

- **Detecção de tendência**: penalizar pools cuja taxa de terminação está
  *subindo*, mesmo enquanto ainda baixa, para antecipar degradação antes que
  ela se materialize por completo.
- **Sucesso como sinal contínuo**: todo job bem-sucedido é evidência positiva,
  não só falhas contando contra um pool.

### Evoluindo para uma abordagem proativa

Uma versão genuinamente proativa precisaria de sinais que não temos atualmente: preço spot em tempo real, sinais antecipados de
interrupção da AWS (rebalance recommendations), e histórico de capacidade por
AZ. Isso é documentado como evolução futura.

## Fora de escopo

Explicitamente excluído desta feature, para evitar scope creep.

| Feature | Motivo                                                                                                                                                                                                                          |
| ------- |---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Autenticação/autorização | Serviço interno da plataforma, em produção viria do gateway/service mesh                                                                                                                                                        |
| Rate limiting a nível de aplicação | Pertence à borda (API gateway/ingress) em produção, opcionalmente demonstrável via um middleware leve e desligável                                                                                                              |
| Banco de dados | Um agregado em memória, totalmente reconstruível a partir do S3, é suficiente (veja [`docs/adr/0002-no-database-in-memory-aggregate.md`](adr/0002-no-database-in-memory-aggregate.md)), o store é plugável para evolução futura |
| LocalStack | Avaliado e descartado, peso desproporcional em relação ao problema. O `moto` já prova compatibilidade com o S3                                                                                                                  |
| `S3Source` validado contra AWS real | Hoje prova que a integração funciona (testado via `moto`, nunca contra um bucket real em produção), suficiente para o escopo atual, veja [`docs/adr/0001-ports-and-adapters.md`](adr/0001-ports-and-adapters.md) |
| Abordagem proativa (preço spot em tempo real, rebalance recommendations da AWS) | No momento apenas temos o histórico de execução                                                                                                                                                                                 |
| Fallback de pool quando nenhum casa com o filtro | Retorna 404 hoje, por previsibilidade, um fallback é documentado como evolução futura                                                                                                                                           |
| Métricas (contagem de requests, latência, distribuição de recomendação por pool, frescor do agregado) | Não fazem parte do escopo desta versão, logging estruturado e `/health`/`/ready` já cobrem a necessidade operacional atual, veja abaixo o caminho recomendado para quando forem realmente necessárias                           |
| Peso contínuo de recência (ex. decaimento exponencial) | O protocolo `RecencyStrategy` atual só suporta filtro binário, uma estratégia de peso contínuo exigiria um desenho diferente, veja abaixo o que isso envolveria                                                                 |

## Implementado mas não conectado: desempate com seed para distribuição de carga

`domain/selector.py::select_best_pools` aceita um parâmetro `seed`: quando dois ou mais pools têm um empate *exato* de
`confidence_score`, um fator pseudoaleatório baseado na seed decide entre
eles, então chamadas idênticas com a mesma seed sempre resolvem da mesma
forma, enquanto seeds diferentes podem distribuir carga entre pools
estatisticamente equivalentes em vez de sempre favorecer o mesmo. Isso está
implementado e testado (`tests/unit/domain/test_selector.py`), e no momento o default
(`seed=None`) produz o fallback com ordem
determinística por `pool_id`.

O que falta: `api/routes.py` nunca passa uma `seed` para `select_best_pools`,
então em produção o caminho `None` é sempre o usado. Isso não é código morto,
a capacidade do domínio é real e correta, só não é realmente necessário o uso pelo único
chamador que existe hoje. Empates exatos também devem ser raros na prática
(exigem `total_events`/`availability_failures`/`recent_events` idênticos entre
pools), então é uma lacuna de baixa prioridade, não um bug. Se distribuir carga
em empates se tornar algo que vale a pena ativar, a rota precisaria passar uma
seed que varie por chamada (ex. derivada da requisição ou do relógio) em vez
de uma constante fixa, o que só mudaria quem sempre vence, sem de fato
distribuir nada.


## Evolução futura: métricas

Se/quando este serviço precisar de observabilidade real além de logs e
`/ready`, o caminho recomendado é:

- **Ferramental**: [`prometheus-client`](https://github.com/prometheus/client_python)
  para um endpoint `/metrics` raspado pelo Prometheus ou `opentelemetry-api`/`opentelemetry-sdk`
  com um exportador OTLP, se o deploy já padronizar em OpenTelemetry/um APM de
  fornecedor (Datadog, Grafana Cloud, etc.) em vez de Prometheus diretamente.
- **Métricas candidatas**:
  - `http_requests_total`
  - `http_request_duration_seconds`
  - `pool_recommendation_total`
  - `stats_store_freshness_seconds` (gauge) idade do agregado, derivada de
    `StatsStore.get_freshness()`

## Evolução futura: peso contínuo de recência (ex. decaimento exponencial)

O protocolo atual de `RecencyStrategy` (`select_window(events, now) ->
Iterable[JobEvent]`) é um filtro binário: um evento conta inteiramente ou não
conta nada. Isso suporta genuinamente novas estratégias do mesmo formato (um
corte diferente, inclusão só em horário comercial), mas não consegue expressar
corretamente um peso contínuo por evento. Uma estratégia de decaimento exponencial é um exemplo natural desse segundo tipo de estratégia.

Implementá-la contra o protocolo atual precisaria de algumas alterações: um método `select_window` não tem como retornar "quanto" um evento pesa, só se ele conta ou não. Qualquer implementação que tentasse resolver isso via um método adicional fora do protocolo (ex. um `weight_for`
que só ela conhece) criaria uma violação de substituição de Liskov.


## Evolução futura: ingestão do S3 em escala maior

O `S3Source` já faz pruning de leitura pelas partições `dt=/hr=` dentro da
janela de recência e cacheia partições fechadas em memória
(`docs/adr/0008-s3-source-partition-pruning.md`), isso resolve o problema de
"reescanear o bucket inteiro a cada ciclo" para os volumes de dado que este
projeto tem como alvo. Em escala significativamente maior (muitos pools, alto
volume de eventos, ou uma janela de recência bem mais ampla), outras opções
existem, em ordem crescente de quanto de arquitetura elas mudam:

- **Paralelizar buscas dentro de um ciclo.** Uma vez que as leituras já estão
  restritas a um punhado de partições/objetos, buscá-los concorrentemente (um
  thread pool, ou `asyncio` + `aioboto3`) encurta ainda mais o tempo de
  relógio do refresh, um ganho menor que o pruning em si, já que o pruning já
  reduziu a contagem de objetos, mas se soma a ele.
- **Desacoplar a ingestão do processo que serve requisições por completo.** A
  resposta de escala de produção: um job separado (Lambda disparado por
  `ObjectCreated` do S3, ou um batch agendado no Glue/Spark) mantém o
  agregado num store externo leve (DynamoDB, um objeto S3 pequeno) que a API
  lê em vez de tocar o S3 diretamente em qualquer caminho, seja servindo
  requisição ou no refresh em background. Isso remove por completo o
  acoplamento de "um processo que serve tráfego e também escaneia um data
  lake", ao custo de infraestrutura real (um segundo deployable, um store
  externo, raciocínio de consistência eventual entre os dois). Provavelmente a
  resposta certa num ambiente de produção real construído sobre S3 em escala,
  fora do escopo aqui.
- **S3 Select / Athena** para filtragem empurrada para o storage em vez de
  transferir objetos inteiros para parsear no lado do cliente. Reduz bytes
  transferidos por objeto, mas adiciona overhead de motor de query e latência
  por chamada, só compensa quando arquivos de partição individuais são
  grandes o suficiente para que o parsing de JSON no lado do cliente (não a
  contagem de objetos) seja o gargalo.
