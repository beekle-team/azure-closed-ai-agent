# 公開ドキュメント

このフォルダは、テンプレートを配るための説明である。
GitHub で誰でも読める前提で書く。

最初に読むのはリポジトリ直下の [README](../README.md)。
構成を見るなら [architecture.md](architecture.md)。
サンプルを動かすなら [sample.md](sample.md)。

| ファイル | 開くとき |
| --- | --- |
| [architecture.md](architecture.md) | 画面、ハーネス、検索、閉域の立て方が知りたい |
| [self-host.md](self-host.md) | なぜ Hosted Agent を既定にしないか知りたい |
| [sample.md](sample.md) | 架空の総合商社サンプルを動かしたい |
| [vs-copilot.md](vs-copilot.md) | Copilot のまま残す仕事と、こちらに移す仕事を分けたい |
| [../infra/terraform/README.md](../infra/terraform/README.md) | Azure に出す |

## ここに置くもの

開き方、構成、サンプル、Microsoft のサービスとの分け。
設計判断は、公式ドキュメントへのリンクと、この箱が取る選択だけを書く。

## ここに置かないもの

特定の会社名、案件名、未公開の調査メモ。
公式文面の逐語対照表、実機 PoC の手順、検証結果の記入欄。
見積、単価、社内の作業メモ。

閉域で Hosted Agent を試す手順は、Microsoft Learn を正本にする。
このリポジトリはその写しを持たない。

手元の調査メモは `docs/_private/` に置ける。Git には入らない。
