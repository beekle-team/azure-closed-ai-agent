# Terraform

閉域の Azure 一式を立てる。
`terraform.tfvars.example` をコピーし、パスワードを入れた `terraform.tfvars` はコミットしない。

Container Apps のイメージは空なら ACR の `closed-agent:latest` / `closed-admin:latest`。
`scripts/push-acr.sh` でエージェントを上げる。公開レジストリは使わない。
AUTH_MODE は entra。Search のキーは Container Apps の secret。
診断設定は OpenAI / Key Vault / エージェントを Log Analytics に流す。

検索面は Blob、Azure AI Search、Service Bus Premium を Private Endpoint で閉じる。
Service Bus の Private Endpoint は Premium が要る。

`enable_nat_gateway` は初回のイメージ取得用。
閉域を締めるときは false にして、公開出口を消す。
