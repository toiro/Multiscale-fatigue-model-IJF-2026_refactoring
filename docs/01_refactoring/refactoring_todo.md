# Refactoring Todo

完了済みの作業履歴と検証ログは [refactoring_log.md](refactoring_log.md) に置く。このファイルは、次に実装・確認する作業だけを短く管理する。

## Current Focus

Phase Last: 研究者向け単純化。

新しい抽象化を増やす段階ではなく、既存構造が論文実装として読みやすいかを確認する。実装変更は小さく、計算式、乱数順序、分岐条件、CSV 形式を変えない。

複数の `steel` / `specimen_type` / `thickness_sign` 条件を取り込む作業は、
リファクタリングではなく条件拡張として扱い、今後は
[`../incorporate_several_param_todo.md`](../incorporate_several_param_todo.md)
を主な作業管理ファイルにする。

## Active Todo

現時点で、結果同一性を保ったまま直ちに進めるべき実装タスクは棚卸済み。

次に作業へ入る場合は、下の `Deferred` または `Needs Confirmation` から目的を選び、検証方針を決めてから `Active Todo` に移す。

## Recently Completed

- [x] `field_values.py` の応力場参照へ意味名 wrapper を追加し、`calculation/` 側を新名へ移行した。
- [x] JSON config の期待項目を `config.py` 側で読めるようにした。
- [x] README に実行階層と `resources/` のファイル構成、サンプル実行方法を追記した。
- [x] `GrainBoundaryData` の型注釈、docstring、CTSD 側の局所名を整理した。
- [x] Stage I / Stage II と停止条件の局所名を整理した。
- [x] 重めの seed 固定条件を `Multiscale_fatigue_model.py` と `src` の両方で再現して比較する専用 config / script を追加した。
- [x] README と `src` の未指定時既定パラメータを `Multiscale_fatigue_model.org.py` 準拠に戻し、軽量設定は検証用 config として分離した。
- [x] 通常実行用 config は random seed 未指定とし、seed 固定 config は比較検証用として分離した。
- [x] `resources/sample_simulation.json` を `.org.py` 準拠の通常設定に合わせた。
- [x] `crack_life.py` の CTSD 評価内に残っていた旧名 `rnList[0]` を `boundary_depths[0]` へ修正した。

## Deferred

結果同一性、乱数順序、または検証負荷に影響しうるため、通常の読解性改善とは分けて扱う。

- `crack_life.py` 内部の `Any` 削減。NumPy/SciPy の scalar・配列返り値が混在するため、数値型正規化の検証計画が先に必要。
- 数値型の正規化。`float(...)`, `.item()`, `np.asarray(...)`, `list(...)` などは結果へ影響しうる。
- 補間器返り値と配列 shape の統一。`griddata`, `interp1d`, `LinearNDInterpolator`, `RBFInterpolator` 由来の返り値差に注意する。
- `_interpolate_stage1_weight_function()` / `_interpolate_stage2_weight_function()` の cache 化。浮動小数 key と補間器返り値の扱いで結果差が出る可能性があるため、計算結果変更を許容する高速化課題として扱う。
- `S_*` 履歴配列の dataclass 化。更新順序を隠す抽象化になりやすいため、現時点では行わない。
- surface grain sampling、orientation、grain boundary sampling、crack-initiation location の乱数呼び出し集約。
- `_crack_life_raw()` 冒頭の discarded initial crack aspect sampling の削除。乱数順序と結果が変わるため通常の冗長削除として扱わない。
- `gData.pkl` 生成、`FieldValues.pkl` 生成、Abaqus cache 読み込み順序の変更。
- `MaterialDataImporter` に残る legacy 作業属性名の一括削除。必要なら小分けに扱う。
- `print` の logger / callback 化。論文実装の実行順確認に使えるため、必要性が明確になるまで保留する。
- `ruff` は `E9`, `F`, `I` へ拡大済み。今後、必要なら対象 rule を増やすが、既存コードのスタイル一括修正は目的にしない。

## Needs Confirmation

コードだけでは論文上の意図、旧実装由来の制約、または潜在バグのどれかを判断できない。挙動変更を伴う修正は、研究上の判断を確認してから行う。

- `element_life.py` の候補粒ループで、すべり面判定に `FoList[0]` を使い、き裂寿命評価には `FoList[Grain_i]` を渡している意図。
- `_record_unstable_fracture_history()` で unstable fracture 後にどの履歴配列をどの値で埋めるべきか。
- `_evaluate_ctsd_at_crack_depth()` の `crack_tip_in_first_grain` / `else` 分岐に残る初期 slip response 構築の物理的意味。
- `_calculate_stress_state_at_crack_depth()` の Stage I / Stage II 分岐で、`σ_remote` から `Δσ` を作る処理が重複している点を共通化してよいか。
- `calculate_crack_life()` と `_crack_life_raw()` の二重構造を最終的に残すか。
- detail CSV ファイル名では旧実装由来の 0-based iteration index を使い、summary CSV の `Iteration` 列では `+1` した 1-based 番号を使っている点を維持すべきか。

## Verification Rules

- 1タスク完了ごとは、通常 `py -m compileall src verification`, `scripts/verification/Invoke-StaticAnalysis.ps1`, `scripts/verification/Invoke-SmokeVerification.ps1` を実行する。
- calculation/output 境界、乱数順序、CSV 内容に触れた場合は `scripts/verification/Invoke-CandidateComparison.ps1` で既存 baseline CSV と比較する。
- baseline を回すと決めた作業単位では、smoke / legacy mini は省略してよい。
- 乱数順序、CSV 形式、引き渡し前確認では `scripts/verification/Invoke-BaselineComparison.ps1` または `scripts/verification/Invoke-HeavyComparison.ps1` で旧実装も再実行する。
- baseline / candidate 比較はいずれも同一 seed・同一条件の CSV 完全一致を基準にする。
