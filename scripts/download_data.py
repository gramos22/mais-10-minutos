"""Recupera a revisão fixa do CSV, verificando seu conteúdo antes de salvar."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

URL = 'https://gist.githubusercontent.com/jakevdp/82409002fcc5142a2add0168c274a869/raw/1bbabf78333306dbc45b9f33662500957b2b6dc3/arrival_times.csv'
EXPECTED = '549438cf42664a0e71c723173ed4ad5ab407884ca14a52aaa0eb0d404230453e'

if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1] / 'data/arrival_times.csv'
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != EXPECTED:
            raise SystemExit('O arquivo local difere da referência. Preserve-o antes de baixar outra cópia.')
        print('A cópia local já corresponde à revisão fixa.')
    else:
        with urlopen(URL, timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != EXPECTED:
            raise SystemExit('O conteúdo recebido difere do hash esperado; nada foi salvo.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        print('CSV baixado e verificado.')
