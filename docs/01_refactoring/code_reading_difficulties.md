# 論文と `src/` の照合時に残る読解上の困難

## 目的

対象論文は H. Ito らの "Multiscale model prediction of ferritic steel fatigue strength based on microstructural information, tensile properties, and loading conditions (no adjustable material constants)" である。

この文書では、破壊力学の研究者が作業記録を読まず、論文、`README.md`、`src/` 以下のコードを手がかりに研究内容をキャッチアップしようとした場合に、現在のコード状態が原因で生じる困難や不都合を整理する。

解決案や改善希望は含めない。重要度は、論文とコードの対応関係を理解するうえでの阻害度に基づく。

## 現状の全体評価

`README.md` には推奨読解順、実行例、設定ファイル利用方針が書かれている。`src/` 側でも、`CalculationInputData`、論文サブモデルに近い入力 dataclass、`ElementLifeResult`、`LoadCaseResult`、`SimulationResult`、`output.py` の CSV 出力責務分離により、旧スクリプトより計算階層は見えやすくなっている。

一方で、README とコードだけで論文実装を追う場合、論文中の Submodel、入力データ、実行階層、出力列がどのファイル・型・関数に対応するかは、まだ読者が複数ファイルを往復して復元する必要がある。特に `calculation/crack_life.py` の Submodel 3 実装、`field_values.py` の応力場参照、`abaqus.py` の FEM cache 生成、`material.py` の入力資源集約が主要な読解負荷として残っている。

## 重要度 高

### 1. `_crack_life_raw` が Submodel 3 の集中点としてまだ大きい

`_crack_life_raw` は、初期き裂形状、粒界生成、評価点生成、応力状態評価、CTSD 評価、寿命積分、停止条件、貫通時補間を一つの主ループで束ねている。

helper 化は進んでいるが、論文の Submodel 3 を「き裂形状」「粒界」「CTSD」「K 値」「closure」「寿命積分」の物理過程ごとに読む場合、主ループと複数の helper を行き来しながら制御フローを復元する必要がある。

### 2. き裂進展履歴が legacy 配列名を中心に進む

`_initialize_crack_growth_history` により履歴配列の初期化は切り出されているが、計算の中心は `S_Δδ0`, `S_K0`, `S_asp0`, `S_RR0`, `S_σ0`, `S_c0`, `S_cyc0`, `S_σ_op0` である。

コメントで CTSD、K value、aspect ratio、effective stress ratio、slip-band length などの意味は補われている。ただし、論文上の量、単位、評価点インデックス、Stage I/II、停止後に埋められる値の意味を、名前と型だけから確信することは難しい。

### 3. `GrainBoundaryData` は改善だが、粒界モデルの内部構造はまだ復元が必要である

`GrainBoundaryData` により、`friction_strengths`, `boundary_depths`, `grain_counts`, `adjacent_grains`, `boundary_fractions`, `orientations` というまとまりは見えるようになった。

一方で、生成側では `rnList`, `Nd`, `PnList`, `RnAS`, `orList` 由来の構造を包んでおり、CTSD 評価側では再びこれらに相当する配列操作へ戻る。粒界位置、層ごとの粒数、隣接粒、層間の分率、結晶方位が論文の粒界モデル上でどう対応するかは、内部処理を読んで復元する必要がある。

### 4. FEM 応力場 cache の由来を `abaqus.py` で追いにくい

`abaqus.py` の `AbaqusDatabaseCreator` は、`.inp` 読み取り、`.dat` 読み取り、active zone 抽出、弾塑性場の補間関数作成、pickle 保存までをまとめて扱っている。

Submodel 1 の FEM 応力場がどの入力ファイルから、どの座標・要素・nominal stress に対応する形で `field_values.py` へ渡るのかを確認するには、大きな parser 処理を通して読む必要がある。

### 5. 応力場参照の total / elastic / plastic の対応が名前から分かりにくい

`field_values.py` には `FieldValuesA`, `FieldValuesAE`, `FieldValuesAP`, `FData_AE`, `FieldValues_ACTIVE_NumpyE`, `FieldValues_ACTIVE_NumpyP` などの旧実装由来の名前が残っている。

`calculation/` 側では `active_element_total_field_by_depth(...)` や `active_surface_total_field_by_nominal_stress(...)` という意味名 wrapper を呼ぶようになっている。この点は改善している。

一方で、wrapper の内側では旧名の関数群に戻るため、total / elastic / plastic の場の関係、nominal stress との対応、応力範囲への変換箇所を確認するには `field_values.py` 内部の旧名体系を読む必要がある。

## 重要度 中

### 6. README だけでは論文 Submodel とコードの対応表になっていない

README には推奨読解順があるが、論文中の Submodel 1, 2, 3、Section 3 の validation、各入力データ、各出力系列が、`src/` のどのファイル・型・関数に対応するかは明示的な一覧になっていない。

そのため、研究者は論文の節や式からコードへ移るたびに、`parameters.py`, `material.py`, `field_values.py`, `context.py`, `calculation/` 以下を横断して対応を推定する必要がある。

### 7. 入力データの由来と計算入力への変換経路が複数ファイルに分かれる

`CalculationInputData` とその内側の dataclass は、計算核へ渡る値のまとまりを示している。

ただし実際の値は `parameters.py`, `material.py`, `microstructure.py`, `field_values.py`, `context.py` を経て作られる。論文の材料条件、FEA 場、測定微視組織、確率生成微視組織、評価点定義を照合するには、入力定義だけでなく生成経路も追う必要がある。

### 8. `MaterialDataImporter` が複数種類の入力資源をまとめて扱っている

`material.py` の `MaterialDataImporter` は、粒径分布 CSV、単調引張特性、摩擦強度、Abaqus field cache、weight function、生成微視組織データを読み込む。

論文の Submodel 1 と Submodel 2 を分けて照合する場合、FEA 場、材料特性、測定微視組織、生成微視組織が同じ importer の中で現れるため、読者が境界を意識して読む必要がある。

### 9. `PaperModelParameters` が入力条件、導出量、実行条件をまとめて保持している

`PaperModelParameters` は論文実装の条件を集約しているが、材料名、試験片条件、active zone、評価点、モデルスイッチ、Paris 則定数などを可変属性として保持する。

作業記録を読まない研究者にとって、どれが論文の入力条件で、どれがコード内で導出された量で、どれが実行設定に近い値なのかを、`parameters.py` と `context.py` をまたいで確認する必要がある。

### 10. `element_life.py` の結果返却は改善したが、内部履歴変数は legacy 名に残っている

`element_life.py` は `ElementLifeResult` を直接返すようになり、raw tuple の読み替えは不要になった。

ただし内部の候補き裂履歴は `S_yz`, `S_cyc`, `S_ai`, `S_surf`, `S_c`, `S_Δδ`, `S_K`, `S_σ`, `S_RR`, `S_asp`, `S_σ_op`, `RnList` として保持される。area element 内で「表面粒をサンプリングする、候補き裂を評価する、最短寿命を採用する」という論文上の手順と、各履歴変数の意味はまだ読み取りが必要である。

### 11. 候補粒ごとの方位評価なのか、代表方位評価なのか判断しづらい箇所がある

`element_life.py` の候補粒ループでは、すべり面判定に `FoList[0]` が使われる一方、き裂寿命評価には `FoList[Grain_i]` が渡される。

この差が論文上の仮定に対応するものなのか、旧実装由来の挙動なのか、コードだけから判断しづらい。研究者が surface grain sampling と slip-plane selection を照合する際に引っかかる箇所である。

### 12. Stage I / Stage II の切り替え条件が複数箇所に散っている

`EvaluationPointDefinition` には Stage I/II の評価点の説明がある。

一方で、実際の分岐は `_build_evaluation_points`, `_calculate_stress_state_at_crack_depth`, `_integrate_life_cycle`, `_crack_life_raw` にまたがる。論文上の Stage 定義からコード上の制御に直行しにくい。

### 13. 停止条件の意味が複数箇所に分散している

`stop_ctsd_evaluation`, `unstable_fracture`, `stop_life_integration` などの名前は説明的だが、CTSD 評価、寿命積分、主ループ、貫通時補間で停止・打ち切りの意味が分かれている。

物理的不安定、枝刈り、CTSD 閾値未満、through-thickness crack のどれなのかを複数箇所で確認する必要がある。

### 14. unstable fracture 後の履歴埋めの意味を読み取りにくい

`_record_unstable_fracture_history` は unstable fracture 時の履歴更新を切り出している。

ただし、停止後の評価点列をどの値で埋めるのか、CTSD と cycles と slip-band length のどれが物理的な停止状態を表すのかは、関数名だけでは分からない。論文上の不安定破壊処理と照合するには、履歴配列の更新規則を読む必要がある。

### 15. 確率的微視組織モデルの乱数呼び出しが散在している

surface grain sampling、orientation、grain boundary sampling、crack-initiation location は `microstructure.py`, `element_life.py`, `crack_life.py` に分散している。

論文の stochastic microstructure model として読もうとすると、確率分布、サンプリング対象、キャッシュ済み粒データ、実行時の追加乱数の関係を複数箇所で確認する必要がある。

### 16. README とコードだけでは実行階層を図式的に把握しにくい

README には実行コマンドと推奨読解順があるが、nominal stress、iteration、active area element、symmetry position、candidate crack、crack-growth evaluation point の階層関係は文章だけでは把握しにくい。

この階層は `runner.py`, `calculation/load_case.py`, `calculation/element_life.py`, `calculation/crack_life.py` にまたがるため、論文の life prediction procedure と照合するには呼び出し関係を追う必要がある。

### 17. `iterations` が配列である理由が README だけでは分かりにくい

README には既定条件として `iterations=[0,1,2,3]` が示されているが、これが単なる iteration 回数ではなく、旧実装の `iteration_num` に対応する試行番号列であることは明示されていない。

実際には summary CSV では `+1` された `1,2,3,4` として現れ、detail CSV のファイル名では `0,1,2,3` がそのまま使われる。`iterations=4` ではなく配列で指定する理由を理解するには、旧実装、`load_case.py`、`output.py` をまたいで確認する必要がある。

## 重要度 低

### 18. 結果型が計算階層に分散している

結果型は作成元の近くに置かれており、`CrackLifeResult` は `crack_life.py`、`ElementLifeResult` は `element_life.py`、`LoadCaseResult` と `IterationResult` は `load_case.py`、`SimulationResult` は `runner.py` にある。

この配置は計算の階層とは合っている。一方で、研究者が出力系列全体を一覧したい場合には、複数ファイルを確認する必要がある。

### 19. 結果データの型が研究上の量を十分に説明していない

`CrackLifeResult` や `ElementLifeResult` は `list[Any]` を多く含んでいる。

各リストの単位、評価点との対応、Stage I/II との対応、CSV 列との関係は一部 docstring で補われているが、型情報からは分からない。

### 20. CSV 列と計算中の履歴配列の対応は `output.py` まで追う必要がある

`output.py` は legacy fallback がなくなり、CSV 書き出しに集中している。

一方で、論文上の量、計算中の `S_*` 履歴配列、`CrackLifeResult` / `ElementLifeResult`、CSV 列名の対応は複数ファイルをまたぐ。計算結果を論文の図表や出力 CSV と照合する際には追加の読み替えが必要である。

### 21. JSON config の期待項目は README だけでは限定的にしか分からない

README には設定ファイルを使う方針と実行例がある。

ただし、material、seed、stress、iteration、cache、output などの実行条件がどのキーとして読まれ、どこで `PaperModelParameters` に反映されるかは、`config.py`, `cli.py`, `context.py` を読む必要がある。

### 22. `print` と warning 抑制が計算核周辺に残っている

`print` は実行順を追う手がかりになる一方で、計算ロジック中に進行表示が混在している。

また、`RuntimeWarning` などの抑制が複数モジュールに残っている。多項式近似、補間、開口応力、CTSD 計算を論文と照合する際、数値的に不安定な箇所が表に出にくい。

## 方向性の評価

現状の整理は、計算結果を変えずに論文実装として読みやすくするという方向に概ね合っている。

`README.md` の読解順、`CalculationInputData` の直接受け渡し、論文サブモデルに近い入力 dataclass、`microstructure.py` の分離、`GrainBoundaryData`、履歴更新 helper、`ElementLifeResult` の直接返却、結果型の計算階層への配置、`output.py` の出力責務への集中、`config.py` / `cli.py` の設定ファイル中心化は、研究者が `src/` だけから計算手順へ入る助けになっている。

ただし、現在残る主要な困難は、論文とコードをつなぐ地図が README だけでは不足していることと、`crack_life.py` の Submodel 3 実装に読解負荷が集中していることである。特に `S_*` 配列、粒界データの内部構造、Stage/停止条件の分散、応力場 cache の由来、iteration 番号列と出力名の対応、結果系列と CSV 列の対応が、論文の物理モデルとコードの対応を確認する際の中心的な障害になっている。
