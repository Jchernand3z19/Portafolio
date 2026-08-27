#!/usr/bin/env bash
# Configura una sola vez la frontera Google Cloud necesaria para la primera carga.
# Requiere Cloud Shell autenticado con permisos para APIs, IAM, BigQuery y WIF.

set -euo pipefail

: "${PROJECT_ID:?Define PROJECT_ID con el proyecto Google Cloud que tendrá los datos}"
: "${DATASET_LOCATION:?Define DATASET_LOCATION; la ubicación del dataset no puede cambiar después}"

DATASET_ID="${DATASET_ID:-precios_sps}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-precios-sps-bigquery}"
POOL_ID="${POOL_ID:-precios-sps-github}"
PROVIDER_ID="${PROVIDER_ID:-github-portafolio}"
GITHUB_REPOSITORY_ID="1282475205"
GITHUB_MAIN_REF="refs/heads/main"
EXPECTED_ISSUER="https://token.actions.githubusercontent.com"
EXPECTED_CONDITION="assertion.repository_id=='${GITHUB_REPOSITORY_ID}' && assertion.ref=='${GITHUB_MAIN_REF}'"
EXPECTED_MAPPING="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.ref=assertion.ref"

if [[ ! "$DATASET_ID" =~ ^[A-Za-z_][A-Za-z0-9_]{0,1023}$ ]]; then
  echo "dataset_id_invalid" >&2
  exit 1
fi

if ! gcloud projects describe "$PROJECT_ID" --format='value(projectId)' >/dev/null; then
  echo "project_not_accessible:${PROJECT_ID}" >&2
  exit 1
fi

gcloud config set project "$PROJECT_ID" >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
if [[ -z "$PROJECT_NUMBER" ]]; then
  echo "project_number_unavailable" >&2
  exit 1
fi

printf 'Configurando APIs necesarias en %s...\n' "$PROJECT_ID"
gcloud services enable \
  bigquery.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project="$PROJECT_ID" \
  --quiet

SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" \
  --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --project="$PROJECT_ID" \
    --display-name="Precios SPS BigQuery runtime"
fi

# Los jobs se ejecutan a nivel proyecto; los datos se limitan al dataset.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/bigquery.jobUser" \
  --condition=None \
  --quiet >/dev/null

if bq show --format=json "${PROJECT_ID}:${DATASET_ID}" >"${TMPDIR:-/tmp}/precios-sps-dataset.json" 2>/dev/null; then
  EXISTING_LOCATION="$(python3 - "${TMPDIR:-/tmp}/precios-sps-dataset.json" <<'PY'
import json
import sys
from pathlib import Path
value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value.get("location", ""))
PY
)"
  if [[ "$EXISTING_LOCATION" != "$DATASET_LOCATION" ]]; then
    echo "dataset_location_mismatch:expected=${DATASET_LOCATION}:actual=${EXISTING_LOCATION}" >&2
    exit 1
  fi
else
  bq --location="$DATASET_LOCATION" mk \
    --dataset \
    --description="Precios de supermercados SPS" \
    "${PROJECT_ID}:${DATASET_ID}"
fi

# Data Editor se concede sólo al dataset, no a todo el proyecto.
bq query \
  --project_id="$PROJECT_ID" \
  --location="$DATASET_LOCATION" \
  --use_legacy_sql=false \
  "GRANT \`roles/bigquery.dataEditor\` ON SCHEMA \`${PROJECT_ID}.${DATASET_ID}\` TO \"serviceAccount:${SERVICE_ACCOUNT_EMAIL}\"" \
  >/dev/null

if ! gcloud iam workload-identity-pools describe "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --project="$PROJECT_ID" \
    --location=global \
    --display-name="Precios SPS GitHub" \
    --description="OIDC de GitHub Actions para la primera carga BigQuery"
fi

PROVIDER_JSON="${TMPDIR:-/tmp}/precios-sps-wif-provider.json"
if gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location=global \
  --workload-identity-pool="$POOL_ID" \
  --format=json >"$PROVIDER_JSON" 2>/dev/null; then
  python3 - "$PROVIDER_JSON" "$EXPECTED_ISSUER" "$EXPECTED_CONDITION" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_issuer = sys.argv[2]
expected_condition = sys.argv[3]
expected_mapping = {
    "google.subject": "assertion.sub",
    "attribute.repository_id": "assertion.repository_id",
    "attribute.ref": "assertion.ref",
}
if value.get("state") not in (None, "ACTIVE"):
    raise SystemExit("wif_provider_not_active")
if value.get("oidc", {}).get("issuerUri") != expected_issuer:
    raise SystemExit("wif_provider_issuer_mismatch")
if value.get("attributeCondition") != expected_condition:
    raise SystemExit("wif_provider_condition_mismatch")
if value.get("attributeMapping") != expected_mapping:
    raise SystemExit("wif_provider_mapping_mismatch")
PY
else
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --project="$PROJECT_ID" \
    --location=global \
    --workload-identity-pool="$POOL_ID" \
    --issuer-uri="$EXPECTED_ISSUER" \
    --attribute-mapping="$EXPECTED_MAPPING" \
    --attribute-condition="$EXPECTED_CONDITION"
fi

POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
WIF_PROVIDER="${POOL_RESOURCE}/providers/${PROVIDER_ID}"
WIF_MEMBER="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository_id/${GITHUB_REPOSITORY_ID}"

gcloud iam service-accounts add-iam-policy-binding "$SERVICE_ACCOUNT_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$WIF_MEMBER" \
  --quiet >/dev/null

cat <<EOF

Configuración Google Cloud lista.
Agrega estas cuatro Repository Variables en GitHub exactamente con estos valores:
PRECIOS_SPS_GCP_PROJECT_ID=${PROJECT_ID}
PRECIOS_SPS_BIGQUERY_DATASET_ID=${DATASET_ID}
PRECIOS_SPS_GCP_WIF_PROVIDER=${WIF_PROVIDER}
PRECIOS_SPS_GCP_SERVICE_ACCOUNT=${SERVICE_ACCOUNT_EMAIL}

La identidad federada acepta únicamente repository_id=${GITHUB_REPOSITORY_ID} y ref=${GITHUB_MAIN_REF}.
No se creó ninguna llave JSON de service account.
EOF
