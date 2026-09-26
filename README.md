# +10 minutos

SPA em Python/Flask para explorar desvios de chegada da **linha C, sentido sul, ponto 431 — 3RD AVE & PIKE ST, Seattle**.

## Executar localmente

Requer Python 3.10 ou 3.11. No PowerShell, dentro desta pasta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe app.py
```

Abra **http://127.0.0.1:8000**. Encerre com `Ctrl+C`. Nesta entrega o ambiente virtual já foi instalado. Para iniciar novamente, também pode executar `powershell -ExecutionPolicy Bypass -File .\iniciar.ps1`.

Em Linux/macOS, os equivalentes são `.venv/bin/python` e `.venv/bin/pip`. O servidor é Waitress, sem modo de depuração. `HOST` e `PORT` configuram a interface e a porta; o padrão local é `127.0.0.1:8000`.

## Usar a aplicação

1. Selecione um dia da semana.
2. Selecione um horário programado disponível para esse dia.
3. Acione **Estimar desvio**.

O resultado distingue atraso, adiantamento e ausência de desvio, com uma casa decimal. O histórico mostra contagem, mediana do desvio e proporção de atrasos maiores que cinco minutos, para o mesmo dia da semana e faixa de uma hora. A ficha expansível mostra métricas, períodos, parâmetros e origem dos dados. Horários incluem segundos para preservar exatamente os cenários da base e permanecem no contexto de Seattle.

## Modelo entregue

| Indicador | Valor |
|---|---:|
| Registros válidos | 6.547 |
| Período | 26/03/2016–27/05/2016 |
| Exemplos no teste reservado | 1.383 |
| MAE da árvore | 1,4390 min |
| MAE da referência de atraso zero | 1,5696 min |
| MAE da referência de mediana | 1,5209 min |

A árvore utiliza apenas `weekday` (segunda=0) e `scheduled_minutes` (horas × 60 + minutos + segundos/60). Não usa o horário realizado como entrada. Foram avaliadas 28 configurações apenas na validação. A versão v1 usa `criterion=absolute_error`, `max_depth=None`, `min_samples_leaf=10`, `random_state=42`.

Divisão temporal por dias completos: 37 dias/3.800 registros de treinamento, 13 dias/1.364 de validação e 13 dias/1.383 de teste. O ajuste final reúne treinamento e validação. O teste não participa da escolha dos parâmetros. Métricas detalhadas e os resultados de todas as configurações estão em `artifacts/v1/model.json`.

O MAE é uma média de erros absolutos, não uma garantia de erro máximo ou um percentual de acerto. A base histórica de 2016 não representa a operação atual, trânsito, clima ou posição de veículos. O histórico descritivo usa todo o período; sua proporção de atrasos não é uma probabilidade prevista pela árvore.

## Preparar e treinar novamente

O CSV original está incluído em `data/arrival_times.csv`. Sua origem e hash estão em `data/README.md`. Para recuperar exatamente a cópia da fonte, se necessário: `python scripts/download_data.py`.

```powershell
.\.venv\Scripts\python.exe train.py --version v2
```

Isso prepara os dados, seleciona os parâmetros, treina e avalia uma nova versão **sem substituir a referência**. Cada versão deve ter um nome novo; diretórios existentes nunca são sobrescritos.

Para gerar e ativar uma nova versão com decisão documentada:

```powershell
.\.venv\Scripts\python.exe train.py --version v3 --activate --reason "Reprodução com a mesma base; parâmetros e métricas comparados com v1."
```

A rotina grava `comparison.json`, comparando a versão anterior e a candidata, inclusive se a base e os períodos são iguais. A ativação exige justificativa quando há referência anterior e altera atomicamente `artifacts/active.json`. A decisão de ativar deve considerar a comparação, sem repetir ajustes com base no teste reservado. Reinicie o servidor para carregar a versão ativada. Para reproduzir v1, use o mesmo CSV, dependências, código e uma versão inédita; timestamps e nomes de versão mudam, mas as previsões permanecem iguais.

Limpeza: recorte de RTE 673/C, DIR S e STOP_ID 431; remoção de duplicatas exatas; exclusão de datas, identificadores e horários inválidos; exclusão de **todas** as linhas de chaves ambíguas `(TRIP_ID, OPD_DATE, DIR, STOP_ID)` restantes. Desvio = realizado − programado. Diferenças acima de +20 horas recebem −24h; abaixo de −20h recebem +24h, seguindo a convenção da fonte. Não se removem atrasos extremos por um limiar arbitrário. O dia da semana é derivado da data operacional.

A árvore é exportada em JSON, com validação de equivalência ao scikit-learn em todos os 6.547 exemplos. Não há pickle nem execução de objetos de modelo. Na inicialização, a aplicação valida manifesto, esquema, estrutura da árvore e hashes do modelo/base limpa. Recurso ausente ou incompatível gera HTTP 503 e mensagem na interface, sem produzir previsão.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/benchmark.py
```
