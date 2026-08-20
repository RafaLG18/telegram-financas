{{- define "caderneta.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "caderneta.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "caderneta.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "caderneta.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "caderneta.selectorLabels" -}}
app.kubernetes.io/name: {{ include "caderneta.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "caderneta.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "caderneta.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Name of the token Secret: the existing one when given, otherwise the one the
chart creates.
*/}}
{{- define "caderneta.secretName" -}}
{{- if .Values.telegram.existingSecret -}}
{{- .Values.telegram.existingSecret -}}
{{- else -}}
{{- printf "%s-token" (include "caderneta.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "caderneta.secretKey" -}}
{{- if .Values.telegram.existingSecret -}}
{{- .Values.telegram.existingSecretKey -}}
{{- else -}}
BOT_TOKEN
{{- end -}}
{{- end -}}

{{- define "caderneta.pvcName" -}}
{{- if .Values.persistence.existingClaim -}}
{{- .Values.persistence.existingClaim -}}
{{- else -}}
{{- printf "%s-data" (include "caderneta.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/*
Guards that fail during `helm template`, before anything reaches the cluster.
*/}}
{{- define "caderneta.validate" -}}
{{- if gt (int .Values.replicaCount) 1 -}}
{{- fail "replicaCount must be 1: a polling bot with two replicas causes a 409 Conflict on getUpdates, and SQLite does not support two writers." -}}
{{- end -}}
{{- if and (not .Values.telegram.existingSecret) (not .Values.telegram.botToken) -}}
{{- fail "Set telegram.existingSecret (recommended) or telegram.botToken." -}}
{{- end -}}
{{- if and .Values.persistence.enabled (not (eq .Values.persistence.accessMode "ReadWriteOnce")) -}}
{{- fail "persistence.accessMode must be ReadWriteOnce: SQLite is a file with a single writer." -}}
{{- end -}}
{{- end -}}
