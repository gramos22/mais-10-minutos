"""Verificação real no Chromium. Dependência de desenvolvimento: playwright==1.49.1."""
import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / 'docs'
    report = {'at':datetime.now(timezone.utc).isoformat(), 'url':args.url, 'platform':platform.platform(),
              'conditions':'Chromium headless, sem limitação de CPU ou rede, servidor Waitress local, 1 usuário, 20 consultas sequenciais após carregar o modelo.',
              'viewports': [], 'errors': []}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        report['browser'] = browser.version
        for width in (1366, 360):
            page = browser.new_page(viewport={'width':width, 'height':900}, reduced_motion='reduce')
            page.on('pageerror', lambda error: report['errors'].append(str(error)))
            start = time.perf_counter()
            page.goto(args.url)
            page.wait_for_function('!document.getElementById("day").disabled')
            initial = time.perf_counter() - start
            assert not page.locator('#result').is_visible()
            page.screenshot(path=str(output / f'preview-{width}-initial.png'), full_page=True)
            # Formulário operável por teclado, com selects nativos.
            page.locator('#day').focus()
            page.keyboard.press('ArrowDown')
            page.keyboard.press('Tab')
            assert page.locator('#time').evaluate('(el) => el === document.activeElement')
            page.keyboard.press('ArrowDown')
            page.keyboard.press('Tab')
            assert page.locator('#submit').evaluate('(el) => el === document.activeElement')
            page.keyboard.press('Enter')
            page.wait_for_selector('#result:visible')
            info = page.request.get(args.url + '/api/info').json()
            scenarios = [(day, t) for day, times in info['catalog'].items() for t in times]
            durations = []
            for i in range(20):
                day, t = scenarios[i * (len(scenarios) // 20)]
                page.select_option('#day', day)
                assert not page.locator('#result').is_visible()
                page.select_option('#time', t)
                start = time.perf_counter()
                page.click('#submit')
                page.wait_for_selector('#result:visible')
                durations.append(time.perf_counter() - start)
                assert t in page.locator('#scenario').inner_text()
            # Captura representativa: dia útil ao fim da tarde.
            page.select_option('#day', '0')
            chosen = next(t for t in info['catalog']['0'] if t.startswith('17:'))
            page.select_option('#time', chosen)
            page.click('#submit')
            page.wait_for_selector('#result:visible')
            page.screenshot(path=str(output / f'preview-{width}.png'), full_page=True)
            page.locator('#evaluation summary').click()
            overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth')
            assert not overflow, f'Rolagem horizontal em {width}px'
            for selector in ['#query-form', '#result-region']:
                assert page.locator(selector).evaluate('(el) => el.scrollWidth <= el.clientWidth')
            page.screenshot(path=str(output / f'preview-{width}-details.png'), full_page=True)
            report['viewports'].append({'width':width, 'horizontal_overflow':overflow, 'keyboard':True,
                                        'initial_load_seconds':initial, 'query_seconds':durations,
                                        'within_3_seconds':sum(t <= 3 for t in durations), 'max_seconds':max(durations)})
            assert sum(t <= 3 for t in durations) >= 19
            # Uma falha de rede não pode manter uma previsão anterior na tela.
            page.route('**/api/estimate', lambda route: route.abort())
            page.click('#submit')
            page.wait_for_selector('#error:visible')
            assert not page.locator('#result').is_visible()
            page.unroute('**/api/estimate')
            page.close()
        # Falha ao carregar recursos e recuperação pelo botão de nova tentativa.
        page = browser.new_page()
        page.route('**/api/info', lambda route: route.fulfill(status=503, content_type='application/json', body=json.dumps({'error':'Base indisponível para teste.'})))
        page.goto(args.url)
        page.wait_for_selector('#error:visible')
        assert page.locator('#submit').is_disabled()
        page.unroute('**/api/info')
        page.click('#retry')
        page.wait_for_function('!document.getElementById("day").disabled')
        browser.close()
    assert not report['errors']
    (output / 'performance-browser.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
