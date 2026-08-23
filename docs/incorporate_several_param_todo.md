# Incorporate Several Parameter Conditions Todo

完了済みの作業履歴と検証ログは
[incorporate_several_param_log.md](incorporate_several_param_log.md) に置く。
このファイルは、複数条件対応の次作業だけを短く管理する。

## Current Focus

条件表、resources 配置、context 境界、10条件の pkl 生成 / CSV validation、
Weight Function RBF 境界整理、追加条件の参照 CSV 比較方針は整った。
通常計算の実行導線も `resources/configs/` に整理済み。
次は `parameter_condition_reading_difficulties.md` の現状版を受け、
残っている raw 条件分岐のうち安全に名前付き decision へ寄せられるものを
小さく整理する。

## Active Todo

### Normal Resource Run Entry

- [x] 外部レビューの各指摘を、コード構造で潰すもの、最小ドキュメントで説明するもの、Deferred に置くものへ分類し、plan に昇格する。
- [x] `SUPPORTED_PARAMETER_CONDITIONS` と各種表をまたぐ読みにくさに対し、今回対象10条件の resolved condition view 方針を plan に昇格する。
- [x] `parameters.py` に `SimulationCondition`, `ResolvedParameterCondition`, `WeightFunctionTableFamily`, `NominalStressExtractionMode`, `resolve_parameter_condition()` を追加する。
- [x] `PaperModelParameters` を resolved condition view 経由で組み立て、`specimen_type` / `thickness_sign` readable alias を追加する。
- [x] `build_parameter_snapshot()` と context 境界で `params.type` / `params.T` より readable alias / resolved condition view を優先して読む。
- [x] `AbaqusImportInput` に `nominal_stress_extraction_mode` を追加し、`context.py` から渡す。
- [x] `abaqus.py` の nominal stress 抽出を extraction mode 判定へ変更し、抽出方式ごとの小関数へ分ける。
- [x] 構造変更後に残る物理的略号と導線だけ、`README.md` / `resources/README.md` に最小限追記する。
- [x] `resources/README.md` の "Planned additional directories" を現状に合わせて supported directories 表現へ更新する。
- [x] `parameter_condition_reading_difficulties.md` の改善済み欄を現状に合わせ、`uses_split_stage2_weight_function` ではなく `stage2_weight_function` callable へ更新する。
- [x] 入力 manifest が期待しない重複ファイル、特に `N50R_Ferrite grain angle copy.csv` は未使用ファイルとして削除する。
- [x] 通常計算用 config の置き場を `resources/configs/` と決める。
- [x] 10条件分の通常計算 config を追加する。
- [x] `verification.check_resources` で通常計算 config の存在と軽量設定混入を検査する。
- [x] README / resources README で、通常計算 config、軽量検証 config、`sample_simulation.json` の役割を分けて説明する。
- [x] 通常計算導線の整理後に `parameter_condition_reading_difficulties.md` の該当項目を更新する。
- [x] 役割を終えた `scripts\Invoke-SampleResourcesRun.ps1` を削除し、README の sample 実行導線を消す。

### Readability Cleanup: Weight Function Family

- [x] `MaterialImportInput` に `weight_function_table_family` を追加し、`context.py` から `params.weight_function_table_family` を渡す。
- [x] `material.py` の weight function constants / remote stress constants 選択を raw `specimen_type` 分岐から `WeightFunctionTableFamily` 判定へ変更する。
- [x] `abaqus.py` の `type == R008 or R100` 表示を extraction mode ベースの表示へ置き換えるか削除する。
- [x] `parameter_condition_reading_difficulties.md` の該当項目を、weight function family 化後の現状に更新する。

### Completed In This Phase

- [x] 追加条件の cache 生成を最初に試す代表条件を `N50R_R008_T24` に決める。
- [x] `N50R_R008_T24` で `scripts\Invoke-ConditionResourcesRun.ps1` を実行し、cache 生成前の停止点を確認する。
- [x] `N50R_R008_T24` の所要時間と生成 cache サイズを log に記録し、残り条件を順次回す前の課題を整理する。
- [x] `calculation/` 以下に `steel` / raw `specimen_type` / `thickness_sign` が不要に残っていないか確認し、残っていれば計算意味を持つ field へ置き換える。
- [x] `R008` / `R100` / `Smooth` の `sigma_nom_list` を決める換算方法が `docs/L135_U175_S20_R-1.py.ref` に含まれていることを確認する。
- [x] `AbaqusDatabaseCreator.read_dat()` に、`L135_U175_S20_R-1.py.ref` の `Smooth` / `R008` / `R100` 用 nominal stress 抽出を明示実装する。
- [x] `N50R_Smooth_T16` で `outputs/condition_cache/N50R_Smooth_T16/` に FieldValues / `gData.pkl` が生成されることを確認する。
- [x] `N50R_R008_T24` で `outputs/condition_cache/N50R_R008_T24/` に FieldValues / `gData.pkl` が生成されることを確認する。
- [x] `N50R_R100_T24` で `outputs/condition_cache/N50R_R100_T24/` に FieldValues / `gData.pkl` が生成されることを確認する。
- [x] 上記3タイプの所要時間と生成 cache サイズを log に記録し、B/G 条件を順次回す前の課題を整理する。
- [x] `Smooth` / `R008` / `R100` の weight function RBF 初期化を `L135_U175_S20_R-1.py.ref` と照合して実装する。
- [x] `N50R_Smooth_T16`, `N50R_R008_T24`, `N50R_R100_T24` で出力 CSV が `verification.validate_output_csv` を通ることを確認する。
- [x] `weight_function_rbf`, `weight_function_rbf_low`, `weight_function_rbf_high`, `uses_split_stage2_weight_function` の参照箇所を棚卸する。
- [x] `WeightFunctionResources` / `WeightFunctionData` に Stage II weight function 評価 callable を追加する。
- [x] `material.py` で single / split RBF を包む callable を作り、RBF 構造の選択を入力準備側で終わらせる。
- [x] `crack_life.py` の `_interpolate_stage2_weight_function()` から single / split RBF 分岐を消す。
- [x] `SpecimenGeometry.uses_split_stage2_weight_function` を削除し、`context.py` と smoke fixture を更新する。
- [x] RBF 構造整理後に `N50R_CS_T50` の candidate 比較を行う。
- [x] RBF 構造整理後に `N50R_Smooth_T16`, `N50R_R008_T24`, `N50R_R100_T24` の CSV validation を確認する。
- [x] B/G の `Smooth` / `R008` / `R100` 条件で pkl 生成と CSV validation を順次確認する。
- [x] 追加条件の比較基準を決める。旧実装再実行で比較するか、参照 CSV を新しく固定するかを選ぶ。

## Completed

- [x] `steel` / `specimen_type` / `thickness_sign` の参照箇所を、条件決定、ファイル名決定、計算核分岐に分類する。
- [x] ファイル名決定を `context.py` の入力準備境界へ軽く集約する。
- [x] 計算核内の raw `specimen_type` 分岐を、計算意味に合わせた field へ置き換える。
- [x] 追加条件ごとの軽量 config を用意する。
- [x] 追加条件で、重い Abaqus/material 読み込み前の context 境界解決が通ることを確認する。
- [x] 追加条件で Abaqus field cache と `gData.pkl` の生成先を条件別に分離できているか確認する。
- [x] 追加条件ごとの smoke 相当の境界検証手順を `scripts/verification/Invoke-ConditionPreflight.ps1` として用意する。
- [x] `resources/` 内の各条件ディレクトリに必要ファイルが揃っているか検査する helper を追加する。
- [x] `N50R_CS_T50` で full baseline 比較と candidate 比較を通し、既存条件の結果一致を確認する。

## Deferred

- `T25`, `CSS`, `B/G_T50` など、`Parameters.py.ref` にはあるが今回の対象外の条件追加。
- `SmoothT` は今回対象外のため実装しない。
- `Smooth` の `sigma_nom_list` 抽出にある Bainite/Martensite 専用分岐は、現在の `B/G/N50R` 条件名と一致しないため今回追加しない。
- Smooth 条件の microstructure model size 推定に関わる挙動変更。
- 条件表を外部 JSON/YAML 化すること。現時点では論文実装としてコード内の表を優先する。

## Verification Rules

- 1タスク完了ごとは、通常 `.venv\Scripts\python.exe -m compileall src verification`, `scripts\verification\Invoke-StaticAnalysis.ps1`, `scripts\verification\Invoke-ConditionPreflight.ps1`, `scripts\verification\Invoke-SmokeVerification.ps1` を実行する。
- ドキュメントだけの変更では実行検証を省略してよい。
- 条件表、リソース解決、`resources/` に触れた場合は、重い計算の前に `scripts\verification\Invoke-ConditionPreflight.ps1` で条件表、必須ファイル配置、軽量 config、context 境界解決を確認する。
- cache 生成先に触れた場合は、既存 `N50R_CS_T50` が通ることを確認する。
- CSV 内容、乱数順序、計算分岐に触れた場合は、既存 baseline CSV との candidate 比較を行う。
- FieldValues / `gData.pkl` を再生成した場合は、古い baseline CSV をそのまま使わず、full baseline 比較で baseline CSV も更新してから candidate 比較を行う。
- 追加9条件は旧実装再実行との一致を当面要求しない。軽量 config の初回通過 CSV を `outputs/condition_reference/<condition>_seed42/` に固定し、以後は `scripts\verification\Invoke-ConditionReferenceComparison.ps1` で現在出力と CSV 完全一致を確認する。
- 追加条件の cache は大きいため比較基準にはしない。cache 再生成を意図的に行い、参照 CSV を更新する場合は、その理由と実行 config を log に記録する。
