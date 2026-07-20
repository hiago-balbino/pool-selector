# ADR 0003: Limite inferior de Wilson para confiança em baixa amostragem

## Decisão

O ajuste estatístico para tamanhos de amostra pequenos usa o **limite
inferior de Wilson**.

## Motivo

Resolve de forma limpa o desempate primário: entre dois pools ambos a 0% de
taxa de terminação, o de maior amostra tem um limite inferior de Wilson
maior, refletindo corretamente que ele carrega mais evidência real.

## Trade-off

Um pouco mais complexo de implementar que uma suavização simples, mas o
comportamento de desempate que ele produz é um requisito do domínio.

## Alternativa considerada: suavização de Laplace

Suavização de Laplace estima a taxa como
`(sucessos + α) / (total + 2α)` para uma constante `α` fixa (tipicamente 1),
em vez de contar direto `sucessos / total`. Isso evita estimativas extremas
(0% ou 100%) com poucas amostras, mas `α` é uma constante arbitrária sem
interpretação probabilística, não corresponde a nenhum nível de confiança
específico, e ajustá-la para reproduzir um comportamento de desempate
equivalente ao de Wilson exigiria calibração manual, sem garantia formal.

## Escopo

`src/pool_selector/domain/scoring.py` e qualquer lógica de seleção de pool.
