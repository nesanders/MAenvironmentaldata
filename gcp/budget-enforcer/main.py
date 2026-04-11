"""Cloud Function: remove public GCS read access when AMEND billing budget hits 100%.

Trigger: Eventarc (Cloud Functions gen2) listening to the billing-alerts Pub/Sub topic.
The billing budget publishes a Pub/Sub message to projects/openamend/topics/billing-alerts
at each threshold (50%, 80%, 100%). Eventarc delivers it to this function as a standard
Pub/Sub event — event['data'] is a base64-encoded JSON payload from the Cloud Billing API.

At >= 100% of the $5/month budget, removes the allUsers:objectViewer IAM binding from
gs://openamend-data, stopping public downloads without disabling the whole project.

To re-enable public access after the month rolls over (and spend resets):
    gsutil iam ch allUsers:objectViewer gs://openamend-data

Deployed via:
    gcloud functions deploy budget-enforcer \
      --gen2 \
      --runtime python311 \
      --trigger-topic billing-alerts \
      --entry-point enforce_budget \
      --region us-east1 \
      --project openamend \
      --service-account budget-enforcer@openamend.iam.gserviceaccount.com
"""

import base64
import json
import logging
import subprocess

BUCKET = 'gs://openamend-data'
SPEND_THRESHOLD = 1.0  # 100% of budget


def enforce_budget(event, context):
    """Pub/Sub-triggered function. Removes allUsers access if budget >= threshold."""
    try:
        payload = json.loads(base64.b64decode(event['data']).decode('utf-8'))
    except Exception as e:
        logging.error('Failed to decode Pub/Sub message: %s', e)
        return

    cost_amount = float(payload.get('costAmount', 0))
    budget_amount = float(payload.get('budgetAmount', 1))
    alert_threshold = float(payload.get('alertThresholdExceeded', 0))

    logging.info(
        'Budget alert: cost=%.2f budget=%.2f threshold=%.0f%%',
        cost_amount, budget_amount, alert_threshold * 100,
    )

    if alert_threshold < SPEND_THRESHOLD:
        logging.info('Threshold %.0f%% < 100%%, no action taken.', alert_threshold * 100)
        return

    logging.warning(
        'Spend $%.2f has reached $%.2f budget (%.0f%%). Removing public GCS access.',
        cost_amount, budget_amount, alert_threshold * 100,
    )

    result = subprocess.run(
        ['gsutil', 'iam', 'ch', '-d', 'allUsers:objectViewer', BUCKET],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        logging.warning('Public access removed from %s. To restore: gsutil iam ch allUsers:objectViewer %s', BUCKET, BUCKET)
    else:
        logging.error('gsutil iam ch failed: %s', result.stderr)
