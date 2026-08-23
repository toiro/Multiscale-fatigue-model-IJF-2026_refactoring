# Refactoring Summary

この文書は、旧スクリプトのコードが `src/` 以下でどのような構造に変わったのかを、依頼者に説明するための要約です。計算モデルそのものの解説ではなく、リファクタリングによってコードの構造がどう変わったのかに焦点を当てています。

## 変更の全体像

変更前は、`multiscale-fatigue-model/Multiscale_fatigue_model.org.py` という1つのスクリプトの中に、入力条件、材料データ読み込み、Abaqus データ処理、微視組織生成、疲労寿命計算、CSV 出力が混在していました。

変更後は、既存の `multiscale-fatigue-model/` を残したまま、整理版を `src/multiscale_fatigue_model_ijf_2026/` 以下に分けています。計算式、乱数呼び出し順序、分岐条件、CSV 形式は変えないことを前提に、コードの置き場と依存関係を整理しました。

| 旧スクリプト内の役割 | 変更後の主な置き場 |
| --- | --- |
| 実行条件・既定パラメータ | `config.py`, `parameters.py` |
| ファイル名・入力パス生成 | `paths.py`, `config.py` |
| 材料 CSV 読み込み | `material.py` |
| Abaqus `.inp` / `.dat` 処理と cache | `abaqus.py`, `material.py` |
| 応力・ひずみ場参照 | `field_values.py` |
| 微視組織・粒データ生成 | `microstructure.py`, `material.py` |
| 計算核へ渡す入力の組み立て | `context.py`, `calculation/inputs.py` |
| 公称応力・iteration・active element ループ | `runner.py`, `calculation/load_case.py` |
| active element 内の候補き裂評価 | `calculation/element_life.py` |
| 1候補き裂の進展寿命計算 | `calculation/crack_life.py` |
| CSV 出力 | `output.py` |
| 検証用コード | `verification/`, `scripts/` |

## 直書きパラメータの外部設定化

旧スクリプトでは、材料名、試験片種別、板厚条件、結晶構造、応力条件、iteration 数、Paris 則パラメータなどが `BasicParameters` の属性としてコード中に直接書かれていました。条件を変えるには、基本的に Python スクリプトそのものを書き換える必要がありました。

変更後は、シミュレーション条件を JSON config から渡す形にしています。通常実行では、たとえば次のように設定ファイルを指定します。

```powershell
python -m multiscale_fatigue_model_ijf_2026.cli run `
  --config-file verification/configs/original_defaults.json `
  --base-dir multiscale-fatigue-model `
  --output-dir outputs/run `
  --delete-existing-output
```

JSON config で指定する主な値は、次の通りです。

- 材料・試験片条件: `steel`, `specimen_type`, `thickness_sign`, `crystal`
- き裂進展パラメータ: `r_ratio`, `c_paris`, `n_paris`, `delta_delta_th`
- 計算ケース: `sigma_nom`, `iteration_count`, `n_symm`
- 検証用の再現性条件: `random_seed`
- 軽量検証用の計算量制限: `max_active_elements`

一方で、コマンドライン引数は、シミュレーションの物理条件ではなく実行管理に関わるものだけに絞っています。

- `--config-file`: シミュレーション条件を書いた JSON。
- `--base-dir`: `.inp`, `.dat`, CSV, weight function などの入力ファイルを読む場所。
- `--output-dir`: CSV 出力先。
- `--cache-dir`: 既存 cache を読む場所。
- `--delete-existing-output`: 実行前に `--output-dir` 内の既存 CSV を削除する指定。

つまり、旧スクリプトでコードに直接書かれていた研究条件は JSON に移し、ディレクトリや出力削除のような実行環境依存の指定だけをコマンドラインに残しています。

既定条件は `verification/configs/original_defaults.json` に置き、`Multiscale_fatigue_model.org.py` と同じ `sigma_nom=[150,160,170,180,190]`, `iteration_count=4`, `n_symm=4` を明示しています。通常実行では random seed を指定しません。リファクタリング前後の比較検証では、再現性のために `verification/configs/heavy_seed42.json` や `verification/configs/lightweight_seed42.json` のような seed 固定 config を使います。

これにより、計算条件を変更するために Python コードを書き換える必要がなくなり、条件ファイルと出力先を分けて管理できるようになりました。

## 入力準備と計算核の分離

旧スクリプトでは、材料データ読み込みや cache 生成と、疲労寿命計算の本体が同じ流れの中にありました。

変更後は、まず `context.py` で入力準備を行い、その後 `calculation/inputs.py` の `CalculationInputData` に計算核へ渡す値をまとめる構造にしています。

重要なのは、`SimulationContext` 全体を計算核へ渡さないことです。`SimulationContext` には I/O、cache、出力、材料データ準備の文脈も含まれるため、解析計算の中心部に渡すには過剰でした。現在の計算核は、必要な物理量、関数、条件だけを `CalculationInputData` 経由で受け取ります。

## 材料データ処理の整理

旧スクリプトでは、材料 CSV、Abaqus field cache、weight function、生成済み微視組織データが、`DataImport` 相当の大きなオブジェクトに混在していました。

変更後は `material.py` を中心に、外から読むべきデータを typed view として分けています。

- `grain_distributions`
- `mechanical_properties`
- `abaqus_field_cache`
- `weight_function_resources`
- `microstructure_data`

`MaterialDataImporter` 内部には旧名由来の作業属性が一部残っていますが、通常の計算経路では上記 view を読む構造に寄せています。また、値が生成される前に大量の `None` スロットを初期化する形はやめ、生成箇所で代入する形へ整理しました。

## 応力場参照の整理

旧スクリプトの `FieldValues_ACTIVE_Numpy()` や `FieldValues_ACTIVE_x0()` は、名前だけでは何を参照しているか分かりにくい関数でした。

変更後は `field_values.py` に、計算核から読むための意味名 wrapper を追加しています。

- `active_element_total_field_by_depth()`
- `active_surface_total_field_by_nominal_stress()`

旧名の関数は互換 wrapper として残しつつ、`calculation/` 側では意味名を呼ぶようにしています。これにより、計算核から見た応力場参照の意図が読みやすくなりました。

## 計算ループの分割

旧スクリプトでは、寿命計算の大きなループが1つのスクリプト内に連続していました。

変更後は、ループの階層に合わせてファイルを分けています。

- `runner.py`: 公称応力ケースのループ。
- `calculation/load_case.py`: iteration、active area element、対称位置のループ。
- `calculation/element_life.py`: 1つの active area element 内で複数の候補き裂を評価し、最短寿命を選ぶ処理。
- `calculation/crack_life.py`: 1つの候補き裂について、Stage I/II 進展、CTSD、K 値、closure、寿命積分を評価する処理。

この分割により、旧スクリプトで深くネストしていた処理を、論文上の計算単位に近い順序で追えるようにしました。

## `crack_life.py` 内部の整理

`crack_life.py` は、計算核の中でも最も重要な部分です。ここでは旧スクリプトの計算式を変えずに、読み筋を作る整理を行いました。

主な変更は次の通りです。

- 初期き裂寸法、粒界データ生成、CTSD 評価、応力状態評価、K 値、closure、寿命積分を局所関数に分けました。
- Stage I / Stage II の判定や停止条件に、意味のある局所名を付けました。
- CTSD の `jj` のような意味が見えにくい変数を、`crack_tip_layer_idx` などの名前へ置き換えました。
- 粒界データの組を `GrainBoundaryData` としてまとめ、`rnList`, `Nd`, `PnList`, `RnAS`, `orList` の意味を追いやすくしました。
- 履歴配列の更新単位を小関数に分け、どのタイミングで `S_*` が更新されるかを追いやすくしました。

一方で、`S_*` 履歴配列そのものを dataclass に包むような抽象化は行っていません。更新順序を隠してしまう可能性があるためです。

## 計算過程の効率化

計算内容を変えない範囲で、同じ値を繰り返し取得・計算していた箇所を一部整理しました。目的はアルゴリズムの変更ではなく、候補き裂1本の計算中で不変な値や同じ参照結果を再利用することです。

`crack_life.py` の K 値積分では、Stage I / Stage II ともに Gauss 点ごとの応力場を6成分それぞれのループ内で繰り返し参照していました。変更後は、各 Gauss 点の `active_element_total_field_by_depth()` の結果を先に1回だけ取得し、その6成分を積分計算で再利用するようにしました。

```text
変更前: 成分ごとに同じ Gauss 点の field lookup を繰り返す
変更後: Gauss 点ごとに field lookup を1回行い、6成分で再利用する
```

また、closure 計算内の `HysterisisA(y, z)` 相当の処理は、同じ候補き裂では `field_values`, `y`, `z` が固定であり、評価点ごとに同じ基準主応力を再計算していました。変更後は `_surface_reference_principal_stress()` として `crack_life.py` 内に切り出し、候補き裂の計算開始時に1回だけ計算して `_calculate_closure_factor()` に渡す形にしました。

これらは、乱数呼び出し順序、履歴配列更新、分岐条件、CSV 出力形式を変えない範囲の効率化です。変更後も candidate 比較で既存 baseline CSV と完全一致することを確認しています。

一方で、`_interpolate_stage1_weight_function()` / `_interpolate_stage2_weight_function()` の cache 化は実施していません。これらは `griddata` や RBF 補間の返り値、浮動小数 key の扱いに依存するため、cache 化によって計算結果が変わる可能性があります。そのため、結果変更を許容する高速化課題として別扱いにしています。

## 結果型と出力の整理

旧スクリプトでは、計算結果の中間値と CSV 出力が近い位置にありました。

変更後は、計算単位ごとに result dataclass を返し、CSV 出力は `output.py` に分離しています。

- `CrackLifeResult`: `calculation/crack_life.py`
- `ElementLifeResult`: `calculation/element_life.py`
- `IterationResult`, `LoadCaseResult`: `calculation/load_case.py`
- `SimulationResult`: `runner.py`

これらは汎用 API のためではなく、計算単位ごとの戻り値を読みやすくするために置いています。CSV ファイル名と列形式は旧実装との比較を優先し、legacy 互換形式を維持しています。

## CLI と設定ファイルの整理

旧スクリプトでは、スクリプト内の値を書き換える形で条件を変更していました。

変更後は、通常実行入口として `cli.py` を実装しています。CLI 引数は、入力ディレクトリ、出力ディレクトリ、cache ディレクトリ、出力削除のような実行管理項目に絞りました。

シミュレーション条件は JSON config に記述します。

- 通常既定条件: `verification/configs/original_defaults.json`
- 重めの比較検証用 seed 固定条件: `verification/configs/heavy_seed42.json`
- 軽量検証条件: `verification/configs/lightweight_seed42.json`
- サンプル実行条件: `resources/sample_simulation.json`

通常既定条件とサンプル実行条件は `Multiscale_fatigue_model.org.py` に準じ、`sigma_nom=[150,160,170,180,190]`, `iteration_count=4`, `n_symm=4` としています。通常実行では random seed を指定しません。

## 検証コードの整理

旧実装との結果一致を確認するためのコードは、通常の `src/` 読解ルートから外し、`verification/` と `scripts/` に集めています。

主な検証スクリプトは次の通りです。

- `scripts/verification/Invoke-SmokeVerification.ps1`: 軽量な import/config/CSV 検証。
- `scripts/verification/Invoke-CandidateComparison.ps1`: 既存 baseline CSV を再利用し、`src` 版の出力と比較する。
- `scripts/verification/Invoke-BaselineComparison.ps1`: 旧実装と `src` 版の両方を再実行して比較する。
- `scripts/verification/Invoke-HeavyComparison.ps1`: 重めの seed 固定条件を、現行 legacy script と `src` 版で比較する。
- `scripts/verification/Compare-AbaqusCacheContent.ps1`: Abaqus cache の pickle 内部データを比較する。

これにより、研究者が通常読むべきコードと、リファクタリング品質保証のための検証コードを分離しました。

## あえて変更していない点

計算結果や乱数順序に影響しうるため、以下は意図的に大きく変更していません。

- 乱数呼び出し順序。
- CSV ファイル名と列形式。
- Python scalar、NumPy scalar、ndarray、list、補間器返り値の型の混在。
- `S_*` 履歴配列のデータ構造。
- `gData.pkl`, `FieldValues.pkl`, Abaqus cache の生成・読み込み順序。
- `print` による進行表示。

また、物理的意図の確認が必要な箇所では、計算結果が変わる修正を避けて保留しています。例として、`FoList[0]` と `FoList[Grain_i]` の使い分け、unstable fracture 後の履歴配列更新、CTSD 初期 slip response の分岐などがあります。

## まとめ

今回の変更は、疲労モデルそのものを変更するものではありません。旧スクリプトにまとまっていた処理を、入力準備、材料データ生成、計算核、出力、検証に分けた変更です。

`src/` 版では、論文実装の計算順序を追いやすくしつつ、同一条件・同一 seed で旧実装と CSV が一致することを確認できる構造にしています。通常の研究者は `config.py -> context.py -> runner.py -> load_case.py -> element_life.py -> crack_life.py -> output.py` の順に読むことで、旧スクリプトよりも計算の流れを追いやすくなります。
