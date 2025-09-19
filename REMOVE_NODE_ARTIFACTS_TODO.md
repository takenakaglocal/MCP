# Node 関連除去 TODO

以下のファイル/設定は Python 版へ統一後は不要。削除は手動で行ってください（履歴管理上の確認を推奨）。

推奨削除対象:
- package.json
- package-lock.json
- node_modules/ ディレクトリ
- mcp-elasticsearch.js

削除コマンド例 (最終確認後):
```
rm -f package.json package-lock.json mcp-elasticsearch.js
rm -rf node_modules
```

注意:
- 他の Node ベースツールが無いことを再確認
- Git でブランチを切ってから削除すると復元容易

残すもの:
- mcp_elasticsearch.py
- requirements.txt
- .vscode/mcp.json (python 指定済み)

追加検討:
- .gitignore に venv/ 追加 (python 仮想環境除外)

