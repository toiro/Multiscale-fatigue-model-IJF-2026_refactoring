# G_R008_T24 NaN 発生に関する調査レポート

## 概要

`G_R008_T24` の通常計算で、active element `17/20` 付近において `K` と `sigma_remote` が全成分 `nan` となり、最終的に `_solve_stage1_slip_band_length()` で `UnboundLocalError` が発生したとの報告を受けた。

現時点の調査では、報告事象そのものを乱数順序込みで完全再現できてはいない。ただし、同じ `G_R008_T24` の入力データを用いて、Stage I weight function の補間範囲外で `K` の元となる weight function が全成分 `nan` になることは再現できた。

したがって、報告事象の有力な原因は、`G_R008_T24` の一部 candidate crack が Stage I weight function table `WFC3PBT` の補間可能範囲を超えることである。

研究者側で検討すべき有力な対応は、`WFC3PBT` の Stage I 領域を拡張し、G 材で生成され得る `ac > 4.0` の candidate crack を補間可能範囲に含めることである。ただし、これは weight function table という解析入力データの拡張であり、追加係数の物理的・数値解析的妥当性確認が必要である。

## 推定原因

`G_R008_T24` は `R008` 条件であるため、`CombinedData_Ellipse_WF_CF.json` 内の `WFC3PBT` を使用する。

Stage I の weight function 補間では、`WFC3PBT` のうち `at <= 0.1` の点群を `griddata(method="linear")` に渡している。この点群の範囲は以下であった。

- `at`: `0.001` から `0.1`
- `ac`: `0.25` から `4.0`

一方、G 材の ferrite grain aspect ratio 分布は `_make_cdfr_aspect()` により `sqrt(DF[:,0])` として初期き裂形状に使われる。初期き裂では Stage I の `ac = aii / rt1` が最大で概ね `DF[:,0] = 5.2075` まで到達し得る。

そのため、G 材では低確率ながら `ac > 4.0` の Stage I candidate が生成され得る。実データを用いた直接確認では、`(at, ac) = (0.01, 4.5)` および `(0.01, 5.2)` で Stage I weight function が全成分 `nan` となった。

## 再現可能性

再現できたこと:

- `G_R008_T24` の `WFC3PBT` 実データを用いた最小再現で、`ac > 4.0` の Stage I weight function が `nan` になること。
- `ac = 4.0` では有限値を返し、`ac = 4.5` では範囲外として診断停止すること。

まだ再現できていないこと:

- 報告された active element `17/20` の同一 candidate crack における停止。

通常 config では乱数 seed を指定しない運用であるため、再実行しても同じ乱数列、同じ candidate crack、同じ停止位置を再現する保証はない。局所診断入口で rank 17 / symmetry 1-4 を直接実行したが、そこでは報告事象は再現しなかった。これは通常実行で rank 17 に到達するまでの乱数消費順序を再現していないためと考えられる。

## コード上で行った対応

今回の対応は、計算を補正して継続するものではなく、原因が読める位置で停止するための診断強化である。

- `CrackLifeDiagnosticError` を追加した。
- Stage I / Stage II weight function、K 積分、remote stress、Abaqus field lookup、CTSD root solving の境界で非有限値を検出するようにした。
- `_solve_stage1_slip_band_length()` で、根が見つからなかった場合に `c_root` 未代入による `UnboundLocalError` ではなく、根なし状態を示す診断例外で停止するようにした。
- `CombinedData_Ellipse_WF_CF.json` 読み込み後、Stage I weight function 点群の `at/ac` min/max を構築し、`griddata` 実行前に明らかな範囲外を検出するようにした。
- 明らかな範囲外では `source='stage1_weight_function_domain'` として、`at`, `ac`, `at_min`, `at_max`, `ac_min`, `ac_max` を含むメッセージで停止する。
- min/max 内だが凸包外の場合は、`griddata` 後の非有限値検査で停止する。

正常系への影響確認として、軽量 smoke と既存 baseline CSV を再利用した candidate 比較を実施し、CSV 一致を確認した。

## コード側で意図的に行っていないこと

以下は計算モデルの変更に相当するため、リファクタリング側では実施していない。

- `nan` を 0 や有限値へ置換する。
- `ac` を `4.0` に丸める。
- `griddata` を nearest 補間や外挿へ切り替える。
- 範囲外 candidate crack を自動で棄却して計算を継続する。
- 初期き裂 aspect ratio の乱数サンプリング範囲を制限する。
- `G_R008_T24` 専用の条件分岐を追加する。

## 研究者側で検討できる対応

### 1. WFC3PBT の Stage I 領域を拡張する

現在の `WFC3PBT` Stage I 点群は `ac <= 4.0` までである。G 材の初期き裂候補が `ac ≈ 5.2` まで到達し得ることを許容するなら、少なくとも `ac = 5.2` 付近までを含む weight function 係数を追加生成する必要がある。

`griddata(method="linear")` は外挿しないため、単に最大値の点を1つ追加するだけでは不十分な場合がある。対象となる `(at, ac)` を囲むように点群を整備する必要がある。

### 2. 現在の WFC3PBT の適用範囲をモデル制約として明示する

現在の `WFC3PBT` を正とする場合、Stage I で `ac > 4.0` となる candidate は weight function table の適用範囲外であると扱う必要がある。

この場合、範囲外 candidate をどのように扱うかは研究判断となる。候補を棄却する、計算停止とする、別モデルへ切り替えるなどの選択肢がある。

### 3. 外挿または別補間方式の採用可否を判断する

nearest 補間、RBF 補間、外挿などに切り替えれば `nan` を回避できる可能性はある。しかし、この変更は計算結果を変えるため、論文実装としての妥当性確認が必要である。

### 4. 初期き裂形状生成と weight function table の整合性を確認する

G 材の aspect ratio 分布から生成される初期き裂形状が、`WFC3PBT` の Stage I 補間範囲を超え得る。aspect ratio 分布、初期き裂寸法式、Stage I weight function table の整合性を確認することが望ましい。

## 現時点の結論

`c_root` 未代入はコード上の診断不足であり、診断例外へ置き換えた。

一方、`K` 全成分 `nan` の発生は、Stage I weight function table `WFC3PBT` の補間範囲外に candidate crack が入ることによる可能性が高い。これは単純なリファクタリングミスではなく、入力データとアルゴリズム適用範囲の整合性に関わる問題である。

報告事象そのものとの同一性は、seed 未指定の通常実行では厳密再現が困難である。今後同様の停止が発生した場合は、追加済みの診断例外により `source='stage1_weight_function_domain'` または `source='stage1_weight_function'` が出るかを確認することで、原因を確定できる。
