"""Mede HTTP no endereço fornecido; não confundir com a medição no navegador."""
import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

def run(base):
    first = time.perf_counter()
    with urlopen(base + '/api/info', timeout=30) as response:
        info = json.load(response)
    initial = time.perf_counter() - first
    scenarios = [(int(day), t) for day, times in info['catalog'].items() for t in times]
    results = []
    for i in range(20):
        day, t = scenarios[i * (len(scenarios) // 20)]
        request = Request(base + '/api/estimate', data=json.dumps({'day':day,'time':t}).encode(), headers={'Content-Type':'application/json'})
        start = time.perf_counter()
        with urlopen(request, timeout=10) as response:
            value = json.load(response)
            assert 'minutes' in value
        results.append(time.perf_counter() - start)
    return {'at':datetime.now(timezone.utc).isoformat(), 'url':base, 'platform':platform.platform(),
            'mode':'20 requisições HTTP sequenciais; modelo carregado; sem simulação de rede',
            'initial_request_seconds':initial, 'seconds':results, 'within_3_seconds':sum(t <= 3 for t in results),
            'max_seconds':max(results), 'public_environment':base.startswith('https://')}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', default='docs/performance-http.json')
    args = parser.parse_args()
    result = run(args.url.rstrip('/'))
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result['within_3_seconds'] >= 19 else 1)
