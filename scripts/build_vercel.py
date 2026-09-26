"""Valida o modelo pronto e prepara os recursos públicos, sem treinar."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import load_bundle

if __name__ == '__main__':
    bundle = load_bundle(ROOT / 'artifacts')
    shutil.copytree(ROOT / 'static', ROOT / 'public/static', dirs_exist_ok=True)
    print(f"Modelo {bundle['version']} verificado; recursos estáticos preparados.")
