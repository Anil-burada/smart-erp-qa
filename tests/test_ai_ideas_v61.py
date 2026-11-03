from fastapi.testclient import TestClient
from backend.api import app
from backend.ai_case_proposals import generate_ideas,workflow_metadata
from backend.approval_plans import read_workflow

def test_offline_ideas_are_unexecuted():
    output=generate_ideas('mock_erp','mock_pi_create','rules')
    assert output['provider']=='rules'
    assert {x['category'] for x in output['cases']}=={'positive','negative'}
    assert all(x['review_needed'] for x in output['cases'])

def test_ai_metadata_does_not_send_locators_or_recorded_values():
    wf=read_workflow('mock_erp','mock_pi_create')
    meta=workflow_metadata(wf)
    serialized=str(meta)
    assert '#save' not in serialized
    assert 'Demo Material' not in serialized
    assert 'http://127.0.0.1' not in serialized


def test_ai_api_offline_rules():
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        resp=client.post('/api/ai/test-cases',json={'project_id':'mock_erp','workflow_name':'mock_pi_create','provider':'rules'})
        assert resp.status_code==200
        assert len(resp.json()['cases'])>=1
