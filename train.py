"""Treinamento offline: python train.py --version v1 --activate."""
import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import sklearn
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_absolute_error
from pipeline import DAYS, FEATURES, SOURCE, prepare, sha256, split_days

ROOT = Path(__file__).resolve().parent

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def train(csv, output, version):
    df, audit = prepare(csv)
    training, validation, test = split_days(df)
    trials = []
    for depth in [2, 3, 4, 5, 6, 8, None]:
        for leaf in [10, 25, 50, 100]:
            params = dict(max_depth=depth, min_samples_leaf=leaf, criterion='absolute_error', random_state=42)
            model = DecisionTreeRegressor(**params).fit(training[FEATURES], training.delay)
            score = float(mean_absolute_error(validation.delay, model.predict(validation[FEATURES])))
            trials.append({'params': params, 'validation_mae': score})
    best = min(trials, key=lambda x: x['validation_mae'])
    fit = pd_concat(training, validation)
    model = DecisionTreeRegressor(**best['params']).fit(fit[FEATURES], fit.delay)
    prediction = model.predict(test[FEATURES])
    median = float(fit.delay.median())
    mae = lambda y, p: float(mean_absolute_error(y, p))
    scores = {'tree': mae(test.delay, prediction), 'zero': mae(test.delay, np.zeros(len(test))),
              'median': mae(test.delay, np.full(len(test), median))}
    by_day = []
    for day, name in enumerate(DAYS):
        mask = test.weekday.to_numpy() == day
        by_day.append({'day': name, 'count': int(mask.sum()),
                       'mae': mae(test.delay[mask], prediction[mask]) if mask.any() else None})
    periods = {name: {'start': part.date.min(), 'end': part.date.max(), 'days': int(part.date.nunique()), 'count': len(part)}
               for name, part in [('train', training), ('validation', validation), ('test', test)]}
    catalog = {str(day): sorted(part.time.unique().tolist()) for day, part in df.groupby('weekday')}
    history = {}
    for (day, hour), part in df.groupby(['weekday', (df.scheduled_minutes // 60).astype(int)]):
        history[f'{day}-{hour}'] = {'count': len(part), 'median': float(part.delay.median()),
                                   'over_five': float((part.delay > 5).mean())}
    tree = model.tree_
    nodes = {'left': tree.children_left.tolist(), 'right': tree.children_right.tolist(),
             'feature': tree.feature.tolist(), 'threshold': tree.threshold.tolist(),
             'value': tree.value[:, 0, 0].tolist()}
    # Exportação JSON evita desserialização executável de modelos na aplicação pública.
    from runtime import predict_tree
    exported = [predict_tree(nodes, row) for row in df[FEATURES].to_numpy()]
    if not np.allclose(exported, model.predict(df[FEATURES]), atol=1e-10):
        raise ValueError('A exportação diverge do modelo treinado.')
    output.mkdir(parents=True, exist_ok=False)
    df.to_csv(output / 'clean.csv', index=False)
    bundle = {'schema': 1, 'version': version, 'features': FEATURES, 'tree': nodes,
              'catalog': catalog, 'history': history, 'clean_sha256': sha256(output / 'clean.csv'),
              'source_sha256': sha256(csv), 'source_url': SOURCE, 'audit': audit,
              'period': {'start': df.date.min(), 'end': df.date.max()},
              'algorithm': 'DecisionTreeRegressor', 'parameters': best['params'],
              'evaluation': {'mae': scores, 'median_baseline_minutes': median, 'by_day': by_day,
                             'periods': periods, 'validation_trials': trials,
                             'selected_validation_mae': best['validation_mae']},
              'created_at': datetime.now(timezone.utc).isoformat(),
              'environment': {'python': platform.python_version(), 'sklearn': sklearn.__version__, 'numpy': np.__version__}}
    dump(output / 'model.json', bundle)
    return bundle

def pd_concat(*frames):
    import pandas as pd
    return pd.concat(frames, ignore_index=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path, default=ROOT / 'data/arrival_times.csv')
    p.add_argument('--version', required=True)
    p.add_argument('--activate', action='store_true')
    p.add_argument('--reason', default='')
    args = p.parse_args()
    import re
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', args.version):
        p.error('Versão deve conter apenas letras, números, hífen e sublinhado.')
    active = ROOT / 'artifacts/active.json'
    previous = json.loads(active.read_text()) if active.exists() else None
    if previous and args.activate and not args.reason.strip():
        p.error('Para substituir a referência, documente a decisão com --reason.')
    output = ROOT / 'artifacts' / args.version
    bundle = train(args.csv, output, args.version)
    comparison = {'candidate': args.version, 'candidate_mae': bundle['evaluation']['mae'],
                  'previous': previous, 'reason': args.reason or 'Primeira versão de referência.', 'activated': args.activate}
    if previous:
        old = json.loads((ROOT / 'artifacts' / previous['version'] / 'model.json').read_text(encoding='utf-8'))
        comparison.update(reference_mae=old['evaluation']['mae'],
                          same_source=old['source_sha256'] == bundle['source_sha256'],
                          same_periods=old['evaluation']['periods'] == bundle['evaluation']['periods'])
    dump(output / 'comparison.json', comparison)
    if args.activate:
        temporary = active.with_suffix('.tmp')
        dump(temporary, {'version': args.version, 'model_sha256': sha256(output / 'model.json')})
        temporary.replace(active)
    print(json.dumps({'version': args.version, 'audit': bundle['audit'], 'test_mae': bundle['evaluation']['mae']}, indent=2))

if __name__ == '__main__':
    main()
