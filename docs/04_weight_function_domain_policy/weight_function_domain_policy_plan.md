# Weight Function Domain Policy Plan

## 目的

weight function の定義域外に到達した場合の扱いを、計算全体の
異常停止だけでなく、レポート用に「定義域内で得られた値を残す」
選択肢として明示する。

対象とする要求:

- weight function が用意されている範囲で、鋼 A/B/C と試験片形状4種類の
  SN 曲線を整理する。
- 範囲外への外挿や補正は行わない。
- 範囲内で完走した応力点の寿命は従来計算と同じ値として扱う。
- 範囲外に達した応力点は、寿命点を無理に埋めず、欠測または
  domain limit として記録する。

ここでの目的は SN 曲線の形状を変えることではない。定義域内で計算可能な
点を落とさず残し、定義域外に出た点を研究者が判別できるようにすることである。

## 基本方針

- weight function 範囲内の計算式、乱数呼び出し順序、分岐条件、CSV 形式を
  不用意に変えない。
- weight function 範囲外で外挿しない。
- 範囲外以降を 0、有限値、推定値で補正しない。
- 既存 baseline 比較や通常の再現性確認では、現状どおり停止する挙動を既定にする。
- レポート用にだけ、範囲外到達を候補き裂の打ち切りとして扱う選択肢を追加する。
- 「計算できた寿命」と「weight function 範囲外で未定の寿命」を混ぜない。
- 追加する設定は実行全体の曖昧な mode ではなく、weight function 定義域外の
  扱いとして名前付けする。

## 設定方針

設定名は `weight_function_domain_policy` とする。

初期値は `error` とし、既存挙動を保つ。

### `error`

現状どおり、weight function 範囲外または補間不能な値を検出した時点で
診断例外として停止する。

用途:

- baseline 比較
- 旧実装一致確認
- 通常の開発検証
- 想定外の数値異常を早期に見つけたい実行

### `truncate_candidate`

weight function 範囲外に到達した候補き裂の crack-depth evaluation loop を
そこで打ち切る。

打ち切り前までの履歴は保持し、後続の grain candidate、area element、
symmetry、load case は続ける。

範囲外以降は外挿せず、寿命点は未定として扱う。

用途:

- weight function が用意されている範囲内の SN データ整理
- Long CG/CS の亀裂長さ-亀裂速度関係で、有効範囲内の履歴を残す実行
- 条件全体を落とさず、範囲外到達の位置と理由を集計する実行

## 非目標

- weight function 範囲外の外挿。
- 範囲外以降の寿命推定。
- NaN や inf を使って通常寿命点を埋めること。
- 未完走 candidate を通常の `minimum life` と同じ意味で採用すること。
- `B_CS_T50` / `G_CS_T50` など未対応 resources 条件の追加。
- SN 曲線作図ロジックやレポート生成スクリプトの完成。

## 実装方針

1. `SimulationConfig` に `weight_function_domain_policy` を追加する。
   - 許容値はまず `error`, `truncate_candidate` に限定する。
   - 未指定時は `error` とする。
   - JSON config の許可キーにも追加する。

2. 計算核へ policy を渡す。
   - `CalculationInputData` に直接 field を追加するか、
     小さな `CalculationControl` dataclass を追加する。
   - 汎用 API 化ではなく、今回の計算制御を明示する最小構造に留める。

3. weight function 範囲外の例外を識別可能にする。
   - 既存の `CrackLifeDiagnosticError` を使う場合は、
     weight function domain 由来か判定できる情報を持たせる。
   - 必要なら `WeightFunctionDomainError` のような派生例外を追加する。
   - Stage I / Stage II / remote stress 由来の context は保持する。

4. `truncate_candidate` では crack-depth loop で domain error を捕捉する。
   - 捕捉位置は `_crack_life_raw()` の evaluation point loop を第一候補にする。
   - そこで候補き裂の残り評価点を打ち切り、後続 candidate へ戻す。
   - 既に記録済みの履歴は保持する。

5. 結果に停止状態を持たせる。
   - 候補: `stop_reason`, `valid_until_index`, `is_complete`
   - `CrackLifeResult` に追加するか、外側の `ElementLifeResult` に集約するかは
     実装時に影響範囲を見て決める。
   - 既存 CSV 互換を壊さないよう、既存列の意味は変えない。

6. 出力方針を分ける。
   - 既存 summary/detail CSV はできるだけ維持する。
   - domain policy の状態は、追加列または別 status CSV として出す。
   - 寿命点として採用できない場合は、`minimum life` と区別できる記録を残す。

## 決定事項

以下は実装時の前提とする。

- 未評価点は detail CSV では `NaN` として表現する。
- `stop_reason`, `valid_until_index`, `is_complete` は status CSV または
  同等の追加出力で確認できるようにする。
- 同一応力点で complete candidate が1つ以上ある場合、その complete candidate の
  寿命を SN 点として採用してよい。
- 同一応力点で complete candidate が無い場合、その応力点の寿命は欠測とする。
- 一部 candidate が domain limit に到達した事実は、complete candidate がある場合でも
  status 出力に残す。
- `weight_function_domain_policy` の対象には、Stage I weight function、
  Stage II weight function、remote stress function の補間不能を含める。
- 既存 CSV 互換を優先し、domain limit による欠測や停止状態は summary CSV の
  既存列へ混ぜず、status CSV 側に記録する。

## SN 曲線への扱い

`truncate_candidate` は、SN 曲線の形状を補正するための mode ではない。

- 完走した応力点は、従来計算と同じ寿命点として扱う。
- weight function 範囲外で打ち切った応力点は、寿命未定として扱う。
- 作図時に欠測点を線でつなぐ場合、その線は計算結果ではなく作図上の補助である。
- レポートでは、各条件・応力点ごとに `complete`, `weight_function_domain_limit`,
  `no_initiation` などの状態表を添える。

このため、目的は「全応力点を埋めた完全な SN 曲線」ではなく、
「weight function が用意されている範囲で得られる SN データを落とさず整理する」
こととして定義する。

## 検証方針

ドキュメントのみの変更では実行検証を省略してよい。

コードに触れた場合は通常:

- `.venv\Scripts\python.exe -m compileall src verification`
- `scripts\verification\Invoke-StaticAnalysis.ps1`
- `scripts\verification\Invoke-ConditionPreflight.ps1`
- `scripts\verification\Invoke-SmokeVerification.ps1`

`error` policy の既存挙動に影響しうる場合:

- `scripts\verification\Invoke-CandidateComparison.ps1`

`truncate_candidate` 実装時:

- weight function domain error を人工的に起こす小さな検証を追加する。
- `error` では従来どおり停止することを確認する。
- `truncate_candidate` では部分履歴と停止理由を返し、後続ループが続くことを確認する。
- 完走条件の CSV が `error` policy と一致することを確認する。

## 成功条件

- 未指定時は従来どおり weight function 範囲外で停止する。
- `weight_function_domain_policy=truncate_candidate` では、範囲外 candidate の
  部分履歴と停止理由が残る。
- 範囲外 candidate によって、後続 candidate / element / load case の実行が
  全体停止しない。
- 完走した応力点の寿命値は従来計算と変わらない。
- 範囲外で未定の寿命が、通常の `minimum life` と混同されない。
