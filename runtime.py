"""Carregamento verificado e inferência da árvore exportada, sem treinamento."""
import csv
import hashlib
import json
import math
import re
from pathlib import Path

FEATURES = ['weekday', 'scheduled_minutes']

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def predict_tree(tree, features):
    node = 0
    while tree['left'][node] != -1:
        value = features[tree['feature'][node]]
        # sklearn converte entradas para float32 antes de comparar os limiares.
        import struct
        value = struct.unpack('f', struct.pack('f', value))[0]
        node = tree['left'][node] if value <= tree['threshold'][node] else tree['right'][node]
    return float(tree['value'][node])

def load_bundle(root):
    active = json.loads((root / 'active.json').read_text(encoding='utf-8'))
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', active['version']):
        raise ValueError('Versão inválida.')
    folder = root / active['version']
    if digest(folder / 'model.json') != active['model_sha256']:
        raise ValueError('Modelo incompatível com o manifesto.')
    data = json.loads((folder / 'model.json').read_text(encoding='utf-8'))
    if data['schema'] != 1 or data['features'] != FEATURES or data['version'] != active['version']:
        raise ValueError('Formato de modelo incompatível.')
    if digest(folder / 'clean.csv') != data['clean_sha256']:
        raise ValueError('Base incompatível com o modelo.')
    with (folder / 'clean.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != data['audit']['valid_rows']:
        raise ValueError('Contagem de registros incompatível.')
    tree = data['tree']
    size = len(tree['left'])
    if not size or any(len(tree[k]) != size for k in ['right', 'feature', 'threshold', 'value']):
        raise ValueError('Árvore incompleta.')
    visited = set()
    def validate(i):
        if type(i) is not int or i < 0 or i >= size or i in visited:
            raise ValueError('Árvore inválida.')
        visited.add(i)
        if not math.isfinite(tree['value'][i]) or not math.isfinite(tree['threshold'][i]):
            raise ValueError('Modelo contém valor inválido.')
        if tree['left'][i] == -1:
            if tree['right'][i] != -1:
                raise ValueError('Folha inválida.')
        else:
            if tree['feature'][i] not in (0, 1):
                raise ValueError('Atributo inválido.')
            validate(tree['left'][i])
            validate(tree['right'][i])
    validate(0)
    if len(visited) != size:
        raise ValueError('Nós desconectados.')
    if not data['catalog']:
        raise ValueError('Sem opções de consulta.')
    for day, times in data['catalog'].items():
        if day not in list(map(str, range(7))) or not times or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d', t) for t in times):
            raise ValueError('Catálogo inválido.')
    return data

def estimate(bundle, day, time):
    if type(day) is not int or str(day) not in bundle['catalog']:
        raise ValueError('Selecione um dia da semana disponível.')
    if not isinstance(time, str) or time not in bundle['catalog'][str(day)]:
        raise ValueError('Selecione um horário disponível para esse dia.')
    h, m, s = map(int, time.split(':'))
    minutes = round(predict_tree(bundle['tree'], [day, h * 60 + m + s / 60]), 1)
    if minutes == 0:
        minutes = 0.0
    return {'minutes': minutes, 'kind': 'atraso' if minutes > 0 else 'adiantamento' if minutes < 0 else 'sem desvio',
            'day': day, 'time': time, 'hour': h,
            'history': bundle['history'].get(f'{day}-{h}'), 'version': bundle['version']}
