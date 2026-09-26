import copy
import json
import shutil
from pathlib import Path
import pandas as pd
import pytest
from app import create_app
from pipeline import prepare, split_days
from runtime import estimate, load_bundle, predict_tree

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def bundle():
    return load_bundle(ROOT / 'artifacts')

def test_original_dataset_and_temporal_split():
    df, audit = prepare(ROOT / 'data/arrival_times.csv')
    assert audit['valid_rows'] == 6547
    assert audit['invalid_rows_removed'] == 83
    assert audit['ambiguous_rows_removed'] == 4
    training, validation, test = split_days(df)
    assert training.date.max() < validation.date.min() < test.date.min()
    assert validation.date.max() < test.date.min()
    assert len(training) + len(validation) + len(test) == len(df)
    assert set(training.date).isdisjoint(test.date)

def test_midnight_duplicates_ambiguity_and_invalid_times(tmp_path):
    base = dict(OPD_DATE='2016-03-26', RTE='673', DIR='S', STOP_ID='431')
    records = [dict(base, TRIP_ID='1', SCH_STOP_TM='23:59:00', ACT_STOP_TM='00:01:00'),
               dict(base, TRIP_ID='2', SCH_STOP_TM='00:01:00', ACT_STOP_TM='23:59:00'),
               dict(base, TRIP_ID='3', SCH_STOP_TM='12:00:00', ACT_STOP_TM='12:01:00'),
               dict(base, TRIP_ID='3', SCH_STOP_TM='12:00:00', ACT_STOP_TM='12:02:00'),
               dict(base, TRIP_ID='4', SCH_STOP_TM='29:00:00', ACT_STOP_TM='12:00:00')]
    records.append(records[0].copy())
    path = tmp_path / 'input.csv'
    pd.DataFrame(records).to_csv(path, index=False)
    df, audit = prepare(path)
    assert sorted(df.delay) == [-2, 2]
    assert audit['exact_duplicates_removed'] == 1
    assert audit['ambiguous_rows_removed'] == 2
    assert audit['invalid_rows_removed'] == 1

@pytest.mark.parametrize('body', [None, [], {}, {'day': True, 'time': '12:00:00'}, {'day': -1, 'time':'12:00:00'},
                                    {'day': 1.0, 'time':'12:00:00'}, {'day': 7, 'time':'12:00:00'},
                                    {'day': 0, 'time':'12:00'}, {'day': 0, 'time':[]},
                                    {'day': 0, 'time':'12:00:00', 'model':'evil'}])
def test_invalid_api_inputs(body):
    client = create_app().test_client()
    assert client.post('/api/estimate', json=body).status_code == 400

def test_all_observed_options_are_predictable(bundle):
    for day, times in bundle['catalog'].items():
        for time in times:
            result = estimate(bundle, int(day), time)
            assert isinstance(result['minutes'], float)
            assert result['history']['count'] > 0
    client = create_app().test_client()
    day = next(iter(bundle['catalog']))
    response = client.post('/api/estimate', json={'day':int(day), 'time':bundle['catalog'][day][0]})
    assert response.status_code == 200
    assert 'Set-Cookie' not in response.headers
    assert response.headers['Cache-Control'] == 'no-store'

def test_absent_history_is_null(bundle):
    modified = copy.deepcopy(bundle)
    modified['history'] = {}
    assert estimate(modified, 0, modified['catalog']['0'][0])['history'] is None

@pytest.mark.parametrize('mode', ['missing', 'corrupt_model', 'corrupt_data'])
def test_missing_or_incompatible_resources(tmp_path, mode):
    if mode != 'missing':
        shutil.copytree(ROOT / 'artifacts', tmp_path / 'artifacts')
        target = tmp_path / 'artifacts/v1' / ('model.json' if mode == 'corrupt_model' else 'clean.csv')
        target.write_text('invalid', encoding='utf-8')
    client = create_app(tmp_path / 'artifacts').test_client()
    assert client.get('/').status_code == 200
    assert client.get('/health').status_code == 503
    assert client.get('/api/info').status_code == 503
    response = client.post('/api/estimate', json={'day':0,'time':'12:00:00'})
    assert response.status_code == 503 and 'minutes' not in response.json

def test_tree_export_and_reproducibility(bundle):
    from sklearn.tree import DecisionTreeRegressor
    import numpy as np
    from pipeline import FEATURES
    df, _ = prepare(ROOT / 'data/arrival_times.csv')
    a, b, c = split_days(df)
    final = pd.concat([a,b])
    model = DecisionTreeRegressor(**bundle['parameters']).fit(final[FEATURES], final.delay)
    actual = model.predict(df[FEATURES])
    exported = [predict_tree(bundle['tree'], row) for row in df[FEATURES].to_numpy()]
    assert np.allclose(actual, exported, atol=1e-10)
    measured = float(np.abs(model.predict(c[FEATURES]) - c.delay).mean())
    assert measured == pytest.approx(bundle['evaluation']['mae']['tree'])

def test_no_training_or_upload_routes():
    client = create_app().test_client()
    assert client.post('/train').status_code == 404
    assert client.post('/upload').status_code == 404
    assert client.post('/api/estimate', data='x' * 3000, content_type='application/json').status_code == 413
