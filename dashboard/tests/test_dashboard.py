import csv
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from copy import deepcopy
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(HERE),str(HERE.parent/'src')]
from cosanum_dashboard.experiments import bootstrap,validate,prepare,run_experiment,read
from cosanum_dashboard.server import Dashboard,make_server
from cosanum_sim.inputs import sha


def payload():
    return dict(values=bootstrap(HERE.parent,HERE)['defaults'],solutions=[True]*6+[False,False],options=bootstrap(HERE.parent,HERE)['option_defaults'],
                mode='annual_same_volume',seed=600,replications=1)


class InputsAndPolicies(unittest.TestCase):
    def setUp(self):self.spec=bootstrap(HERE.parent,HERE)

    def test_defaults_bound_to_packaged_evidence(self):
        self.assertEqual(self.spec['defaults'],dict(demand=350,days=2,practice=3,group=30,wait=14))

    def test_bad_inputs_do_not_create_runs(self):
        examples=[]
        for key,value in [('demand',True),('practice',float('nan')),('group',3),('days',2.5),('wait',0)]:
            p=payload();p['values'][key]=value;examples.append(p)
        for key,value in [('seed',True),('replications',2),('mode',['unsafe']),('solutions',[True]*6)]:
            p=payload();p[key]=value;examples.append(p)
        p=payload();p['arbitrary_file']='../source';examples.append(p)
        for p in examples:
            with self.subTest(p=p),self.assertRaises(ValueError):validate(p,self.spec)

    def test_recovery_cannot_silently_create_required_policies(self):
        for absent in (0,4):
            p=payload();p['solutions'][absent]=False
            with self.assertRaisesRegex(ValueError,'Recovery'):validate(p,self.spec)

    def test_arbitrary_planning_only_keeps_ist_bypass_and_review(self):
        p=payload();p['solutions']=[False,False,False,True,False,False,False,False]
        x=prepare(HERE.parent,p,self.spec,300);c=x['chosen']
        self.assertEqual(c.planning_delay,0);self.assertFalse(c.deadline_enabled)
        self.assertEqual(c.urgency_review.interval_minutes,21*1440)
        self.assertEqual(x['recognition'],2880);self.assertEqual(c.workflow.proof_delay,30)
        self.assertIsNone(c.priority);self.assertFalse(c.joined_scheduling)
        self.assertTrue(c.use_baseline_delivery);self.assertEqual(c.phase_allocation,'legacy')
        self.assertEqual(c.workflow.coordination_minutes,5)

    def test_group_target_changes_policy_not_demand(self):
        p=payload();a=prepare(HERE.parent,p,self.spec,300)
        p['values']['group']=5;b=prepare(HERE.parent,p,self.spec,300)
        self.assertEqual(a['underlying'],b['underlying'])
        self.assertEqual(b['chosen'].target,5);self.assertEqual(b['chosen'].capacity,30)
        self.assertEqual(a['baseline'],b['baseline'])

    def test_source_stock_frozen_and_synthetic(self):
        p=payload();p['mode']='frozen_backlog';x=prepare(HERE.parent,p,self.spec,300)
        self.assertEqual(len(x['underlying']),1305)
        self.assertTrue(all(r.cohort_id=='initial' and r.person_id.startswith('synthetic-') for r in x['underlying']))
        self.assertEqual(sum(x['topics'][r.topic_id].priority==1 for r in x['underlying']),191)

    def test_duration_sensitivity_preserves_source_and_changes_both_partners(self):
        p=payload();p['values']['practice']=2.5;x=prepare(HERE.parent,p,self.spec,300)
        self.assertEqual(x['baseline'].workflow.practice_duration,150)
        self.assertEqual(x['chosen'].workflow.practice_duration,150)
        original=read(HERE.parent/'config/source_values.json')
        self.assertEqual(next(i['value'] for i in original['values'] if i['input_id']=='practice_standard_minutes'),180)


class EngineIntegration(unittest.TestCase):
    def test_standard_pair_reproduces_saved_outputs_and_manifest(self):
        library=read(HERE/'static/library.json')
        before={str(p):sha(p) for p in (HERE.parent).rglob('*') if p.is_file() and '__pycache__' not in str(p)}
        with tempfile.TemporaryDirectory() as directory:
            dest=Path(directory)/'run';result=run_experiment(HERE.parent,HERE,dest,payload())
            for row in result['rows']:
                expected=next(r for r in library['runs'] if r['case_id']==row['case_id'] and r['scenario']==row['scenario'] and r['replication']==600)
                for key,value in row.items():
                    if key in expected and key!='fixture_hash':
                        if isinstance(value,float) or isinstance(expected[key],float):
                            self.assertAlmostEqual(value,expected[key],places=7,msg=(row['scenario'],key))
                        else:
                            self.assertEqual(value,expected[key],(row['scenario'],key))
                self.assertAlmostEqual(row['gross_chf']-row['credit_chf'],row['net_chf'])
            self.assertEqual(len({r['fixture_hash'] for r in result['rows']}),1)
            self.assertTrue(all(x['lower'] is None and x['n']==1 for x in result['paired']))
            manifest=read(dest/'experiment_manifest.json')
            self.assertTrue(all(sha(dest/k)==v for k,v in manifest['files'].items()))
            with self.assertRaises(FileExistsError):run_experiment(HERE.parent,HERE,dest,payload())
        self.assertEqual(before,{str(p):sha(p) for p in (HERE.parent).rglob('*') if p.is_file() and '__pycache__' not in str(p)})

    def test_joined_standard_keeps_saved_pipeline_results(self):
        p=payload();p['solutions'][6]=True
        library=read(HERE/'static/library.json')
        with tempfile.TemporaryDirectory() as directory:
            result=run_experiment(HERE.parent,HERE,Path(directory)/'joined',p)
        selected=next(r for r in result['rows'] if r['scenario']=='S7_RECOVERY_JOINED')
        expected=next(r for r in library['runs'] if r['case_id']=='annual_same_volume' and r['scenario']=='S7_RECOVERY_JOINED' and r['replication']==600)
        for key in ('training_completed','common_target_service','joined_practice_reservations','joined_planning_failures','net_chf'):
            if isinstance(selected[key],float) or isinstance(expected[key],float):
                self.assertAlmostEqual(selected[key],expected[key],places=7,msg=key)
            else:
                self.assertEqual(selected[key],expected[key])
        self.assertGreater(selected['joined_practice_reservations'],0)

    def test_five_predeclared_pairs_use_paired_differences(self):
        p=payload();p['replications']=5;p['values'].update(demand=200,days=4,practice=1)
        p['solutions']=[False,False,False,True,False,False,False,False]
        with tempfile.TemporaryDirectory() as directory:
            result=run_experiment(HERE.parent,HERE,Path(directory)/'five',p)
        self.assertEqual(len(result['rows']),10)
        for metric in ('net_chf','training_completed'):
            paired=next(r for r in result['paired'] if r['metric']==metric)
            differences=[]
            for rep in range(600,605):
                a=next(r for r in result['rows'] if r['replication']==rep and r['scenario']=='CUSTOM')
                b=next(r for r in result['rows'] if r['replication']==rep and r['scenario']=='S0')
                self.assertEqual(a['fixture_hash'],b['fixture_hash']);differences.append(a[metric]-b[metric])
            self.assertEqual(paired['n'],5);self.assertAlmostEqual(paired['mean'],sum(differences)/5)
            self.assertIsNone(paired['lower']);self.assertEqual(paired['precision_status'],'descriptive_only')


class HTTPIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=Dashboard(HERE,Path(self.tmp.name))
        self.server=make_server(self.app);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.thread.join();self.server.server_close();self.app.close();self.tmp.cleanup()
    def request(self,path,method='GET',body=None,token=True,origin=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=60)
        headers={'Content-Type':'application/json'}
        if token:headers['X-Cosanum-Token']=self.app.token
        if origin:headers['Origin']=origin
        conn.request(method,path,json.dumps(body) if body is not None else None,headers)
        response=conn.getresponse();content=response.read();status=response.status;conn.close()
        return status,content
    def test_origin_token_path_and_input_validation(self):
        self.assertEqual(self.request('/api/library',token=False)[0],403)
        self.assertEqual(self.request('/api/library',origin='https://example.org')[0],403)
        self.assertEqual(self.request('/../runtime/config/source_values.json')[0],404)
        self.assertEqual(self.request('/api/experiments','POST',{'bad':1})[0],400)
        self.assertEqual(self.request('/api/bootstrap')[0],200)
        self.assertEqual(self.request('/')[0],200)
    def test_real_job_export_and_restart_history(self):
        p=payload();p['values'].update(demand=200,days=4,practice=1);p['solutions']=[False]*8
        status,raw=self.request('/api/experiments','POST',p);self.assertEqual(status,202);job=json.loads(raw)
        deadline=time.monotonic()+60
        while job['status']=='running' and time.monotonic()<deadline:
            time.sleep(.05);status,raw=self.request('/api/experiments/'+job['id']);job=json.loads(raw)
        self.assertEqual(job['status'],'complete',job)
        self.assertEqual(self.request('/api/experiments/'+job['id']+'/result')[0],200)
        status,content=self.request('/api/experiments/'+job['id']+'/export')
        self.assertEqual(status,200);self.assertTrue(content.startswith(b'PK'))
        restarted=Dashboard(HERE,Path(self.tmp.name))
        try:self.assertEqual(restarted.status(job['id'])['status'],'complete')
        finally:restarted.close()


if __name__=='__main__':unittest.main()
