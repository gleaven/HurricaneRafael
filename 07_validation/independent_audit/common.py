import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, '05_other_sources')
REG = os.path.join(ROOT, '06_data_streams')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
D0_EPOCH = 1820880000
LANDFALL = '2027-09-14T06:00:00'
def vessels():
    return json.load(open(os.path.join(REG, 'vessels.json')))['vessels']
