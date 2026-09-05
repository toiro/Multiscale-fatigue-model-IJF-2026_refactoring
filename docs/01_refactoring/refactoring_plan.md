# Multiscale Fatigue Model Refactoring Plan

## 目的

`multiscale-fatigue-model/Multiscale_fatigue_model.py` を、以下の責務に分離し、論文実装として計算手順を追いやすい形にする。

1. 入力
2. 計算用データ生成
3. 計算
4. 出力

ここでいう「再利用可能」とは、汎用 API 化ではなく、計算核を入力準備・出力処理から切り離し、研究者が計算内容を読解・検証・修正できる状態にすることを指す。

リファクタリング中は、同じ入力条件・同じ乱数 seed で計算結果が変わらないことを最優先する。

## 基本方針

- `multiscale-fatigue-model/` は legacy 実装として残す。
- refactored 実装は `src/multiscale_fatigue_model_ijf_2026/` 以下に作る。
- 論文上の計算単位に対応する名前、構造、依存関係を優先する。
- `BasicParameters` は旧スクリプト由来の全体状態として扱い、最終的に `src/` から排除する。
- 過剰な抽象化、過剰な関数分割、応用利用向けの拡張点追加は避ける。
- 計算式、乱数呼び出し順序、分岐条件、丸め、list/NumPy の評価順序を不用意に変えない。
- 型注釈の追加と実値の型正規化は区別する。`float(...)`, `.item()`, `np.asarray(...)`, `list(...)` などの変換は計算結果へ影響しうるため、通常の読解性改善とは別タスクにする。
- 1タスク完了ごとは通常 smoke 検証を行う。
- baseline を回すと決めた作業単位では、smoke / legacy mini は省略してよい。
- 開発中は既存 baseline CSV を再利用する candidate 比較を優先する。
- candidate / baseline 比較の refactored 側実行は、通常 CLI 経由へ寄せる。
- 乱数順序・CSV形式・引き渡し前確認では、旧実装も再実行する baseline / heavy 比較を行う。
- baseline / candidate 比較はいずれも、同一 seed・同一条件の CSV 完全一致を基準にする。
- legacy 対応は最終的に最外周 façade に閉じ込め、計算核と計算核入力データからは排除可能な状態にする。

完了履歴と検証ログは [refactoring_log.md](refactoring_log.md) に分離する。

## 現在の構成

現在の `src/multiscale_fatigue_model_ijf_2026/` は、当初の責務分離に概ね沿っている。

- 入力: `config.py`, `cli.py`
- サンプル入力: `resources/`
- 計算用データ生成: `parameters.py`, `abaqus.py`, `material.py`, `field_values.py`, `context.py`, `paths.py`
- 計算: `calculation/crack_life.py`, `calculation/element_life.py`, `calculation/load_case.py`
- 実行制御: `runner.py`
- 結果と出力: 各計算単位の result dataclass, `output.py`
- 検証用外周: `verification/smoke.py`, `verification/compare_csv_outputs.py`, `verification/validate_output_csv.py`, `verification/compare_abaqus_cache.py`

通常実行経路は legacy 互換 shim に依存しない状態まで移行済みである。`verification/` は smoke と比較・検査 helper に絞り、通常読解ルートから外す。

## 目標アーキテクチャ

### 入力層

実行条件は `SimulationConfig` に集約する。

通常 CLI では、材料、seed、応力、iteration などのシミュレーション条件を個別のコマンドライン引数にしない。これらは JSON 設定ファイルに記述し、CLI は `--config-file`, `--base-dir`, `--output-dir`, `--cache-dir`, `--delete-existing-output` などの実行管理項目に絞る。

主な項目:

- `base_dir`
- `output_dir`
- `cache_dir`
- `steel`
- `specimen_type`
- `thickness_sign`
- `crystal`
- `sigma_nom`
- `iteration_count`
- `r_ratio`
- `n_symm`
- `c_paris`
- `n_paris`
- `delta_delta_th`
- `random_seed`
- `max_active_elements`
- `delete_existing_output`

既定値は `multiscale-fatigue-model/Multiscale_fatigue_model.org.py` と一致させる。通常実行では random seed を指定しない。比較検証用の seed 固定条件や、軽量検証用の `sigma_nom=[150]`, `iteration_count=1`, `n_symm=1`, `max_active_elements=1` は JSON config で明示し、通常の既定値とは分けて扱う。

### 計算用データ生成層

`SimulationConfig` から、事前処理に必要な入力と計算核へ直接渡す入力を分けて構築する。

`SimulationContext` は実行全体の文脈を持つ。

- `config`
- 事前処理用の入力条件
- `material`
- `field_values_by_load`
- `parameter_snapshot`
- 入力、出力、cache に関する情報

`SimulationContext` は I/O や実行管理を含むため、解析計算の心臓部へそのまま渡さない。

legacy スクリプト由来の属性名や fallback は、この層より内側へ恒久的に置かない。`BasicParameters` 互換が必要な場合は `verification/` 側の façade として扱い、`src/` の通常読解ルートから排除する。

### 計算層

計算層はファイル出力を行わず、論文計算の確認・比較・修正に使える結果データを返す。

計算核には `SimulationContext` 全体ではなく、解析計算に必要なパラメータだけを準備して渡す。

現在の計算核入口は `CalculationInputData` である。

`CalculationInputData` は、外側の入力準備境界で `PaperModelParameters`、材料 import 結果、field values から作る。これは汎用 API のためではなく、計算核に入る物理量と条件を明示するための構造である。

現在の `calculation/inputs.py` は、計算核が必要とする入力 dataclass の正本として扱う。外部ファイル、config、cache、`MaterialDataImporter` の事情は calculation の外側で `CalculationInputData` へ写像し、計算核と `CalculationInputData` は整理済みの入力データだけを前提に読める状態を維持する。

- `SpecimenGeometry`
- `CrackGrowthConstants`
- `EvaluationPointDefinition`
- `MicrostructureModel`
- `MaterialStrengthProperties`
- `WeightFunctionData`
- `StressFieldData`

### 出力層

CSV 出力は計算ロジックから分離する。

- `calculate_*` 関数は CSV を書かない。
- `calculation/` は `output.py` に依存しない。
- `run_simulation` は `SimulationContext` を受け取らない。
- `run_simulation` は `CalculationInputData` を直接受け取る。
- 出力つき実行では `OutputContext` を明示的に渡す。
- `SimulationContext` から直接実行する adapter は過渡構造として扱い、通常 CLI 経路が安定した後は削除候補とする。
- CSV ファイル名は当面 legacy 形式を維持する。
- 出力先は `SimulationConfig.output_dir` で指定する。
- 新しい出力形式や応用利用のための拡張点は、論文実装の読解性を下げない場合に限って検討する。

### Legacy 互換境界

legacy 互換と検証用 adapter は、最終的には次の最外周だけに残す。

- original script と比較する検証スクリプト
- `verification/smoke.py`
- 外側の入力準備層における prepared objects -> `CalculationInputData` 変換境界

context adapter route は旧実装そのものではなく、`src` 内の別入口を通すだけだったため、Phase Last の単純化で削除済み。

逆に、次の場所には legacy 対応を恒久的に残さない。

- `calculation/crack_life.py`
- `calculation/element_life.py`
- `calculation/load_case.py`
- `calculation/inputs.py` の最終的な dataclass 定義
- 各計算単位の result dataclass の研究量名

ただし、移行中は結果同一性を守るため fallback を残す場合がある。その場合も「外側 façade へ移すまでの暫定措置」として扱い、計画と todo に残す。

### 研究者向け読解性

論文内容とコードの照合を容易にする。一般的なライブラリ化ではなく、研究者が計算内容を追い、必要に応じて修正できることを優先する。

当面は、これ以上の層追加ではなく、既に分けた構造が論文の読み筋に沿っているかを確認し、必要なら単純化する。

優先する対応:

- `CalculationInputData` は、計算核へ入る物理量を明示するために使い、汎用 API 化のためには増やさない。
- legacy fallback は外側の入力準備境界に閉じ込め、計算核へ再流入させない。
- 旧実装互換 shim は `verification/` 側に置き、一般研究者の通常読解ルートには含めない。
- `BasicParameters` に残る研究条件は、`src/` 内の正本にしない。事前処理用入力、派生値生成、計算核入力に分け、旧名互換は再導入しない。
- `MaterialDataImporter` の公開面は、`grain_distributions`, `mechanical_properties`, `abaqus_field_cache`, `weight_function_resources`, `microstructure_data` の typed view に絞る。旧名属性は入力準備内部の作業状態として扱い、新たな外部依存を増やさない。
- `MaterialDataImporter` の内部作業属性は、事前に大量の `None` スロットを並べず、値が生成される `_load_*` / `_build_*` の中で初めて代入する。必要な場合だけ型注釈で存在を示す。
- `crack_life.py` では、これ以上 helper を細かく増やしすぎず、Stage I/II、CTSD、K 値、closure、寿命積分の主導線を読みやすく保つ。
- raw tuple や旧式変数名は、計算結果を変えずに意味が分かる名前・局所コメント・結果変換境界で補う。
- 乱数利用箇所は、乱数順序を変えずに、どの物理モデルに属する確率変数かを追えるようにする。
- 結果型の整理は、CSV 出力や legacy 互換を壊さない範囲で必要最小限に留める。

コード付随の説明ドキュメントは、コード構造が固まった後に最小限だけ整備する。`docs/refactoring_plan.md` と `docs/refactoring_todo.md` は作業管理記録として更新する。

## フェーズ状況

### Phase 1: `CalculationContext` の導入 完了

- `calculation/context.py` と `CalculationContext` は過渡構造として導入後、削除済み。
- `context.py` は実行準備の流れを担い、prepared objects から `CalculationInputData` を作る細かな helper は外側の入力準備層に分ける。
- `calculate_load_case`, `calculate_element_life`, `calculate_crack_life` は `CalculationInputData` を直接受ける。
- 計算式、乱数呼び出し順序、戻り値、CSV 出力形式は変更しない。

### Phase 2: 計算核入力データの分解

- `calculation/inputs.py` に用途別 dataclass を追加済み。
- `load_case.py` は `SpecimenGeometry`, `EvaluationPointDefinition`, `StressFieldData` の参照を使い始めている。
- `element_life.py` の raw kernel は `CalculationInputData` 経由の参照へ移行済み。
- `crack_life.py` は Paris 則定数、応力比、Stage I 境界の一部を `CrackGrowthConstants` / `EvaluationPointDefinition` 経由へ移行済み。
- `crack_life.py` の試験片形状参照は `SpecimenGeometry` 経由へ移行済み。
- `crack_life.py` の weight function 参照は `WeightFunctionData` 経由へ移行済み。
- `crack_life.py` の material strength 参照は `MaterialStrengthProperties` 経由へ移行済み。
- `crack_life.py` の評価点参照は `EvaluationPointDefinition` 経由へ移行済み。
- `crack_life.py` の微視組織生成とすべり面 resolver 参照は `MicrostructureModel` 経由へ移行済み。
- `crack_life.py` から `BasicParams.*` / `DataImport.*` の直接参照は撤去済み。
- `run_simulation` は `runner.py` に移し、`CalculationInputData` と任意の `OutputContext` を受ける形へ移行済み。
- 参照置換は一属性または一小領域ずつ進め、各単位で smoke 検証を実施した。
- 以後は新しい層を増やすより、導入済みの構造が論文の読み筋を助けているかを点検する。

### Phase 3: 計算式の安全な構造化 完了

- `crack_life.py` の `_crack_life_raw` に物理モデル単位の節コメントを追加済み。
- `safe_arccos`, crack aspect 関数、evaluation points 生成は private 関数へ切り出し済み。
- CTSD 計算は `_evaluate_ctsd_at_crack_depth` と関連 helper へ切り出し済み。
- K 値計算、remote stress 変換、closure factor 計算は private 関数へ切り出し済み。
- 初期き裂寸法、粒界生成、life integration は private 関数へ切り出し済み。
- `crack_life.py` の raw tuple 境界は当面維持し、同じファイル内で `CrackLifeResult` に変換する。

### Phase 4: 材料データと微視組織生成の分離 完了

- `MaterialDataImporter` の初期化処理を、入力データ読み込み、材料強度、Abaqus field cache、weight function、微視組織生成、view 生成に分けた。
- CSV 入力、引張特性、摩擦強度、Abaqus field cache、weight function constants、Pearlite fraction、`gData` cache、`ModelSize` は段階メソッドとして分離済み。
- `GrainDistributionData`, `MechanicalPropertyData`, `AbaqusFieldCacheData`, `WeightFunctionResources`, `MicrostructureGeneratedData` を導入した。
- `MaterialDataImporter` は typed view 5つを公開面とし、legacy 属性名は view 構築のための内部作業状態へ縮小する。
- `calculation/inputs.py` の legacy fallback は撤去済みで、legacy 属性名の読み替えは `context.py` の入力準備境界に集約済み。
- 乱数呼び出し順序、cache 読み込み順序、Pearlite thickness CSV の探索順は維持する。
- `FieldValuesFunction` の旧名属性 fallback は削除済みで、`abaqus_field_cache` view だけを読む。旧名属性は private 作業属性へ寄せ、外部参照は typed view 5つに限定済み。
- `_initialize_legacy_attribute_slots()` は削除済み。Gauss 10点はモジュール定数とし、条件分岐で未生成になりうる値だけを該当する生成関数内で明示する。

### Phase 5: façade 解消と実行順の見える化 完了

過剰な抽象化を増やす前に、二重構造になっている façade を低リスク領域から解消し、その後で実行順を見える化する。

優先順:

- `FieldValuesFunction` が読む `EES`, `PES`, `AES`, `f_sigma` などを `abaqus_field_cache` view 経由へ寄せた。
- `output.py` の材料強度参照を `mechanical_properties` view 経由へ寄せた。
- weight function まわりは、計算経路では `WeightFunctionData` が正本になっているため追加変更しない。
- `gData`, `PRateN`, `Ng`, `Mg` は乱数と cache に関わるため、legacy 属性を当面残す。
- façade 解消後に、`build_context()`、`MaterialDataImporter`、`run_simulation()`、`calculate_load_case()`、`calculate_element_life()`、`calculate_crack_life()`、`_crack_life_raw()` の実行順 docstring を追加した。
- `print` は研究者が実行順を追う手がかりでもあるため、現時点では logger/progress callback 化を急がない。必要性が明確になった場合のみ、既定の標準出力を維持した最小変更で扱う。
- `verification/` は高速 smoke と比較・検査 helper に縮小済み。旧名互換 shim と context adapter runner/CLI は Phase Last の単純化で削除済み。

### 完了: 結果型を生成する計算単位の近くへ移す

計算途中の更新単位は小関数境界として固定済みである。次は、初期リファクタリング時に raw tuple 整理のため導入した `results.py` の dataclass 群を、結果を生成する計算単位の近くへ移す。

方針は、研究者が `calculate_*` の実行順を追うとき、その関数が作る結果型を同じファイルまたは同じ計算単位で確認できるようにすることである。汎用 result 型置き場としての `results.py` は縮小し、最終的には削除可能か判断する。

進捗:

- particle data 生成系は `microstructure.py` へ抽出済み。
- `paths.py` の filename helper は `BasicParameters` 全体ではなく明示引数を受ける形へ移行済み。
- `FieldValuesFunction`, `MaterialDataImporter`, `AbaqusDatabaseCreator` は、それぞれ必要入力だけを持つ dataclass を受ける形へ移行済み。
- `BasicParameters` 旧名は `src/` から撤去済みで、旧名互換 shim も削除済み。
- 試験片寸法、active zone、評価点生成、結晶方位生成、すべり面 resolver は `parameters.py` の独立関数へ切り出し済み。
- `PaperModelParameters` は長い互換メソッドを持たない薄い属性束へ畳み直し済み。
- `context.py` の Abaqus / material / field values の準備は小さな helper に分割済み。計算核入力の組み立て helper は外側の入力準備層へ分ける。
- `AbaqusDatabaseCreator` の `FieldValues.pkl` 新規生成枝は検証済みで、生成 cache を使った candidate 比較は CSV 完全一致。
- `scripts/verification/Compare-AbaqusCacheHash.ps1` を追加し、Abaqus cache の byte-level hash 差分を検出できるようにした。
- legacy cache と再生成 cache は CSV 結果は一致するが、`FieldValues.pkl` の hash は一致していない。
- `verification/compare_abaqus_cache.py` と `scripts/verification/Compare-AbaqusCacheContent.ps1` を追加し、pickle 内部の主要データを比較できるようにした。
- legacy cache と再生成 cache は、内部比較では一致している。
- `context.py` の `params` 側 `_get(...)` fallback と material legacy 属性 fallback は撤去済みで、typed view を直接読む形へ移行済み。
- `context.py` の `SimulationConfig` から `PaperModelParameters` への変換は `_build_paper_model_parameters()` に閉じ、`build_context()` の実行順を短くした。
- `_crack_life_raw()` の履歴初期化、評価点ごとの履歴反映、unstable fracture 時の後続点更新、板厚到達後の後続点埋めは小関数へ分離済み。
- `_integrate_life_cycle()` は Stage I の点更新と Stage II の3点窓更新へ分離済み。
- `_evaluate_ctsd_at_crack_depth()` の重複した層進展ループは `_advance_ctsd_through_grain_layers()` へ集約済み。
- `_generate_grain_boundaries()` の粒数縮小/拡張探索は意味名を持つ小関数へ分離済み。
- `_generate_grain_boundaries()` が生成する粒界・方位・摩擦強度データは `GrainBoundaryData` としてまとめ、CTSD 評価へ組で渡す形へ移行済み。
- `element_life.py` の最短候補判定と採用処理は、単一候補き裂の履歴と area element 内の最短候補を区別して読める境界へ分離済み。
- `_element_life_raw()` は area element 内で採用された最短候補き裂を `ElementLifeResult` として直接返す形へ移行済み。
- `CrackGrowthHistory` のように mutable な計算途中状態を包む dataclass は、現時点では追加しない。更新順序を隠す抽象化になりやすいため、必要性が再び出た場合は Phase Last の単純化観点で判断する。

優先順:

- 未使用の `OutputTables` は削除済み。
- `CrackLifeResult` と raw tuple 変換は、計算層内の単一候補き裂履歴として `calculation/crack_life.py` へ移動済み。
- `ElementLifeResult` は、area element 内で採用された最短候補き裂の結果として `calculation/element_life.py` へ移す。
- `IterationResult` と `LoadCaseResult` は、load case 計算が生成する集約結果として `calculation/load_case.py` へ移す。
- `SimulationResult` は、実行全体を束ねる `runner.py` へ移す。
- `element_result_from_raw()` は削除済みで、通常の element 計算経路では raw tuple を返さない。
- `results.py` は参照がなくなったため削除済み。
- `calculate_crack_life()` は当面維持し、`_crack_life_raw()` の raw tuple 境界を同じファイル内で `CrackLifeResult` に変換する入口として扱う。
- `S_*0` 履歴配列は、`Result` ではなく「単一候補き裂の計算途中状態」として扱う境界を維持する。
- `_crack_life_raw()` の主ループは論文 Submodel 3 の主導線として残し、これ以上 helper を細かく増やしすぎない。
- `S_cyc0` は近傍点を巻き込んで補正されるため、単純な点更新履歴として扱わない構造を維持する。
- Python scalar / NumPy scalar / ndarray / list / 補間器返り値の混在をそろえる作業は、必要性はあるが結果同一性リスクが高いため保留課題として管理する。
- `parameters.py` は現状を維持する。`context.py` は実行準備の流れに絞り、計算入力の細かな組み立て helper は外側の入力準備層へ分ける。
- `rg "BasicParameters|BasicParams" src` が該当なしの状態は維持する。
- 開発中の反復確認には、既存 baseline CSV を再利用する `scripts/verification/Invoke-CandidateComparison.ps1` を使う。

移行結果:

1. `ElementLifeResult` は `calculation/element_life.py` へ移動済み。
2. `IterationResult` と `LoadCaseResult` は `calculation/load_case.py` へ移動済み。
3. `SimulationResult` は `runner.py` へ移動済み。
4. `results.py` は削除済み。
5. `py -m compileall src verification` と `scripts/verification/Invoke-CandidateComparison.ps1` は通過済み。

### Phase Last: 研究者向け単純化

すべての構造整理と結果同一性確認が落ち着いた後、最後に必ず、プログラミング初学者の研究者が追いやすい構造へ畳み直す。以後の各作業でも、この観点に反する抽象化を増やしていないか確認する。

このフェーズは新しい抽象化を増やすためではなく、リファクタリング途中で安全のために導入した抽象化を見直し、不要なものを減らすために置く。

確認すること:

- 読むべき入口が少数に絞られているか。
- `pyproject.toml` の console script と `cli.py` が、通常実行入口として既存経路だけを呼ぶ状態になっているか。
- `SimulationContext`, `CalculationInputData`, `context.py` の入力生成の関係が過剰に複雑でないか。
- adapter や fallback が残りすぎていないか。
- context adapter route のような過渡的検証入口が用済みになっていないか。
- 検証専用 helper が `verification/` にまとまり、通常読解ルートへ混ざっていないか。
- `MaterialDataImporter` の通常読解上の公開面が typed view 5つに見えているか。
- `MaterialDataImporter` の読み筋が、事前スロット初期化ではなく実際の生成順に沿っているか。
- `BasicParameters` が `src/` の通常読解ルートに残っていないか。
- legacy 互換が最外周 façade だけに閉じており、計算核入力と計算核から排除可能か。
- private helper が多すぎて、逆に実行順を追いにくくしていないか。
- 型表現が研究量の理解に役立っているか。単にクラス数を増やしていないか。
- コード構造が固まった後、必要最小限の読む順番だけを整備しているか。

原則:

- 詳細な汎用 API より、論文計算を追うための読み筋を優先する。
- 高度な型表現より、素直な関数名、素直なデータ名、短い実行順を優先する。
- 結果同一性を崩さない範囲で、過渡期の抽象化を削る。
- CLI は、既存の `SimulationConfig -> build_context -> build_calculation_input_data -> build_output_context -> run_simulation` 経路を呼ぶだけにし、計算核へ別経路を作らない。
- CLI の通常実行は設定ファイル方式とし、シミュレーション条件の追加・変更は JSON の項目追加として扱う。
- サンプル実行用の入力ファイルは `resources/` に置き、`--base-dir resources` で読める状態にする。`resources/sample_simulation.json` は `.org.py` 準拠の通常設定に合わせる。cache 生成物の `.pkl` は入力ファイルとは分ける。

## 成功条件

- 既存の通常実行結果が維持される。
- 同じ `random_seed` と同じ入力条件で、リファクタリング前後の CSV が一致する。
- 引き渡し前の baseline 比較で、legacy と `src` の CSV 一致を確認できる。
- 計算核を入力準備・出力処理から切り離して読める。
- 出力先フォルダを自由に指定できる。
- 軽量設定で短時間に検証できる。
- 計算核が I/O 文脈や CLI 文脈に依存しない。
- 研究者が論文上のサブモデルとコード上の責務を追いやすい。
- 検証用外周は、結果保証に必要な smoke / baseline / candidate 比較に絞られている。
