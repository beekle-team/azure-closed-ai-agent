# Terraform

閉域の Azure 一式を立てる。
`terraform.tfvars.example` をコピーし、パスワードを入れた `terraform.tfvars` はコミットしない。

Container Apps のイメージは `admin_image` / `agent_image` で渡す。
本番は Private ACR のイメージ。公開レジストリのまま出さない。
診断設定は OpenAI / Key Vault / エージェントを Log Analytics に流す。

検索面は Blob、Azure AI Search、Service Bus Premium を Private Endpoint で閉じる。
Service Bus の Private Endpoint は Premium が要る。

`enable_nat_gateway` は初回のイメージ取得用。
閉域を締めるときは false にして、公開出口を消す。
