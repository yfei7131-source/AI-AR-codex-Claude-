"""Run the inherited V4 audit on native streams containing empty PRIMITIVE records."""
from pathlib import Path
import copy
import importlib.util
import json
import sys

design_root = Path(__file__).resolve().parents[1] / 'evt1-h03-r11-master/hardware/evt1-native-eda-20261118'
if not design_root.is_dir():
    design_root = Path(__file__).resolve().parents[2]
path = design_root / 'h03-v4-dfm-u11-2n2-route/independent_hdi_dfm_auditor_v4.py'
spec = importlib.util.spec_from_file_location('ev1_v4_audit', path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
from prepare_hierarchy import Record
original = Record.__init__

def parse(self, line):
    header, value = line.split(b'||', 1)
    if json.loads(header).get('type') != 'PRIMITIVE' or value.rstrip(b'\r\n') != b'|':
        original(self, line)
        return
    self.header = json.loads(header)
    self.payload = None
    self.tail = value
    self.original = line
    self._header = copy.deepcopy(self.header)
    self._payload = None

Record.__init__ = parse
audit.main()
