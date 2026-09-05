# Incorporate Several Parameter Conditions Plan

## 目的

`N50R_CS_T50` だけを前提にしていた整理版実装へ、複数の
`steel` / `specimen_type` / `thickness_sign` 条件を段階的に取り込む。

対象条件:

- `B_Smooth_T16`, `G_Smooth_T16`, `N50R_Smooth_T16`
- `B_R008_T24`, `G_R008_T24`, `N50R_R008_T24`
- `B_R100_T24`, `G_R100_T24`, `N50R_R100_T24`
- 既存基準条件: `N50R_CS_T50`

ここでの主目的は、パラメータ条件と入力リソースを見通しよく扱い、
各条件を比較可能な形で実行できるようにすることである。これは
読解性リファクタリングではなく、対応入力条件の拡張作業として扱う。

## 基本方針

- 旧実装・既存 `N50R_CS_T50` の結果同一性は維持する。
- 条件追加は `steel` / `specimen_type` / `thickness_sign` の組み合わせを明示し、未対応条件は早期に `ValueError` で止める。
- 条件ごとの入力ファイルは `resources/<steel>_<specimen_type>_<thickness_sign>/` に置く。
- 実行時に読む入力ファイルは条件ディレクトリ内で完結させる。共通ファイルでも暗黙の親ディレクトリ fallback は使わない。
- 計算式、乱数呼び出し順序、分岐条件、CSV 形式は不用意に変えない。
- 旧実装由来の潜在バグに見える箇所は、条件追加とは別タスクとして扱い、比較方針を決めてから変更する。

## 現在の構成

- `parameters.py`
  - `SUPPORTED_PARAMETER_CONDITIONS`
  - `THICKNESS_BY_SIGN`
  - `WIDTH_BY_SPECIMEN_TYPE`
  - `ACTIVE_ZONE_BY_SPECIMEN_TYPE`
  - `STAGE2_POINTS_BY_CONDITION`
- `resources/`
  - `sample_simulation.json`
  - `configs/*.json`
  - 条件別ディレクトリ
    - `.inp`, `.dat` または `.dat.zip`
    - 材料・粒径系 CSV
    - `CombinedData_Ellipse_WF_CF.json`
- `paths.py`
  - 条件ディレクトリが存在する場合はそこを読む
  - 入力ファイルは解決済みディレクトリ直下からのみ読む

## 検証方針

- ドキュメントのみの変更では実行検証を省略してよい。
- `parameters.py`, `paths.py`, `context.py` に触れた場合は、通常:
  - `.venv\Scripts\python.exe -m compileall src verification`
  - `scripts\verification\Invoke-StaticAnalysis.ps1`
  - `scripts\verification\Invoke-ConditionPreflight.ps1`
  - `scripts\verification\Invoke-SmokeVerification.ps1`
- `scripts\verification\Invoke-ConditionPreflight.ps1` は寿命計算、Abaqus parse、`gData.pkl` 生成を行わず、条件表、`resources/` の必須ファイル配置、軽量 config、context 境界解決を確認する。
- `verification.check_resources` は `resources/configs/` の通常計算 config も検査し、軽量設定の混入を防ぐ。
- `scripts\verification\Invoke-ParameterConditionVerification.ps1` はその内部実体として残す。
- `N50R_CS_T50` の計算結果や CSV 形式に影響しうる場合:
  - `scripts\verification\Invoke-CandidateComparison.ps1`
- 追加条件の初回実行では、軽量 config を作って cache 生成と CSV validation を行う。
- 追加9条件は旧実装再実行との一致を当面要求しない。初回通過した軽量 config の CSV を `outputs/condition_reference/<condition>_seed42/` に固定し、以後の回帰確認は `scripts\verification\Invoke-ConditionReferenceComparison.ps1` で参照 CSV と現在出力の完全一致を確認する。
- 追加条件の cache は容量が大きく、実行環境依存の再生成コストも高いため比較基準にはしない。cache 再生成や参照 CSV 更新を行う場合は、理由と実行 config を log に記録する。
- FieldValues / `gData.pkl` を再生成した場合、既存 baseline CSV は前提 cache が変わっている可能性があるため、`scripts\verification\Invoke-BaselineComparison.ps1` で旧実装と整理版を同じ cache 前提で比較し直す。

## 通常計算導線

`resources/` に置いた10条件を通常計算として実行する入口は、
`resources/configs/<condition>.json` と
`scripts\Invoke-ConditionResourcesRun.ps1` の組み合わせとする。

- 通常計算 config は `resources/configs/` に置く。
- config 名は条件ディレクトリ名と同じ `<steel>_<specimen_type>_<thickness_sign>.json` とする。
- 通常計算 config は `.org.py` 由来の既定値
  `sigma_nom=[150,160,170,180,190]`, `iteration_count=4`, `n_symm=4`
  を明示し、`random_seed` と `max_active_elements` は入れない。
- 軽量検証 config は `verification/configs/conditions/lightweight_*.json` に置き、
  通常計算導線とは分ける。
- `resources/sample_simulation.json` は `N50R_CS_T50` の代表サンプルとして残すが、
  10条件の通常計算入口の正本にはしない。
- `verification.check_resources` は、条件ディレクトリの入力 manifest と合わせて
  通常計算 config の存在・内容も検査する。

## 条件コンテクスト境界整理計画

`steel` / `specimen_type` / `thickness_sign` は、現在以下の3つの意味を同時に持っている。

- 計算パラメータ決定: 寸法、active zone、評価点、材料入力条件を決める。
- ファイル名決定: 条件ディレクトリ、Abaqus 入力、cache、CSV 出力名を決める。
- 計算核内分岐: `specimen_type` が crack growth 側の一部分岐に残っている。

今回の目的は、この3つの意味が計算核へ過剰に入り込まないようにすることである。将来の汎用 API 化ではなく、今回対象の10条件を安全に扱うための境界整理とする。

### 到達状態

- `steel` / `specimen_type` / `thickness_sign` は入力準備層で `SimulationCondition` として受け取り、計算パラメータとファイル名を解決した後は原則として役割を終える。
- 計算核へ `steel` と `thickness_sign` は渡さない。
- 計算核へ raw `specimen_type` は渡さない。必要な分岐は、物理・計算上の意味に合わせた値へ変換して渡す。
- 出力 CSV ファイル名は現段階では変更しない。`model_name` を出力名 body として維持する。
- FieldValues / gData cache 名は、現状どおり `steel` + `specimen_type` ベースを維持する。`thickness_sign` が生成条件に関わらない限り変更しない。

### 計算核へ残す候補パラメータ

現状 `crack_life.py` で `specimen.specimen_type in ["CS", "CSS"]` が使われている箇所は2箇所である。ここは `specimen_type` そのものではなく、以下のような計算意味の値へ変換する。

- 候補名: `surface_crack_shape_mode`
- 値案:
  - `semi_elliptical_surface_crack`: 旧 `CS` / `CSS` 側
  - `through_width_or_three_point_bending`: 旧 `Smooth` / `R008` / `R100` 側

命名は実装直前に `crack_life.py` の式を再確認して決める。重要なのは、`CS` というファイル・試験片名ではなく、計算分岐の意味を表すことである。

### 段階実装

1. 現状棚卸
   - `steel`, `specimen_type`, `thickness_sign` の参照箇所を、条件決定、ファイル名決定、計算核分岐に分類する。
   - 追加検証は不要。文書更新のみ。

2. ファイル名決定の軽い集約
   - `context.py` で `model_name` と条件ディレクトリを早期に決める。
   - 必要なら軽量な `ResolvedResourceNames` または局所変数で、Abaqus model name、FieldValues cache filename、gData cache filename、出力 filename body をまとめる。
   - `MaterialDataImporter` / `AbaqusDatabaseCreator` へ渡す raw 条件は、ファイル名と入力選択に必要な範囲に留める。
   - 出力 CSV 名は変更しない。

3. 計算パラメータ決定の終端を明確化
   - `PaperModelParameters` から `CalculationInputData` を作る時点で、`steel` / `thickness_sign` を落とす。
   - `specimen_type` は raw 文字列のまま渡さず、計算意味の値へ変換する。
   - `build_parameter_snapshot()` には入力条件の記録として残してよい。これは計算核入力ではなく実行記録である。

4. 計算核内の `specimen_type` 分岐置換
   - `SpecimenGeometry.specimen_type` を計算意味名の field に置き換える。
   - `crack_life.py` の `if specimen.specimen_type in ["CS", "CSS"]` を、新 field の値判定へ置換する。
   - mock smoke fixture も新 field に合わせる。

5. 検証
   - まず軽量検証:
     - `.venv\Scripts\python.exe -m compileall src verification`
     - `scripts\verification\Invoke-StaticAnalysis.ps1`
     - `scripts\verification\Invoke-ConditionPreflight.ps1`
     - `scripts\verification\Invoke-SmokeVerification.ps1`
   - `N50R_CS_T50` の計算分岐名を置き換えるため、可能なら `scripts\verification\Invoke-CandidateComparison.ps1` で既存 baseline CSV と完全一致を確認する。
   - 追加条件は旧実装一致を要求せず、条件表・resources manifest・入力準備境界、CSV validation、固定済み参照 CSV との一致を優先する。

### 非目標

- 出力 CSV ファイル名の変更。
- cache filename への `thickness_sign` 追加。
- 条件表の JSON/YAML 外部化。
- 10条件を超える汎用的な条件解決 API 化。

## Weight Function RBF 境界整理計画

現状の `WeightFunctionData` は、single RBF と split RBF を別 field として
計算核へ渡している。

- `weight_function_rbf`
- `weight_function_rbf_low`
- `weight_function_rbf_high`

さらに Stage II 側では `SpecimenGeometry.uses_split_stage2_weight_function`
を見てどの RBF を使うか決めている。この構造では、RBF の持ち方という
weight function table 側の事情が、specimen geometry 側の field として
計算核に漏れている。

### 到達状態

- `SpecimenGeometry` から `uses_split_stage2_weight_function` を外す。
- single / split の選択は、weight function resource 構築時に完了させる。
- 計算核は RBF の内部構造を知らず、Stage II weight function の評価だけを呼ぶ。
- `CS` と非 `CS` の現行結果は変えない。

### 方針

- `WeightFunctionData` に Stage II weight function 評価用 callable を持たせる。
- callable は `material.py` 側で作る。
- single RBF の場合は既存 `weight_function_rbf([[at, ac]])[0]` を使う。
- split RBF の場合は `at <= 0.6` で low、`at > 0.6` で high を選ぶ。
- `crack_life.py` の `_interpolate_stage2_weight_function()` は、
  `1 / sqrt(thickness * at)` の係数適用だけを担当する。
- Stage I weight function は現状どおり constants から都度補間する。

### 段階実装

1. 現状棚卸
   - `weight_function_rbf`, `weight_function_rbf_low`,
     `weight_function_rbf_high`, `uses_split_stage2_weight_function` の参照箇所を確認する。
   - `L135_U175_S20_R-1.py.ref` の `KWeight` と `weight_function()` の対応を記録する。

2. 評価 callable の導入
   - `WeightFunctionResources` / `WeightFunctionData` に
     `stage2_weight_function` を追加する。
   - `material.py` で single / split RBF を包む callable を作る。
   - 既存 field は移行中の比較用として一時的に残してよい。

3. 計算核から RBF 構造を隠す
   - `_interpolate_stage2_weight_function()` は
     `weight_function.stage2_weight_function(at, ac)` を呼ぶ。
   - `SpecimenGeometry.uses_split_stage2_weight_function` を削除する。
   - `context.py` と smoke fixture を更新する。

4. 不要 field の削除
   - `weight_function_rbf`, `weight_function_rbf_low`,
     `weight_function_rbf_high` が計算核から参照されなくなったことを確認する。
   - 移行用 field を残す必要がなければ `WeightFunctionData` から削除する。

5. 検証
   - 軽量検証:
     - `.venv\Scripts\python.exe -m compileall src verification`
     - `scripts\verification\Invoke-StaticAnalysis.ps1`
     - `scripts\verification\Invoke-ConditionPreflight.ps1`
     - `scripts\verification\Invoke-SmokeVerification.ps1`
   - 既存条件:
     - `scripts\verification\Invoke-CandidateComparison.ps1`
   - 追加条件:
     - `N50R_Smooth_T16`, `N50R_R008_T24`, `N50R_R100_T24` の
       `scripts\Invoke-ConditionResourcesRun.ps1` 実行と CSV validation。
     - 固定済み参照 CSV がある場合は
       `scripts\verification\Invoke-ConditionReferenceComparison.ps1`。

## 外部レビューを受けた Readability 方針

`docs/parameter_condition_reading_difficulties.md` の指摘は外形的な読みにくさを
整理しているが、README を厚くする前に、コード構造で読解負荷そのものを
減らせるものを優先して検討する。次段階では計算結果を変えず、条件の
意味と効き方がコード上の境界から自然に読める形へ寄せる。

### 優先して直すもの

1. 条件カタログをコード上の読解単位にする
   - `SUPPORTED_PARAMETER_CONDITIONS` の set と、寸法・active zone・評価点の
     別表を読むだけでは「1条件が何を決めるか」が分散して見える。
   - 新しい汎用 API ではなく、今回対象10条件の読み取り view として
     `SimulationCondition` / `ResolvedParameterCondition` 相当の dataclass を導入する。
   - `SimulationCondition` は config 由来の raw 条件を表す:
     `steel`, `specimen_type`, `thickness_sign`, `model_name`。
   - `ResolvedParameterCondition` は計算準備で使う解決済み view を表す:
     `condition`, `dimensions`, `active_zone`, `evaluation_points`,
     `cache_name_key`, `weight_function_table_family`,
     `nominal_stress_extraction_mode`。
   - `cache_name_key` は現行どおり `steel + specimen_type` とし、
     `thickness_sign` は含めない。条件別 cache root による分離方針を維持する。
   - `ResolvedParameterCondition` を読めば、README の大きな説明表なしに
     1条件が決める主要値を追える状態にする。

2. `specimen_type` の多重効果を named decision へ分ける
   - `specimen_type` そのものが幅、active zone、weight function table 選択、
     Abaqus nominal stress 抽出を直接決めているように見えるのが読みにくい。
   - 計算核へ raw `specimen_type` を戻さず、入力準備側で意味別の値へ分ける。
   - まず導入する named decision:
     - `weight_function_table_family`
       - `smooth`
       - `three_point_bending`
       - `compact_specimen`
     - `nominal_stress_extraction_mode`
       - `smooth_dsload`
       - `three_point_bending_rf1`
       - `compact_specimen_dsload`
   - `specimen_geometry_family` は、現時点では `dimensions` と `active_zone` が
     具体値として解決されているため導入しない。必要が出た時点で追加する。

3. 旧名 `type` / `T` の読み替え負担低減
   - `PaperModelParameters` 内部の `self.type` / `self.T` は旧実装互換名として
     すぐには削除しない。
   - 代わりに `specimen_type` / `thickness_sign` の readable alias を用意し、
     新しい境界コードや snapshot では alias を優先して読む。
   - 旧名の完全撤去は、CSV 一致確認と差分量を見て別タスクにする。

4. Abaqus field cache 生成分岐の位置づけ明示
   - `abaqus.py` の `Smooth`, `R008/R100`, `CS/CSS` 分岐は、
     計算核の specimen 分岐ではなく、入力ファイル形式と nominal stress
     抽出方式の違いとして扱う。
   - `read_dat()` が raw `specimen_type` を直接判定するのではなく、
     `AbaqusImportInput` に渡された `nominal_stress_extraction_mode` を判定する形にする。
   - 各抽出方式に小さな関数名を付けることで、README 説明より先にコードで意図を読む。

5. resources の現在状態に合わせた更新
   - `resources/README.md` の "Planned additional directories" は現在状態と
     ずれているため、supported condition directories として書き直す。
   - `resources/` にあるが通常入力として使わない重複ファイルがあれば、
     入力 manifest の期待値と照合して扱いを決める。

### 外部レビュー指摘の扱い

- コード構造で潰す:
  - `thickness_sign` と実板厚値の対応が追いにくい。
  - `specimen_type` が複数の計算条件を同時に決めている。
  - 対応条件と派生値が複数表に分かれている。
  - ファイル名、寸法、評価点、cache への効き方が分散している。
  - Abaqus field cache 生成の raw `specimen_type` 分岐が読みにくい。
  - config 名と旧実装名 `type` / `T` が混在している。
- 最小ドキュメントで説明する:
  - `B`, `G`, `N50R`, `Smooth`, `R008`, `R100`, `CS` の物理的略号。
  - `resources/README.md` の現在の supported directory 一覧。
  - 条件ディレクトリ自動選択の入口導線。
- Deferred に置く:
  - `SmoothT`, `T25`, `CSS`, `B/G_T50` など今回対象外条件。
  - Smooth の Bainite/Martensite 専用 nominal stress 抽出分岐。
  - 条件表の JSON/YAML 外部化。

### 実装順

1. `parameters.py` に condition view を追加する。
   - `SimulationCondition`
   - `ResolvedParameterCondition`
   - `WeightFunctionTableFamily`
   - `NominalStressExtractionMode`
   - `resolve_parameter_condition()`

2. `PaperModelParameters` を condition view 経由で組み立てる。
   - `self.specimen_type` / `self.thickness_sign` alias を追加する。
   - `self.type` / `self.T` は旧実装互換名として残す。
   - `build_parameter_snapshot()` は alias を読む。

3. `context.py` のファイル名・Abaqus 入力境界を condition view 優先へ寄せる。
   - `ResolvedModelFiles` は `params.name` / `params.steel` / `params.type`
     の直接参照を減らし、condition view の値を使う。
   - `AbaqusImportInput` へ `nominal_stress_extraction_mode` を渡す。

4. `abaqus.py` の nominal stress 抽出を extraction mode へ分離する。
   - `_extract_smooth_dsload_nominal_stresses()`
   - `_extract_three_point_bending_rf1_nominal_stresses()`
   - `_extract_compact_specimen_dsload_nominal_stresses()`

5. 構造変更後に残る最小ドキュメントだけ更新する。
   - `resources/README.md` の planned 表現を supported 表現へ更新する。
   - README には物理的略号と検証入口への導線だけを短く置く。

6. 最小限の入口ドキュメント
   - コード構造で潰せない `B`, `G`, `N50R` などの物理的略号だけは
     README / resources README に短く残す。
   - 実板厚や supported condition table は、可能ならコード上の条件カタログを
     正本にして、ドキュメントは導線と要約に留める。

### 当面変えないもの

- 追加9条件は固定済み参照 CSV との比較を回帰基準にし、旧実装再実行との
  一致は当面要求しない。
- `SmoothT`, `T25`, `CSS`, `B/G_T50` は今回の10条件対応には含めない。
- `Smooth` の Bainite/Martensite 専用 nominal stress 抽出分岐は、
  現在対象の `B/G/N50R` 条件名と一致しないため追加しない。必要になった時点で
  条件名と入力データの対応を確認してから実装する。
- cache filename に `thickness_sign` は追加しない。条件別 cache root で分離する
  現方針を維持する。

## 旧 Refactoring 文書との関係

## 外部レビュー再評価: 次にコード構造で潰すもの

`docs/parameter_condition_reading_difficulties.md` の現状版では、入口説明、
condition view、Abaqus extraction mode は改善済みになっている。残る主な
読解負荷は、条件解決で作った named decision が、まだ一部の入力準備コードで
使い切られていないことにある。

### 改善済み: weight function table family を material 境界へ渡す

以前:

- `parameters.py` で `WeightFunctionTableFamily` を解決している。
- しかし `material.py` の weight function constants / remote stress constants 選択は、
  まだ `self.input.specimen_type in ["Smooth"]`, `["R008", "R100"]`,
  `["CS", "CSS"]` を直接見ている。

方針:

- `MaterialImportInput` に `weight_function_table_family` を追加する。
- `context.py` から `params.weight_function_table_family` を渡す。
- `material.py` は raw `specimen_type` ではなく family で
  `WFCsmooth` / `WFC3PBT` / `WFCCS` と `CFsmooth` / `CF3PBT` / `CFCS` を選ぶ。
- `specimen_type` は引き続き材料 CSV / cache 名 / microstructure 生成に必要な
  入力ラベルとして残す。

これにより、レビュー項目「weight function 系の選択が `parameters.py` と
`material.py` にまたがる」は、`parameters.py` で決めた family が
`material.py` へ明示的に渡る構造へ改善される。

### 改善済み: 通常計算 config と軽量検証 config の導線分離

以前:

- `verification/configs/conditions/lightweight_*.json` は追加条件名を持つが、
  `sigma_nom=[150]`, `iteration_count=1`, `n_symm=1`,
  `max_active_elements=1` の軽量検証用である。
- 研究者が resources 内の条件を通常計算する入口と誤読しやすい。

現在:

- 通常計算 config は `resources/configs/<condition>.json` に揃えた。
- 軽量 config は `verification/configs/conditions/lightweight_*.json` に残し、
  名前にも lightweight を維持する。
- 通常計算入口は `scripts\Invoke-ConditionResourcesRun.ps1 -ConfigFile resources\configs\<condition>.json` とする。
- `scripts\Invoke-SampleResourcesRun.ps1` は役割を終えたため削除した。
- `resources/sample_simulation.json` は参照用サンプル config として残すが、
  通常計算入口の正本にはしない。

### 優先 3: microstructure の raw 条件分岐は今回すぐ抽象化しない

現状:

- `microstructure.py` は `steel` と `specimen_type` により粒データ生成を分岐する。
- `Bainite`, `Martensite`, `H`, `CS` など、今回10条件外の旧実装分岐も残る。

方針:

- ここは weight function family と違い、生成データの形・乱数消費・材料相の扱いに
  直接触れるため、Readability cleanup の小変更としては扱わない。
- まずは raw 条件分岐が「計算核」ではなく「微視組織入力生成」に残っていることを
  受け入れる。
- 将来触る場合は `MicrostructureGenerationMode` の導入を別 plan に切り出し、
  `N50R_CS_T50` baseline と追加9条件参照 CSV の両方で検証する。

### 優先 4: 低優先の痕跡 cleanup

- `abaqus.py` の `print("type == R008 or R100", ...)` は extraction mode 導入後の
  旧表示なので、意味が伝わる表示に置き換えるか削除する。
- `AbaqusImportInput.specimen_type` は error message と cache filename に必要なため
  当面残す。
- `PaperModelParameters.type` / `T` は旧実装互換 alias として残すが、新規コードでは
  `specimen_type` / `thickness_sign` を使う。

`docs/01_refactoring/` は、単一条件を前提にした整理版実装の履歴として残す。
今後の作業管理は以下を主に使う。

- [incorporate_several_param_plan.md](incorporate_several_param_plan.md)
- [incorporate_several_param_todo.md](incorporate_several_param_todo.md)
- [incorporate_several_param_log.md](incorporate_several_param_log.md)
