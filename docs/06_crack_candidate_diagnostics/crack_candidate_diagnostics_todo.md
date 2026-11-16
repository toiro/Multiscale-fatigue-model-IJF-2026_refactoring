# Crack Candidate Diagnostics Todo

背景は [crack_candidate_diagnostics_plan.md](crack_candidate_diagnostics_plan.md) を参照する。

## Current Focus

`--write-diagnostics` を追加し、06の診断CSVと診断事象・保存先の案内表示を既定では出力しないようにする。
入力準備・計算失敗時の `failure.csv` も指定時のみ保存する。計算側の検査・事象記録・例外と、
通常の計算経過表示・summary/detail・04の status CSV は維持する。
2026-11-16: スイッチ・READMEの実装と、軽量検証・full baseline比較を完了した。
条件検証には既存の調査用configによる制限があり、下記に分けて記録する。

## Active Todo

- [x] 現行のCLI、通常診断・入力準備失敗・計算失敗の保存経路を確認する。
- [x] Planにスイッチ名、既定値、制御対象、計算核との境界、検証方針を追加する。
- [x] `cli.py` に `--write-diagnostics` と help を追加し、既定を `False` にする。
- [x] `_run` へ明示的に渡し、入力準備失敗の診断保存を指定時だけにする。
- [x] `run_simulation` に `write_diagnostics=False` を追加し、計算失敗時の保存を制御する。
- [x] `write_load_case_outputs` で通常診断の保存と診断用案内表示を制御する。
- [x] 無指定時は診断ディレクトリを作らず、例外の再送出と通常tracebackを維持する。
- [x] `write_outputs=False` が診断を含む全ファイル出力を抑止することを維持する。
- [x] 診断を利用する既存検証・補助スクリプトの呼び出し箇所を点検し、必要箇所で明示的に有効化する。
- [x] ルートの `README.md` に、既定では診断を出力しないこと、`--write-diagnostics` の実行例、保存対象・保存先、既存診断ファイルの扱いを記載し、常時出力と読める説明を修正する。
- [x] READMEの記載が実装・`--help` と一致することを確認する。
- [x] `.ps1` 経由の軽量検証に、CLI・正常終了・入力準備失敗・計算失敗の有効／無効を追加する。
- [x] 既存診断ファイルの保持と、`--delete-existing-output` の既存動作を確認する。
- [x] 有効時の診断CSVの内容・行対応・生成条件と、既存の診断検証を確認する。
- [x] 同一seedで有効／無効の計算履歴・乱数状態・summary/detail・status・例外・policyが一致することを確認する。
- [x] compileall・静的解析・条件検証・smokeを実施する（baselineを行う作業単位ではsmoke省略可）。
- [x] 既存baselineでのcandidate比較と、引き渡し前のfull baseline比較を実施する。
- [x] 検証結果・既知の検証制限と、実際のCLI使用例をPlan / Todoに記録する。

## 診断出力スイッチの検証記録

- 2026-11-16: `Invoke-CrackCandidateDiagnosticsVerification.ps1` の19件が成功。
  既存14件を明示的な有効指定へ変更し、既定の非出力、CLI引数・help、入力準備失敗、
  計算失敗、全出力無効の優先、過去の診断ファイルの保持と明示的削除を追加確認した。
- 有効／無効の軽量比較でsummary/detail/statusのバイト一致、計算結果・診断事実の保持、
  Python / NumPyの乱数状態の一致を確認した。定義域外例外を含む失敗でも元の例外を再送出する。
  既存の定義域policy・途中履歴・事象の分類・行対応の検証も成功した。
- compileall（`src verification`）と `Invoke-StaticAnalysis.ps1` は成功。
- `Invoke-ParameterConditionVerification.ps1` は条件表10条件の確認後、既存の調査用config
  `B_Smooth_T16_report.json` と `N50R_CS_T50_ctsdnan.json` の一覧判定で停止した。
  context境界10条件は `.venv` で `verification.check_context_boundaries` を別途実行して成功した。
  対象configと条件検証ツールは変更していない。
- full baseline比較を実行する作業単位のため、smoke / legacy miniは省略する。
  変更前のbaseline CSVは `outputs/diagnostics_switch_before/` に保存し、再計算後のcandidateとの比較にも使う。
- `Invoke-BaselineComparison.ps1` は成功。旧実装約8分15秒、整理版約8分43秒で完了し、
  seed42の検証条件でsummary/detailの2 CSVが許容誤差0で一致した。
  保存済みbaselineとのcandidate比較も再計算せず実施して成功し、3組のCSVはバイト単位でも一致した。
  整理版は無指定で実行し、診断CSVと診断案内が生成されていないことを確認した。
  実行ログは `outputs/diagnostics_switch_baseline.log`、軽量検証ログは `outputs/diagnostics_switch_verification.log`。
- 使用例はREADMEの実行説明に追加した。通常の `run` コマンドに `--write-diagnostics` を付けると、
  `diagnostics/*.rows.csv`、事象がある場合の `*.events.csv`、失敗時の `failure.csv` と診断案内を出力する。
  既定では出力せず、計算検査・例外・通常の結果CSVと計算経過表示は維持する。

## 前回作業の完了状況

想定外の状態を見過ごさず、結果 CSV の対象行から診断理由を確認できるようにする。
想定内のゼロ値は簡潔な状態表示にとどめる。件数集計や通常終了理由の網羅的分類を優先しない。
初回の診断出力の実装と、軽量診断検証・旧実装との結果一致確認は完了した。
計算側に残す発生事実と、出力側で付ける診断分類・説明の分離と、その検証を完了した。
通常条件 config の一覧検証は既存の report config を拒否するため、検証結果を下記に分けて記録する。

## 計算事実と診断表示の分離の完了記録

- [x] 計算事実と診断表示を分ける方針を Plan / Todo に追加する。
- [x] 計算側の事象記録・履歴の由来・例外から、表示分類と開発上の保留方針を切り分ける。
- [x] `no_candidate_adopted_details_deferred` を計算事実の `no_candidate_adopted` に変更する。
- [x] `CalculationDiagnostic` と例外の `diagnostic()` が表示分類を決定する構造を整理する。
- [x] 診断の分類と説明文を出力側の小さな対応表へ移す。
- [x] 粒層不足・負の積分値の発生事実を維持し、未確認という説明を出力側へ移す。
- [x] `history_state` の計算上の由来と、情報不足時の表示分類を分離する。
- [x] 計算位置・値・既存の技術的エラーメッセージを保持し、表示用の書式・補足文との境界を点検する。
- [x] 有限値・定義域の検査、例外、途中履歴、既存 policy の停止・継続が変わらないことを確認する。
- [x] 計算事実の保持と出力分類・行対応を別々に軽量検証し、既存の診断検証を更新する。
- [x] 計算側に CSV名・行番号・イベントID・表示分類・保留方針が含まれないことを確認する。
- [x] 診断 CSV の列・意味・参照方法を維持し、事象名変更以外の意図しない差がないことを確認する。
- [x] Plan の通常検証・candidate 比較・引き渡し前 full baseline 比較を実施し、この整理の検証結果を追記する。

## 初回実装の完了記録

- [x] Plan / Todo を作成する。
- [x] 結果行と理由の対応を最優先にする。
- [x] 診断の重点を想定外の検出に変更し、想定内の詳細分類を保留する。
- [x] CTSD停止・寿命積分打ち切りの分岐を確認し、通常判定・想定外・分類未確認を整理する。
- [x] 負の積分値・粒層不足は分類未確認、破壊表現の意図的な inf は検査対象外とし、検査対象を確定する。
- [x] 既存の診断例外と検査を確認し、不足する診断だけを特定する。
- [x] 結果 CSV のファイル名・データ行番号から理由を確認する対応表を設計する。
- [x] 初期履歴・採用履歴を区別し、想定内のゼロ行の簡潔な表示を決める。
- [x] 想定外の種類・説明・位置・値と、結果行から参照する方法を決める。
- [x] 非選択候補の異常と最終結果の関係を表し、直接原因と未確定の影響を区別する。
- [x] 全体停止で結果行がない場合にも診断を保存する方法を決める。
- [x] 専用例外の捕捉・診断保存・再送出を実装し、既存 policy の停止・継続を維持する。
- [x] 途中履歴の消失や誤採用を防ぎ、計算核とファイル出力を分離する。
- [x] 想定外の診断記録と結果行の対応表を保存する。
- [x] 既存 print を維持し、想定外の状態と診断保存先を標準出力へ追加する。
- [x] 想定内・人工的な想定外・分類未確認の軽量検証を `.ps1` から実行可能にする。
- [x] 結果行から理由・根拠を確認でき、件数だけに依存しないことを検証する。
- [x] 非選択候補の異常、全体停止時の保存、既存 policy の挙動を検証する。
- [x] 既存履歴・乱数状態・summary/detail CSV の不変性を確認する。
- [x] compileall・静的解析・条件検証・smoke を実施する（条件検証の失敗は下記に記録）。
- [x] candidate 比較と引き渡し前の full baseline 比較を実施する。
- [x] 検証結果と、診断で確認できる範囲・未確認の状態を記録する。

## Deferred

- 理由4の想定内の終了原因の網羅的分類。
- 全候補の判定値・件数の網羅的保存。
- 初期値・寿命選択条件・計算アルゴリズムの修正。
- 当時の 135 MPa の4回分の完全再現と原因確定。
- 負の積分値・粒層不足のモデル上の意味の最終確定。今回の出力は分類未確認とし、正常扱いにしない。

## 分離作業の検証記録

- 2026-11-15: 診断の軽量検証14件が成功。事実記録を保ったまま出力の分類・説明だけを変更できること、
  技術的例外メッセージの保持、履歴情報未提供時の表示、非採用事実と表示文の分離を追加確認した。
- compileall・静的解析・smoke は成功。計算側には `classification` / `unclassified` / `deferred`、
  CSV名・行番号・イベントID、保留方針の文言が含まれないことを確認した。
- 条件検証は、初回と同じ既存 `B_Smooth_T16_report.json` の一覧判定で停止。
  条件表10条件と、別途実行した context 境界10条件の確認は成功。対象 config と検証ツールは変更していない。
- `Invoke-BaselineComparison.ps1` は成功（旧実装約8分、整理版約7分53秒）。
  seed42の検証条件で summary/detail の2 CSV は許容誤差0で一致し、バイト単位でも一致した。
- `Invoke-CrackCandidateDiagnosticsVerification.ps1 -BaselineDir outputs/diagnostics_boundary_before -CandidateDir outputs/refactored_seed42`
  は14件の軽量検証と、変更前の確認済み CSV を再利用した候補比較の両方で成功した。
- 変更前に保存した実出力の行対応表（662行）も、変更後と列・値・バイト単位で一致した。
  事象名変更と、履歴未提供時に採用履歴と誤説明しない表示は人工的な軽量入力で確認した。
- 計算側の記録は `reason`・`context`・任意の技術的 `message` のみとし、表示分類と未確認の説明は出力側へ移した。
  検査・例外・既存 policy・途中履歴・従来 CSV の動作変更は行っていない。

## 初回実装の検証履歴

以下は初回実装の検証履歴であり、追加する分離作業の検証結果ではない。

- 2026-11-15: `Invoke-CrackCandidateDiagnosticsVerification.ps1` の10件が成功。
  想定内の初期値、NaNによる比較不成立、非選択候補の問題、定義域外 policy、
  CTSD停止と粒層不足、負の寿命積分、非有限積分値と意図的な inf の区別、
  致命例外の保存・再送出、乱数不変性を確認。
- compileall、`Invoke-StaticAnalysis.ps1`、`Invoke-SmokeVerification.ps1` は成功。
- `Invoke-ParameterConditionVerification.ps1` は条件表10条件の確認後、既存の
  `resources/configs/B_Smooth_T16_report.json` が通常条件名以外の config として拒否され停止。
  この config と検証ツールは変更していない。context 境界10条件は別途成功。
- candidate 比較は許容誤差0で既存 baseline CSV と完全一致（約7分59秒）。
  以後に追加した観測用検査・対応表列を含む最終版は full baseline 比較で確認する。
- `Invoke-BaselineComparison.ps1` は旧実装・整理版を再実行して成功。
  original 約7分48秒、candidate 約8分3秒。従来の summary/detail の2 CSV は許容誤差0で一致し、
  ファイル内容もバイト単位で一致した。
- 実際に生成した detail CSV の662データ行（末尾の空欄行を含む）について、
  対応表の行数・1始まりの行番号・き裂深さ0かつCTSD 0の判定が元 CSV と一致することを確認。
- 最終の行対応の補正は、初期履歴を採用候補として参照しないための出力側の条件追加のみ。
  軽量診断検証10件と静的解析で確認し、数値計算には変更していない。

## Verification Rules

文書のみでは実行検証を省略する。実装時は Plan の検証方針に従い、Python は `.venv` を使用する。
