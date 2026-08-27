# 実行は自前、モデルは Azure に残す

Foundry の Hosted Agent は、プラットフォームがコンテナイメージを引く。
[公式の制限](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/virtual-networks) は、そのレジストリをプライベートエンドポイントの後ろに置けないと書いている。
会話データは閉じられても、イメージ置き場だけパブリックに残る。

このテンプレートは、エージェントのループを Azure Container Apps に置く。
イメージの取得も実行も、自分の VNet の中で完結する。
モデル呼び出しだけ Azure OpenAI（または Foundry のモデル）に残す。

Hosted Agent や、設定だけで動く Prompt Agent を入口の試作に使ってよい。
口伝をスキルにして回し、実行の手前で承認し、トークンを組織ごとに数えるところまで載せるなら、ループは自前になる。

詳しいネットワーク手順は Learn の [Hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) と [private networking](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/virtual-networks) を見る。
この箱の立て方は [architecture.md](architecture.md) と `infra/terraform` を見る。
