'use strict';
const $ = id => document.getElementById(id);
const days = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'];
const number = (value, digits = 1) => new Intl.NumberFormat('pt-BR', {minimumFractionDigits: digits, maximumFractionDigits: digits}).format(value);
const esc = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const date = value => value.split('-').reverse().join('/');
let info = null;
let requestNumber = 0;

async function api(path, options = {}) {
  const response = await fetch(path, {...options, signal: AbortSignal.timeout(15000)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Não foi possível concluir a consulta.');
  return data;
}
function showError(message) {
  $('error').textContent = message;
  $('error').hidden = false;
}
function resetResult() {
  requestNumber++;
  $('result').hidden = true;
  $('empty-state').hidden = false;
  $('error').hidden = true;
  $('result-badge').textContent = 'Modelo de regressão';
  $('submit').firstElementChild.textContent = 'Estimar desvio';
}
function updateTimes() {
  resetResult();
  const times = info.catalog[$('day').value] || [];
  $('time').replaceChildren(new Option('Selecione o horário', ''));
  times.forEach(time => $('time').add(new Option(time, time)));
  $('time').disabled = !times.length;
  $('submit').disabled = true;
}
function renderModel() {
  $('version').textContent = `Modelo ${info.version}`;
  $('total-observations').textContent = number(info.audit.valid_rows, 0);
  const e = info.evaluation;
  const labels = {train:'Treinamento', validation:'Validação', test:'Teste reservado'};
  $('model-content').innerHTML = `
    <p>Árvore de regressão (<strong>DecisionTreeRegressor</strong>), versão <strong>${esc(info.version)}</strong>.
    Critério: erro absoluto; profundidade máxima: ${esc(info.parameters.max_depth ?? 'sem limite')}; mínimo de exemplos por folha: ${esc(info.parameters.min_samples_leaf)}; semente: ${esc(info.parameters.random_state)}.</p>
    <h3>Erro absoluto médio no teste (MAE)</h3>
    <p>Distância média entre o desvio estimado e o observado, em minutos. Quanto menor, melhor. Não é um percentual de acerto.</p>
    <div class="metrics">${[['tree','Árvore de regressão'],['zero','Referência: atraso zero'],['median','Referência: mediana']].map(([key,label]) => `<div class="metric"><strong>${number(e.mae[key], 2)} min</strong><span>${label}</span></div>`).join('')}</div>
    <p>${e.mae.tree < Math.min(e.mae.zero, e.mae.median) ? 'Neste teste, a árvore apresentou menor MAE que as duas referências.' : 'Neste teste, a árvore não superou todas as referências simples. A estimativa deve ser interpretada com essa limitação.'} Mediana usada na referência: ${number(e.median_baseline_minutes, 2)} min, calculada apenas no conjunto de ajuste final.</p>
    <h3>Avaliação cronológica por dias completos</h3>
    <table><caption class="muted">Divisão aproximada de 60% / 20% / 20% dos dias</caption><thead><tr><th>Etapa</th><th>Período de 2016</th><th>Dias</th><th>Registros</th></tr></thead><tbody>${Object.entries(e.periods).map(([key, p]) => `<tr><td>${labels[key]}</td><td>${esc(date(p.start).slice(0,5))} – ${esc(date(p.end).slice(0,5))}</td><td>${p.days}</td><td>${number(p.count,0)}</td></tr>`).join('')}</tbody></table>
    <p>A configuração foi escolhida entre ${e.validation_trials.length} candidatas usando somente a validação (MAE escolhido: ${number(e.selected_validation_mae,2)} min). O ajuste final reúne treinamento e validação. O teste reservado não foi usado para selecionar parâmetros.</p>
    <h3>Erro no teste por dia da semana</h3><table><thead><tr><th>Dia</th><th>Exemplos</th><th>MAE (min)</th></tr></thead><tbody>${e.by_day.map(row => `<tr><td>${esc(row.day)}</td><td>${row.count}</td><td>${row.mae === null ? 'Sem dados' : number(row.mae,2)}</td></tr>`).join('')}</tbody></table>
    <h3>Preparação e rastreabilidade</h3><p>${number(info.audit.pilot_rows,0)} linhas no recorte original; ${info.audit.exact_duplicates_removed} duplicatas exatas removidas; ${info.audit.invalid_rows_removed} registros inválidos excluídos; ${info.audit.ambiguous_rows_removed} correspondências ambíguas excluídas; ${info.audit.midnight_adjustments} ajustes de meia-noite. Resultado: ${number(info.audit.valid_rows,0)} observações.</p>
    <p>Na passagem pela meia-noite, diferenças superiores a 20 horas são ajustadas em um dia, conforme o tratamento da fonte. O dia da semana corresponde à data operacional da base. Horários permanecem no contexto local de Seattle.</p>
    <p>SHA-256 do CSV original: <code>${esc(info.source_sha256)}</code></p>
    <p><a href="${esc(info.source_url)}" rel="noopener noreferrer" target="_blank">Acessar o CSV original ↗</a> · A consulta usa uma cópia local e não acessa a fonte externa.</p>
    <p>O resumo histórico utiliza todo o período disponível. Os dados não refletem o trânsito, o clima ou a operação atual. Não coletamos localização nem armazenamos histórico individual de consultas.</p>`;
}
async function load() {
  $('retry').hidden = true;
  $('error').hidden = true;
  try {
    info = await api('/api/info');
    $('day').replaceChildren(new Option('Selecione o dia', ''));
    days.forEach((name, day) => { if (info.catalog[day]) $('day').add(new Option(name, String(day))); });
    $('day').disabled = false;
    renderModel();
  } catch (error) {
    showError(error.name === 'TimeoutError' ? 'O carregamento demorou mais que o esperado. Tente novamente.' : error.message === 'Failed to fetch' ? 'Não foi possível conectar. Verifique sua conexão e tente novamente.' : error.message);
    $('version').textContent = 'Modelo indisponível';
    $('model-content').textContent = 'A avaliação ficará disponível quando a base e o modelo forem carregados.';
    $('day').replaceChildren(new Option('Dados indisponíveis', ''));
    $('retry').hidden = false;
  }
}
$('day').addEventListener('change', updateTimes);
$('time').addEventListener('change', () => {resetResult(); $('submit').disabled = !$('time').value;});
$('retry').addEventListener('click', load);
$('query-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!$('day').value || !$('time').value) return;
  resetResult();
  const current = requestNumber;
  $('submit').disabled = true;
  $('submit').firstElementChild.textContent = 'Calculando…';
  $('result-region').setAttribute('aria-busy', 'true');
  try {
    const result = await api('/api/estimate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({day:Number($('day').value),time:$('time').value})});
    if (current !== requestNumber) return;
    $('scenario').textContent = `${days[result.day]} · ${result.time} · Seattle`;
    $('minutes').textContent = `${result.minutes > 0 ? '+' : result.minutes < 0 ? '−' : ''}${number(Math.abs(result.minutes))}`;
    $('kind').textContent = result.kind === 'sem desvio' ? 'Sem desvio' : `de ${result.kind}`;
    $('prediction-description').textContent = result.minutes > 0 ? 'Chegada estimada após o horário programado.' : result.minutes < 0 ? 'Chegada estimada antes do horário programado.' : 'Sem diferença estimada em relação ao horário programado.';
    $('hour-window').textContent = `${String(result.hour).padStart(2,'0')}:00–${String(result.hour).padStart(2,'0')}:59`;
    $('history-stats').hidden = !result.history;
    $('no-history').hidden = Boolean(result.history);
    $('small-sample').hidden = !result.history || result.history.count >= 30;
    if (result.history) {
      $('count').textContent = number(result.history.count,0);
      $('median').textContent = `${number(result.history.median)} min`;
      $('proportion').textContent = `${number(result.history.over_five * 100)}%`;
    }
    $('empty-state').hidden = true;
    $('result').hidden = false;
    $('result-badge').textContent = `Modelo ${result.version}`;
    if (window.matchMedia('(max-width: 650px)').matches) $('result-region').scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block:'start'});
  } catch (error) {
    if (current === requestNumber) showError(error.name === 'TimeoutError' ? 'A consulta demorou mais que o esperado. Tente novamente.' : error.message === 'Failed to fetch' ? 'Não foi possível conectar. Tente novamente.' : error.message);
  } finally {
    $('result-region').setAttribute('aria-busy', 'false');
    if (current === requestNumber) {
      $('submit').disabled = false;
      $('submit').firstElementChild.textContent = 'Estimar desvio';
    }
  }
});
load();
