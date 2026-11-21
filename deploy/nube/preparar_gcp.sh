#!/usr/bin/env bash
# Prepara Google Cloud para AutoCaja, UNA sola vez, dentro del nivel gratuito.
# Se corre en Cloud Shell (la terminal del navegador en console.cloud.google.com), con el
# proyecto ya elegido arriba:
#
#   bash preparar_gcp.sh
#
# Crea (sin costo dentro de los límites gratis):
#   - Artifact Registry «autocaja» con limpieza: guarda solo las 2 últimas imágenes (< 0,5 GB).
#   - Secretos: clave de caja, clave de la app de notificaciones y token de Hugging Face (3 de 6
#     versiones gratis).
#   - Dos cuentas de servicio: una para el quiosco (solo lee sus secretos) y otra para que GitHub
#     despliegue sin claves guardadas (Workload Identity Federation, solo para este repositorio).
#   - Un presupuesto de US$1 que avisa por correo al 50, 90 y 100 %.
# El servicio de Cloud Run lo crea el primer despliegue del CD, con los topes de costo.
set -euo pipefail

REGION="us-central1"            # región de precio más bajo (Tier 1)
REPO_GITHUB="Nakusuo/autocheckout-vision"
PROYECTO="$(gcloud config get-value project 2>/dev/null)"
if [ -z "$PROYECTO" ]; then
  echo "Elige primero un proyecto (arriba en la consola) y vuelve a correr el script." >&2
  exit 1
fi
NUMERO="$(gcloud projects describe "$PROYECTO" --format='value(projectNumber)')"
SA_RUN="autocaja-run@${PROYECTO}.iam.gserviceaccount.com"
SA_DEPLOY="autocaja-deploy@${PROYECTO}.iam.gserviceaccount.com"
echo "== Proyecto: $PROYECTO ($NUMERO), región $REGION"

echo "== Activando servicios"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  billingbudgets.googleapis.com cloudbilling.googleapis.com

echo "== Artifact Registry con limpieza automática"
gcloud artifacts repositories describe autocaja --location="$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create autocaja --repository-format=docker --location="$REGION" \
    --description="Imágenes de AutoCaja (solo las 2 últimas)"
LIMPIEZA="$(mktemp)"
cat > "$LIMPIEZA" <<'JSON'
[
  {"name": "borrar-todo", "action": {"type": "Delete"}, "condition": {"tagState": "any"}},
  {"name": "guardar-2-ultimas", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 2}}
]
JSON
gcloud artifacts repositories set-cleanup-policies autocaja --location="$REGION" \
  --policy="$LIMPIEZA" --no-dry-run

echo "== Secretos"
crear_secreto() {  # nombre valor
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    echo "   $1 ya existe: se deja igual"
  else
    printf %s "$2" | gcloud secrets create "$1" --data-file=- --replication-policy=automatic
  fi
}
CAJA="$(openssl rand -hex 10)"
NOTIFICADOR="$(openssl rand -hex 16)"
crear_secreto kiosk-caja-key "$CAJA"
crear_secreto kiosk-notifier-key "$NOTIFICADOR"
if ! gcloud secrets describe hf-token >/dev/null 2>&1; then
  read -rsp "Pega tu token de LECTURA de Hugging Face (no se verá) y Enter: " HF
  echo
  crear_secreto hf-token "$HF"
fi

echo "== Cuenta de servicio del quiosco (solo lee sus secretos)"
gcloud iam service-accounts describe "$SA_RUN" >/dev/null 2>&1 ||
  gcloud iam service-accounts create autocaja-run --display-name="AutoCaja (Cloud Run)"
for s in kiosk-caja-key kiosk-notifier-key hf-token; do
  gcloud secrets add-iam-policy-binding "$s" --member="serviceAccount:$SA_RUN" \
    --role=roles/secretmanager.secretAccessor >/dev/null
done

echo "== Cuenta de servicio para GitHub (despliega, sin claves guardadas)"
gcloud iam service-accounts describe "$SA_DEPLOY" >/dev/null 2>&1 ||
  gcloud iam service-accounts create autocaja-deploy --display-name="AutoCaja (GitHub Actions)"
for rol in roles/run.admin roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "$PROYECTO" --member="serviceAccount:$SA_DEPLOY" \
    --role="$rol" --condition=None >/dev/null
done
gcloud iam service-accounts add-iam-policy-binding "$SA_RUN" \
  --member="serviceAccount:$SA_DEPLOY" --role=roles/iam.serviceAccountUser >/dev/null

gcloud iam workload-identity-pools describe github --location=global >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools create github --location=global --display-name="GitHub"
gcloud iam workload-identity-pools providers describe github --location=global \
  --workload-identity-pool=github >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools providers create-oidc github --location=global \
    --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == '${REPO_GITHUB}'"
gcloud iam service-accounts add-iam-policy-binding "$SA_DEPLOY" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${NUMERO}/locations/global/workloadIdentityPools/github/attribute.repository/${REPO_GITHUB}" >/dev/null

echo "== Presupuesto de US\$1 con avisos por correo"
CUENTA="$(gcloud billing projects describe "$PROYECTO" --format='value(billingAccountName)' | sed 's|billingAccounts/||')"
if [ -n "$CUENTA" ] && ! gcloud billing budgets list --billing-account="$CUENTA" \
    --format='value(displayName)' | grep -qx "AutoCaja tope"; then
  gcloud billing budgets create --billing-account="$CUENTA" --display-name="AutoCaja tope" \
    --budget-amount=1USD --filter-projects="projects/${PROYECTO}" \
    --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0
fi

PROVEEDOR="projects/${NUMERO}/locations/global/workloadIdentityPools/github/providers/github"
cat <<FIN

==================================================================
LISTO. Copia estas 3 líneas y pégalas en la terminal de tu PC
(dentro de la carpeta del proyecto). No son secretas:

gh variable set GCP_PROYECTO --body "${PROYECTO}"
gh variable set GCP_WIF_PROVIDER --body "${PROVEEDOR}"
gh variable set GCP_SA_DEPLOY --body "${SA_DEPLOY}"

Tu CLAVE DE CAJA (para entrar a /ayuda; guárdala, no se vuelve a mostrar):
   ${CAJA}
(Si el secreto ya existía, la clave es la de antes:
 gcloud secrets versions access latest --secret=kiosk-caja-key)
==================================================================
FIN
