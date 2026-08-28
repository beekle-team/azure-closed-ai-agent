variable "name_prefix" {
  type        = string
  default     = "closedai"
  description = "リソース名の接頭辞"
}

variable "location" {
  type        = string
  default     = "japaneast"
}

variable "openai_location" {
  type        = string
  default     = "japaneast"
  description = "Azure OpenAI のリージョン。モデル提供状況で変える"
}

variable "openai_deployment_name" {
  type    = string
  default = "gpt-4o"
}

variable "openai_model_name" {
  type    = string
  default = "gpt-4o"
}

variable "openai_model_version" {
  type    = string
  default = "2024-11-20"
}

variable "enable_nat_gateway" {
  type        = bool
  default     = true
  description = "初回のイメージ取得用。閉域を締めるときは false"
}

variable "postgres_admin_login" {
  type    = string
  default = "pgadmin"
}

variable "postgres_admin_password" {
  type      = string
  sensitive = true
}

variable "neo4j_password" {
  type      = string
  sensitive = true
}

variable "admin_image" {
  type        = string
  default     = ""
  description = "空なら ACR の closed-admin:latest。公開レジストリは使わない"
}

variable "agent_image" {
  type        = string
  default     = ""
  description = "空なら ACR の closed-agent:latest。公開レジストリは使わない"
}

variable "azure_tenant_id" {
  type        = string
  default     = ""
  description = "Entra テナント。AUTH_MODE=entra で必須"
}

variable "azure_client_id" {
  type        = string
  default     = ""
  description = "エージェント API のアプリ ID。JWT の aud"
}

variable "channel_webhook_secret" {
  type        = string
  sensitive   = true
  description = "Teams / メール入口の共有秘密。Bearer では身元を開かない"
}
