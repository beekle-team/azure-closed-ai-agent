# Terraform

閉域の Azure 一式を立てる。
`terraform.tfvars.example` をコピーし、パスワードを入れた `terraform.tfvars` はコミットしない。

Container Apps のイメージはプレースホルダである。
ACR に Laravel と FastAPI を上げたあと、`azurerm_container_app` の `image` を差し替える。

検索面は Blob、Azure AI Search、Service Bus Premium を Private Endpoint で閉じる。
Service Bus の Private Endpoint は Premium が要る。

`enable_nat_gateway` は初回のイメージ取得用。
閉域を締めるときは false にして、公開出口を消す。
