# AGENTS.md

1. 前提論文は https://doi.org/10.1016/j.ijmecsci.2019.105339 である。
2. 目的は、論文実装として計算手順を追いやすくしつつ、計算結果を変えずに段階的に整理すること。
3. 既存の `multiscale-fatigue-model/` は原則そのまま残し、整理版は `src/` 以下に作成する。
4. `docs/01_refactoring/refactoring_plan.md` と `docs/01_refactoring/refactoring_todo.md` は整理版実装の履歴として参照する。複数条件取り込みでは `docs/incorporate_several_param_plan.md` と `docs/incorporate_several_param_todo.md` を作業管理記録として参照・更新する。
5. 計算核は入力準備・出力処理から分離し、必要なパラメータだけを明示的に渡す。
6. 「再利用可能」は汎用 API 化ではなく、研究者が計算内容を読解・検証・修正できることを指す。
7. Readability は、論文上の計算単位に対応した名前・構造・依存関係を優先する。
8. 過剰な抽象化、過剰な関数分割、応用利用向けの拡張点追加は避ける。
9. 計算式、乱数呼び出し順序、分岐条件、丸め、CSV 形式を不用意に変えない。
10. `BasicParams` や `DataImport` などのグローバル依存を増やさない。
11. 乱数 seed、出力先フォルダ、軽量検証条件を指定可能にし、比較可能性を保つ。
12. 検証手順は PowerShell の `.ps1` スクリプトとして明示化する。
13. 1タスクの粒度は小さくし、通常は完了ごとに静的解析と軽量検証を実施する。
14. 複数条件取り込みで `parameters.py`, `paths.py`, `context.py`, `resources/` に触れた場合は、重い寿命計算ではなく `scripts/verification/Invoke-ConditionPreflight.ps1` で条件表、入力ファイル配置、軽量 config、context 境界解決を確認する。
15. 複数条件取り込みの通常検証は `.venv\Scripts\python.exe -m compileall src verification`, `scripts/verification/Invoke-StaticAnalysis.ps1`, `scripts/verification/Invoke-ParameterConditionVerification.ps1`, `scripts/verification/Invoke-SmokeVerification.ps1` を基本とする。
16. baseline を回すと決めた作業単位では、smoke / legacy mini は省略してよい。
17. 開発中は既存 baseline CSV を再利用する candidate 比較を優先する。
18. 乱数順序・CSV形式・引き渡し前確認では、旧実装も再実行する full baseline 比較を行う。
19. `print` は研究者が実行順を追う手がかりとして当面維持する。
20. コード付随の説明ドキュメントは最小限に保ち、構造が固まった後に整備する。
21. サブエージェントは明示的に許可された場合に限り使い、主担当が変更をレビューする。
22. 判断に迷う場合は、再現性、論文実装としての読解性、段階的移行の順に優先する。
23. プロジェクト内でのpython実行は .venv のものを使用する
