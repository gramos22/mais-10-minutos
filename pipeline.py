"""Preparação determinística da base histórica. Nenhuma coleta durante consultas."""
import hashlib
from pathlib import Path
import pandas as pd

SOURCE = 'https://gist.githubusercontent.com/jakevdp/82409002fcc5142a2add0168c274a869/raw/1bbabf78333306dbc45b9f33662500957b2b6dc3/arrival_times.csv'
DAYS = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
FEATURES = ['weekday', 'scheduled_minutes']

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def prepare(path):
    raw = pd.read_csv(path, dtype=str)
    required = {'RTE', 'DIR', 'STOP_ID', 'TRIP_ID', 'OPD_DATE', 'SCH_STOP_TM', 'ACT_STOP_TM'}
    if not required.issubset(raw.columns):
        raise ValueError('CSV sem as colunas necessárias.')
    df = raw.loc[(raw.RTE == '673') & (raw.DIR == 'S') & (raw.STOP_ID == '431')].copy()
    audit = {'source_rows': len(raw), 'pilot_rows': len(df)}
    before = len(df)
    df = df.drop_duplicates()
    audit['exact_duplicates_removed'] = before - len(df)
    valid = df.SCH_STOP_TM.str.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d', na=False)
    valid &= df.ACT_STOP_TM.str.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d', na=False)
    dates = pd.to_datetime(df.OPD_DATE, format='%Y-%m-%d', errors='coerce')
    valid &= dates.notna() & df.TRIP_ID.notna()
    audit['invalid_rows_removed'] = int((~valid).sum())
    df = df.loc[valid].copy()
    ambiguous = df.duplicated(['TRIP_ID', 'OPD_DATE', 'DIR', 'STOP_ID'], keep=False)
    audit['ambiguous_rows_removed'] = int(ambiguous.sum())
    df = df.loc[~ambiguous].copy()
    if df.empty:
        raise ValueError('Não há registros válidos para o piloto.')
    scheduled = pd.to_timedelta(df.SCH_STOP_TM).dt.total_seconds()
    actual = pd.to_timedelta(df.ACT_STOP_TM).dt.total_seconds()
    delta = actual - scheduled
    crossing = delta.abs() > 20 * 3600
    delta = delta.where(delta <= 20 * 3600, delta - 86400)
    delta = delta.where(delta >= -20 * 3600, delta + 86400)
    audit['midnight_adjustments'] = int(crossing.sum())
    clean = pd.DataFrame({'date': df.OPD_DATE, 'weekday': pd.to_datetime(df.OPD_DATE).dt.dayofweek,
                          'time': df.SCH_STOP_TM, 'scheduled_minutes': scheduled / 60,
                          'delay': delta / 60})
    clean = clean.sort_values(['date', 'time'], kind='stable').reset_index(drop=True)
    audit['valid_rows'] = len(clean)
    return clean, audit

def split_days(df):
    days = sorted(df.date.unique())
    if len(days) < 10:
        raise ValueError('São necessários ao menos dez dias para avaliação temporal.')
    a, b = int(len(days) * .6), int(len(days) * .8)
    return tuple(df.loc[df.date.isin(part)].copy() for part in (days[:a], days[a:b], days[b:]))
