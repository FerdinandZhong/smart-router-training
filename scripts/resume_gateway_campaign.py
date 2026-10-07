"""Resume the frozen campaign with an explicitly recorded independent judge fallback."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import gateway_annotation_campaign as campaign
from smart_router.annotation.gateway_campaign import GatewayRunner,model_spec
from smart_router.annotation.pipeline import VERSION,atomic_json,digest
from smart_router.annotation.backends import request_body

class FallbackGateway(GatewayRunner):
    def __init__(self,output,limit=150,requests_per_minute=30,retry_errors=True):
        super().__init__(output,limit,10,retry_errors)

    def invoke(self,model,system,user,context):
        if context.get('role')!='judge':
            return super().invoke(model,system,user,context)
        key=digest({'pipeline_version':VERSION,'model':model,'body':request_body(model,system,user),'context':context})
        path=self.calls/(key+'.json')
        previous=json.loads(path.read_text()) if path.exists() else None
        if previous and previous['status']=='ok':return previous
        fallback=model_spec('JUDGE','gpt-5.4',model['api_key_file'])
        fallback.pop('class_id');fallback['max_output_tokens']=model['max_output_tokens']
        receipt=super().invoke(fallback,system,user,{**context,'fallback_for':model['model']})
        # Keep the physical call and failed Terra attempts, then record a logical
        # resolution with an explicit link to the actual fallback call.
        resolved={**receipt,'key':key,'requested_model':model['model'],
                  'fallback_model':fallback['model'],'fallback_call':receipt['key'],
                  'resolution':'independent_judge_fallback'}
        atomic_json(path,resolved)
        return resolved

if __name__=='__main__':
    atomic_json(campaign.OUT/'judge-fallback-policy.json',{
        'original_judge':'gpt-5.6-terra','fallback_judge':'gpt-5.4',
        'retain_successful_original_calls':True,'requests_per_minute':10,
        'estimated_cost_ceiling_usd':150,
        'candidate_policy':'retry original models; never substitute route labels'})
    campaign.GatewayRunner=FallbackGateway
    sys.argv=[sys.argv[0],'all']
    try:campaign.main()
    except Exception as exc:
        atomic_json(campaign.OUT/'campaign-state.json',{'status':'failed','error_type':type(exc).__name__})
        raise
