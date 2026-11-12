from common import *
import collections
rs=load('maintenance/base_status_reports.csv')
for inst in sorted({r['installation_id'] for r in rs}):
    v=[r for r in rs if r['installation_id']==inst]
    print('==',inst,v[0]['installation_name'],len(v),v[0]['report_date'],v[-1]['report_date'])
    # run-length encode key fields
    for col in ('readiness_pct','aircraft_on_station','flight_ops_status','backup_power_status','generator_test_result','perimeter_sensor_status','production_status','facility_status'):
        runs=[]; 
        for r in v:
            x=r[col]
            if runs and runs[-1][0]==x: runs[-1][2]=r['report_date']
            else: runs.append([x,r['report_date'],r['report_date']])
        if len(runs)<=14: print('  ',col,[(a,b[5:],c[5:]) for a,b,c in runs])
        else: print('  ',col,'runs',len(runs),'distinct',len({a for a,b,c in runs}),[(a,b[5:]) for a,b,c in runs[:40]])
    rem=[(r['report_date'],r['remarks']) for r in v if r['remarks']]
    print('   remarks',len(rem)); [print('     ',x[0],x[1][:230]) for x in rem[:16]]
    print('   gen test dates',sorted({r['generator_last_test_date'] for r in v})[:40])
