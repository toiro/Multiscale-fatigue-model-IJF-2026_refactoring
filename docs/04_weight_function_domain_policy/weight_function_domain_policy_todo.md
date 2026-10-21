# Weight Function Domain Policy Todo

このファイルは、weight function 範囲外の扱いを設定化する作業だけを短く管理する。
背景と設計方針は
[weight_function_domain_policy_plan.md](weight_function_domain_policy_plan.md) を参照する。

## Current Focus

`weight_function_domain_policy` を導入し、既定の `error` では従来挙動を維持しつつ、
レポート用の `truncate_candidate` で weight function 定義域内の部分履歴を
残せるようにする。

## Active Todo

- [x] `weight_function_domain_policy` の値を `error` / `truncate_candidate` に固定する。
- [x] `SimulationConfig` と `SIMULATION_CONFIG_KEYS` に `weight_function_domain_policy` を追加する。
- [x] config 読み込み時に未知の policy 値を早期に拒否する。
- [x] 計算核へ policy を渡す置き場所を決める。
  - `CalculationInputData` に field を追加する。
- [x] weight function domain 由来の停止を識別できる例外または例外属性を決める。
  - `WeightFunctionDomainError` を追加する。
- [x] Stage I weight function 範囲外を policy 判定の対象にする。
- [x] Stage II weight function 範囲外または補間不能を policy 判定の対象にする。
- [x] remote stress function の補間不能を同じ policy に含めるか、別扱いにするか決める。
- [x] remote stress function の補間不能を policy 判定の対象にする。
- [x] `_crack_life_raw()` の evaluation point loop で、`truncate_candidate` 時だけ
      domain error を捕捉する。
- [x] 部分履歴の埋め方を決める。
  - 既に記録済みの点は保持する。
  - 未評価点は detail CSV では NaN として表現する。
- [x] `CrackLifeResult` / `ElementLifeResult` へ停止状態を追加する。
  - `stop_reason`
  - `valid_until_index`
  - `is_complete`
- [x] `_is_better_crack_candidate()` が未完走 candidate を通常寿命として誤採用しないようにする。
- [x] domain limit に到達した応力点を summary CSV に行として残すか、
      status CSV だけに記録するか決める。
- [x] domain limit による欠測や停止状態を status CSV 側に記録する。
- [x] detail CSV または別 status CSV で domain limit 到達を確認できるようにする。
- [x] smoke fixture を policy 追加後の入力型に合わせる。
- [ ] 人工的に weight function 範囲外を起こす軽量検証を追加する。
- [x] `error` policy で既存 candidate 比較が従来どおり通ることを確認する。
- [x] `truncate_candidate` policy で後続 candidate / element / load case が続くことを確認する。
- [ ] 完走条件では `error` と `truncate_candidate` の結果が一致することを確認する。
- [x] README または resources README に、policy はレポート用実行の選択肢であり、
      外挿ではないことを最小限追記する。

## Deferred

- weight function 範囲外の外挿。
- 範囲外以降の寿命推定。
- 欠測 SN 点を補間して完全な曲線として埋めること。
- `B_CS_T50` / `G_CS_T50` など未対応条件の追加。
- レポート用の図作成スクリプト整備。
- condition ごとの weight function 有効範囲を事前スクリーニングして
  実行前に候補を削ること。

## Decided

- 未評価点は detail CSV では NaN として表現する。
- 停止状態は `stop_reason`, `valid_until_index`, `is_complete` として確認できるようにする。
- 複数 candidate のうち一部だけが domain limit に到達した場合でも、
  complete candidate があれば、その寿命を SN 点として採用する。
- complete candidate が無い応力点は寿命欠測とする。
- `remote_stress_function` の補間不能も `weight_function_domain_policy` の対象に含める。
- 既存 CSV 互換を優先し、domain limit による欠測や停止状態は summary CSV の
  既存列へ混ぜず、status CSV 側に記録する。

## Needs Researcher Decision

現時点ではなし。

## Verification Rules

- ドキュメントだけの変更では実行検証を省略してよい。
- コードに触れた場合は通常:
  - `.venv\Scripts\python.exe -m compileall src verification`
  - `scripts\verification\Invoke-StaticAnalysis.ps1`
  - `scripts\verification\Invoke-ConditionPreflight.ps1`
  - `scripts\verification\Invoke-SmokeVerification.ps1`
- `error` policy の既存挙動や CSV 内容に影響しうる場合:
  - `scripts\verification\Invoke-CandidateComparison.ps1`
- `parameters.py`, `paths.py`, `context.py`, `resources/` に触れた場合:
  - `scripts\verification\Invoke-ConditionPreflight.ps1`
- `truncate_candidate` の確認では、通常の重い条件ではなく、人工的な範囲外入力または
  軽量 config を優先する。
