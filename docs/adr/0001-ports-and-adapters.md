# ADR 0001: Ports & adapters para fonte de dados e store de estatísticas

## Decisão

Fontes de dados (S3/local) e o store de estatísticas são acessados
exclusivamente através de portas (`DataSource`, `StatsStore`), nunca
diretamente por uma implementação concreta.

## Motivo

Permite trocar `LocalFileSource` e `S3Source` entre si, e trocar
`InMemoryStore` por um futuro `RedisStore`/`DBStore`, sem tocar a lógica de
domínio (extensibilidade). Também torna as duas camadas testáveis com
fakes/`moto`, sem nenhuma infraestrutura real.

## Trade-off

Uma camada extra de indireção (interfaces) para um projeto que hoje só
precisa de uma implementação de cada porta. O `S3Source` hoje só foi
exercitado contra `moto` (S3 simulado), nunca contra um bucket real em
produção, existe para provar que a porta `DataSource` suporta S3 de fato (que seria o caso real).

## Escopo

`src/pool_selector/ingestion/`, `src/pool_selector/store/`, e qualquer
feature futura que leia eventos ou agregados.
