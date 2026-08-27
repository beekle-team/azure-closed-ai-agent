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
  default     = "nginx:alpine"
  description = "本番は Private ACR の管理画面イメージ。公開レジストリのまま出さない"
}

variable "agent_image" {
  type        = string
  default     = "python:3.12-slim"
  description = "本番は Private ACR のエージェントイメージ。公開レジストリのまま出さない"
}
