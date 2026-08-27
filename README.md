# Azure閉域AIエージェント

Microsoft 365 と Entra と Azure OpenAI はそのまま使う。
エージェントのループ、業務の関係、承認とログは FastAPI とグラフDBで持つ。
ユーザー、組織、課金、管理画面は Laravel と PostgreSQL に置く。

Beekle が業務システムで繰り返している分け方と同じである。
入口は Traefik、管理画面は [laravel-react-docker-template](https://github.com/beekle-team/laravel-react-docker-template)、推論は FastAPI、関係は Neo4j。
