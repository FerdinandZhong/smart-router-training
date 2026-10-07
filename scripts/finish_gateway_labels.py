"""Recover remaining judge transport errors and export a new immutable bundle."""
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import gateway_annotation_campaign as campaign
from resume_gateway_campaign import FallbackGateway
from smart_router.annotation.pipeline import atomic_json,run
from smart_router.annotation.gateway_campaign import Budget
from smart_router.data.pilot_bundle import validate_bundle
from export_smoke_training_data import export

def main():
    frozen=campaign.freeze_config()
    baseline=campaign.OUT/'pre-recovery-20261003'
    baseline.mkdir(exist_ok=True)
    for name in ['silver_labels.jsonl','annotated.jsonl','report.json','campaign-summary.json']:
        source=campaign.OUT/name
        if source.exists() and not (baseline/name).exists():shutil.copy2(source,baseline/name)
    campaign.GatewayRunner=FallbackGateway
    atomic_json(campaign.OUT/'campaign-state.json',{'status':'running','phase':'recover_remaining_judges'})
    # Successful calls are cached; only retryable errors below three attempts run.
    campaign.judge_stage(frozen)
    with patch('smart_router.annotation.backends.call',side_effect=AssertionError('Finalization cannot call network')):
        report=run(frozen,campaign.OUT,live=True)
    destination=ROOT/'data/pilot/gateway-pilot-v1-final'
    if destination.exists():raise RuntimeError('Final output already exists; refusing overwrite')
    manifest=export(campaign.SOURCE,[campaign.OUT/'silver_labels.jsonl'],destination,
                    dataset_id='gateway-pilot-v1-final',purpose='pilot_training')
    validate_bundle(destination)
    summary=json.loads((baseline/'campaign-summary.json').read_text())
    summary.update(artifact=str(destination),class_support=manifest['class_support'],
                   annotation_report=report,conservative_estimated_campaign_spend_usd=Budget(campaign.OUT/'cost-ledger.jsonl',150).committed(),
                   previous_export_preserved=str(ROOT/'data/pilot/gateway-pilot-v1'))
    atomic_json(campaign.OUT/'campaign-summary.json',summary)
    atomic_json(campaign.OUT/'campaign-state.json',{'status':'completed','phase':'exported_final'})
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
