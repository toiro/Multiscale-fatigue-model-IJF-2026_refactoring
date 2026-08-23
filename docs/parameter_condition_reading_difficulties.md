# `steel` / `specimen_type` / `thickness_sign` の読解上の課題

## 目的

この文書では、初めてこのコードを読む研究者が、シミュレーション条件である `steel` / `specimen_type` / `thickness_sign` の意味と影響範囲を理解しようとしたときに障害となる点を整理する。

対象は、作業記録を読まず、論文、`README.md`、`resources/README.md`、`src/` 以下のコードを手がかりにキャッチアップする場面である。重大度は、条件の物理的意味、入力ファイル対応、計算条件への影響を理解するうえでの阻害度に基づく。

## 重大度 高

現状では、`steel` / `specimen_type` / `thickness_sign` の入口説明、主要な条件解決、通常計算用 config の導線は改善されており、重大度「高」として残る読解上の障害は見当たらない。

README には、`steel` が材料ラベル、`specimen_type` が試験片または荷重形状、`thickness_sign` が論文実装由来の板厚ラベルであることが説明されている。また、実際に使われる寸法、active zone、評価点、cache key、weight-function family、Abaqus nominal stress extraction mode は `parameters.resolve_parameter_condition()` で組み立てられることも示されている。

さらに、`resources/` 内の各条件を通常計算するための config は `resources/configs/` に揃えられ、軽量検証用 config は `verification/configs/conditions/` に分けて置かれている。そのため、前回まで問題だった「どの JSON が通常計算用なのか分かりにくい」という障害も大きく下がっている。

## 重大度 中

### 1. `thickness_sign` と実板厚値の対応はコードを読む必要がある

`thickness_sign` は `parameters.py` の `THICKNESS_BY_SIGN` で実板厚に変換される。

ただし、`T16` は `1.35`、`T24` は `1.9`、`T50` は `4.5` に対応しており、記号からそのまま `1.6 mm`, `2.4 mm`, `5.0 mm` と読めるわけではない。

README は `thickness_sign` が論文実装由来の板厚ラベルであることを説明しているが、具体的な数値対応は `parameters.py` を確認する必要がある。そのため、初見の研究者は、ラベル名と計算に使われる実板厚の関係を一段追って確認することになる。

### 2. `specimen_type` が複数の計算条件を同時に決めている

`specimen_type` は試験片形状の名前であるだけでなく、幅、active zone、active element size、active element 数、`stress_lim`、Stage II 評価点、weight-function family、Abaqus nominal stress extraction mode に影響する。

これらの多くは `resolve_parameter_condition()` からたどれるようになっているが、影響先は `WIDTH_BY_SPECIMEN_TYPE`、`ACTIVE_ZONE_BY_SPECIMEN_TYPE`、`STAGE2_POINTS_BY_CONDITION`、`WEIGHT_FUNCTION_TABLE_FAMILY_BY_SPECIMEN_TYPE`、`NOMINAL_STRESS_EXTRACTION_MODE_BY_SPECIMEN_TYPE` に分かれている。

そのため、`specimen_type` を単なるファイル名用の分類として読むと、計算対象領域、評価点数、応力抽出方法、weight function 系まで変わることを見落としやすい。

### 3. 微視組織生成では `steel` と `specimen_type` の分岐が残っている

`microstructure.py` では、粒データの生成方法に `steel` と `specimen_type` が直接使われている。

特に、現在の supported condition には出てこない `Bainite`、`Martensite`、`H` の分岐が残っており、さらに `specimen_type == "CS"` の場合には粒形状や角度の扱いが他の形状と変わる。

そのため、`steel` / `specimen_type` の影響範囲を計算条件表だけで把握しようとすると、微視組織生成に残る条件依存を見落としやすい。

### 4. 3つのパラメータがファイル名、ディレクトリ名、寸法、評価点、cache に異なる形で効く

`steel` / `specimen_type` / `thickness_sign` は、`specimen_model_name()` で `<steel>_<specimen_type>_<thickness_sign>` という model name になる。この名前は condition directory や `.inp` / `.dat` のファイル名に使われる。

一方で、field cache や grain data cache のファイル名は `<steel>_<specimen_type>_FieldValues.pkl` や `<steel>_<specimen_type>_gData.pkl` であり、`thickness_sign` を含まない。

README にはこの cache 命名規則の説明がある。ただし、材料 CSV は主に `steel` で決まり、寸法や評価点は `specimen_type` / `thickness_sign` / `steel` の組み合わせで決まるため、3つのパラメータの効き方を厳密に把握するには、`paths.py`、`parameters.py`、`context.py`、`material.py`、`microstructure.py` をまたいで読む必要がある。

## 重大度 低

### 5. 新しい config 名と旧実装由来の内部名が併存している

JSON config では `specimen_type` / `thickness_sign` として指定し、`PaperModelParameters` にも同名の属性がある。

一方で、旧実装互換のため `self.type` / `self.T` も同じ値を指す alias として残っている。

現状では新しい名前が主導になっているため大きな障害ではないが、初見では同じ概念に複数の名前があるように見える。

### 6. Abaqus nominal stress 抽出の分岐は mode 化されたが、周辺には旧名の痕跡が残る

Abaqus field cache 生成では、`NominalStressExtractionMode` によって `Smooth`、3点曲げ、compact specimen の nominal stress 抽出経路を選ぶ形に整理されている。

ただし、`AbaqusImportInput` には `specimen_type` も残っており、エラーメッセージや実行時表示には旧来の `type` 表現が残る箇所がある。

そのため、主要な分岐は読みやすくなっているが、周辺の表示や診断文を読むときには旧実装由来の語彙が混じる。

### 7. 条件ディレクトリの自動選択は互換挙動を含んでいる

README には、`--base-dir resources` を使うと一致する condition directory が選ばれることが書かれている。

実際の選択は `resolve_condition_dir()` により、`base_dir / model_name` が存在する場合だけそこへ切り替わり、存在しない場合は `base_dir` 直下を読む。

この互換挙動は legacy 入力ディレクトリ指定を保つために残っている。入力ファイル名そのものに親ディレクトリ fallback は無いが、条件ディレクトリが選ばれるかどうかは `paths.py` と `context.py` を確認する必要がある。

### 8. `steel` が材料条件と計算領域条件の両方に効く

`steel` は材料 CSV、摩擦強度、引張特性などの材料データ選択に使われる。

一方で、`ACTIVE_ZONE_BY_SPECIMEN_TYPE` 内の `stress_lim_by_steel` でも使われ、active element のうち評価対象とする範囲にも影響する。

そのため、`steel` を材料名としてだけ読んでいると、同じ値が探索領域側の条件にも関与していることを見落としやすい。

## 改善済み

### 入口説明と resources の現状追従

README には、`steel` / `specimen_type` / `thickness_sign` の概略と、解決済み条件を `parameters.resolve_parameter_condition()` で確認できることが追記されている。

`resources/README.md` も現在の condition directory 構成に追従しており、以前のように実在ディレクトリが planned 扱いに見える状態ではなくなっている。

### 計算核内の raw `specimen_type` 分岐

以前は `CalculationInputData` の `SpecimenGeometry` に raw `specimen_type` が残り、`crack_life.py` 内で `CS` / `CSS` 判定に使われていた。

現在は入力準備境界で `stage2_weight_function(at, ac)` callable へ変換し、計算核は試験片名でも single / split RBF の持ち方でもなく、Stage II weight function 評価だけを見る。

### Abaqus nominal stress 抽出 mode

以前は Abaqus field cache 生成経路で `specimen_type` を直接見て nominal stress 抽出処理を選ぶ構造だった。

現在は `parameters.py` で `NominalStressExtractionMode` を解決し、`abaqus.py` はその mode によって抽出処理を選ぶ形になっている。

### weight function table family の material 境界渡し

以前は `parameters.py` に `WeightFunctionTableFamily` がある一方で、`material.py` の weight function constants と remote stress constants の選択には raw `specimen_type` 分岐が残っていた。

現在は `parameters.py` で解決した `weight_function_table_family` を `MaterialImportInput` へ渡し、`material.py` はその family で `WFCsmooth` / `WFC3PBT` / `WFCCS` と `CFsmooth` / `CF3PBT` / `CFCS` を選ぶ。

これにより、試験片名そのものではなく、weight function table の family という named decision を材料入力境界で読む形になっている。

### 外部 config の iteration 指定

以前は外部 config に `iterations=[0,1,2,3]` のような旧実装由来の試行番号列が現れていた。

現在は `iteration_count=4` の形になっており、初見の研究者が「なぜ回数ではなく配列なのか」を追う必要は小さくなっている。内部では旧実装互換のため `iteration_num=np.arange(0, iteration_count, 1)` が生成される。

### cache 命名規則と事前確認手順の README 導線

README には、FieldValues と生成微視組織 cache が `steel + specimen_type` ベースの legacy filename rule を使い、`thickness_sign` を含まないことが追記されている。

また、追加条件を重い寿命計算の前に確認するための condition preflight への導線も追加されている。これにより、条件ディレクトリ、必須入力ファイル、軽量 config、context 境界解決の確認手段は以前より見つけやすくなっている。

### 通常計算 config と軽量検証 config の分離

以前は `resources/` 内の各条件を通常計算するための JSON config が揃っておらず、`resources/sample_simulation.json` や `verification/configs/conditions/lightweight_*.json` の位置づけが混ざって見えやすかった。

現在は、通常計算用 config を `resources/configs/<condition>.json` に置き、軽量検証用 config は `verification/configs/conditions/lightweight_<condition>.json` に置く形へ分離している。

`verification.check_resources` でも、10条件分の通常 config が揃っていること、通常 config に `random_seed` や `max_active_elements` が混入していないことを確認する。

これにより、研究者が `resources/` 内の各条件を通常計算として実行する場合は `resources/configs/` を見ればよく、短時間の開発確認では `verification/configs/conditions/` を見る、という役割分担が読み取りやすくなっている。
