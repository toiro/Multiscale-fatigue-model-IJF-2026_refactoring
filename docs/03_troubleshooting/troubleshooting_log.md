# Troubleshooting Log

## 2026-09-06: `G_R008_T24` NaN 発生源の一次切り分け

- `CrackLifeDiagnosticError` と非有限値検査 helper を `crack_life.py` に追加した。
- `_solve_stage1_slip_band_length()` の `c_root` 未代入は、根なし状態を示す診断例外へ置き換えた。
- Stage I / Stage II weight function、K 積分、remote stress、Abaqus field lookup の境界に非有限値検査を追加した。
- 診断 helper は CTSD の `sigma_friction_ratio` のような入れ子 list / ndarray を扱えるよう、数値を再帰的に平坦化して検査する形にした。
- 通常 config 全実行は 24 時間以上かかる可能性があるため実施しない方針に変更した。
- `verification/diagnose_element_life.py` と `scripts/verification/Invoke-ElementDiagnosis.ps1` を追加し、rank 指定で単一 active element を診断できる入口を用意した。
- `G_R008_T24` 軽量 config の rank 1 / symmetry 1 は診断入口で完走したため、軽量条件では報告 NaN は再現しなかった。
- `G_R008_T24` の Stage I weight function table は `at <= 0.1` の点群で `ac` 最大が `4.0` だった。
- G 材の ferrite grain aspect ratio 分布は `_make_cdfr_aspect()` により `sqrt(DF[:,0])` として使われるため、初期き裂の Stage I `ac = aii / rt1` は最大で概ね `DF[:,0] = 5.2075` まで到達し得る。
- 分布を 100001 点で評価したところ、`ac > 4.0` になり得る領域は約 `0.57%` だった。
- 実際に `griddata(stage1_points, stage1_values, (0.01, 4.5), method="linear")` と `(0.01, 5.2)` は全成分 `nan` を返した。
- `scripts/verification/Invoke-ElementDiagnosis.ps1 -ConfigFile resources/configs/G_R008_T24.json -AreaElementRank 17` を symmetry 1 から 4 まで実行したが、いずれも完走し、報告事象は再現しなかった。
- これは局所診断入口が rank 17 を直接実行しており、通常実行で rank 17 に到達するまでの乱数消費順序を再現していないためと考えられる。
- `build_context()` を通した最小再現は通常 material / microstructure 準備だけでも重く、15 分でタイムアウトしたため中止した。
- `build_context()` を使わず、`resources/G_R008_T24/CombinedData_Ellipse_WF_CF.json` から `WeightFunctionData` を最小構築して `_interpolate_stage1_weight_function()` を直接呼ぶ再現を行った。
- この最小再現では `ac=4.0` は有限値を返し、`ac=4.5` と `ac=5.2` は `CrackLifeDiagnosticError` として `stage1_weight_function` の非有限値を報告した。
- 診断メッセージには `point_min=[0.001, 0.25]`, `point_max=[0.1, 4.0]` が含まれ、Stage I weight function 点群の範囲外であることが確認できた。
- Stage I weight function 点群の `at/ac` min/max を `MaterialDataImporter` で読み込み時に構築し、`WeightFunctionData` に渡すようにした。
- `_interpolate_stage1_weight_function()` は `griddata` 実行前に min/max domain を確認し、明らかな範囲外では `stage1_weight_function_domain` として診断停止する。
- 最小再現では `ac=4.5` が `griddata` 前に `stage1 weight function query is outside min/max domain` として停止することを確認した。

現時点の見立て:

- 報告された `K: [nan nan nan nan nan nan]` は、Stage I weight function の線形補間点が凸包外に出た場合の挙動と整合する。
- これは `griddata(method="linear")` の仕様と、G 材 aspect ratio 分布が weight function table の `ac` 範囲を超え得ることの組み合わせであり、単純なリファクタリングミスよりもアルゴリズム適用範囲の制約である可能性が高い。
- Stage I weight function の範囲外 NaN は最小再現でき、明らかな min/max domain 外は `griddata` 前に検出できるようになった。一方で、報告事象そのものの active element 17/20 は乱数消費順序込みではまだ再現できていないため、同一事象としての最終確定には通常実行順序を再現する診断が必要である。
