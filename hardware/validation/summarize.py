"""Summarize physical run-sheet entries by run, unit and declared condition.

No input rows means NOT_RUN. Exit status 2 means malformed records.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

FIELDS = ('run_id', 'unit_id', 'condition_id', 'trial_id', 'metric', 'value',
          'unit', 'instrument_id', 'evidence_id')
UNITS = {'bare_mass_g':'g', 'fitted_mass_g':'g', 'peak_contact_c':'degC',
         'comfort_nose_4h':'score', 'comfort_temple_4h':'score',
         'comfort_ear_4h':'score', 'hud_understood':'bool',
         'latency_s':'s', 'latency_failure':'bool'}


def read_trials(path):
    groups = defaultdict(lambda: defaultdict(dict))
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError('unexpected CSV header')
        for n,row in enumerate(reader,2):
            if None in row or any(not (v or '').strip() for v in row.values()):
                raise ValueError(f'line {n}: missing or extra field')
            r = {k:v.strip() for k,v in row.items()}
            metric, unit = r['metric'], r['unit']
            value = float(r['value'])
            if not math.isfinite(value) or UNITS.get(metric) != unit:
                raise ValueError(f'line {n}: invalid value, metric or unit')
            if ((unit == 'g' and value <= 0) or (unit == 's' and value < 0)
                    or (unit == 'score' and not 0 <= value <= 10)
                    or (unit == 'bool' and value not in (0,1))
                    or (metric == 'latency_failure' and value != 1)):
                raise ValueError(f'line {n}: value outside measurement domain')
            group = groups[r['run_id'],r['unit_id'],r['condition_id']]
            trial = r['trial_id']
            opposite = {'latency_s':'latency_failure','latency_failure':'latency_s'}.get(metric)
            if trial in group[metric] or (opposite and trial in group.get(opposite,{})):
                raise ValueError(f'line {n}: duplicate trial for metric')
            group[metric][trial] = value
    return groups


def summarize(groups):
    result = []
    for (run,unit,condition),metrics in sorted(groups.items()):
        record = {'run_id':run, 'unit_id':unit, 'condition_id':condition, 'metrics':{}}
        rows = record['metrics']
        for metric,trials in sorted(metrics.items()):
            values = list(trials.values())
            if metric in ('latency_s','latency_failure'):
                continue
            if metric == 'hud_understood':
                score = sum(values) / len(values)
                rows[metric] = {'participants':len(values), 'understood':int(sum(values)),
                                'fraction':score, 'sample_meets_90_percent':score >= 0.9}
            else:
                peak = max(values)
                item = {'n':len(values), 'max':peak, 'unit':UNITS[metric]}
                if metric == 'bare_mass_g':
                    item.update(sample_meets_50g=peak<=50, above_55g=peak>55)
                elif metric == 'peak_contact_c':
                    item['sample_at_or_below_41C'] = peak <= 41
                elif metric.startswith('comfort_'):
                    item['sample_at_or_below_2'] = peak <= 2
                rows[metric] = item
        if 'latency_s' in metrics or 'latency_failure' in metrics:
            success = sorted(metrics.get('latency_s',{}).values())
            failures = len(metrics.get('latency_failure',{}))
            n = len(success) + failures
            # Nearest rank across all attempts; failures sort after all finite readings.
            rank = math.ceil(.95*n)
            rows['capture_to_optical_hud'] = {
                'attempts':n, 'failed_or_timed_out':failures, 'rank':rank,
                'p95_s':success[rank-1] if rank<=len(success) else None,
                'assessment':('INSUFFICIENT_TRIALS' if n<50 else
                              'TARGET_MISSED' if rank>len(success) or success[rank-1]>6
                              else 'SAMPLE_MEETS_TARGET')}
        result.append(record)
    return {'status':'SAMPLES_ONLY' if result else 'NOT_RUN', 'groups':result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('measurements', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(summarize(read_trials(args.measurements)),indent=2,allow_nan=False))
    except (ValueError,OSError) as err:
        parser.error(str(err))


if __name__ == '__main__':
    main()
