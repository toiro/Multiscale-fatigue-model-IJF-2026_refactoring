# Troubleshooting Plan

## 目的

追加の `B_Smooth_T16` / 135 MPa の CTSD NaN 調査は
[B_Smooth_T16_ctsd_nan_report.md](B_Smooth_T16_ctsd_nan_report.md) に記録する。
この事象では、保存した CTSD 入力を局所再評価し、計算式や分岐の修正とは分けて原因を確認する。

通常条件の動作確認で発生した計算停止を、計算結果を補正せずに診断可能な形へ整理する。

対象の初期事象:

- 条件: `G_R008_T24`
- 通常 config: `resources/configs/G_R008_T24.json`
- 停止位置: active element `17/20` 付近
- 直前ログ: `sigma_remote` と `K` が全成分 `nan`
- 例外: `_solve_stage1_slip_band_length()` の `c_root` 未代入による `UnboundLocalError`

ここでの目的は、計算を継続させることではない。NaN、補間範囲外、根なし状態を早期に検出し、研究者がアルゴリズム上の妥当性を判断できる情報を返すことである。

## 基本方針

- NaN を 0 や有限値に置き換えない。
- 補間範囲外で外挿しない。
- root solving 失敗時に新しい fallback 値を導入しない。
- 失敗した crack candidate を自動棄却して計算を継続しない。
- 条件固有の例外処理は入れない。
- 旧実装由来の挙動と異なる補正は、研究者判断後の別タスクとする。
- 通常 `G_R008_T24` config の全実行は 24 時間以上かかる可能性があるため、原因特定の初手にはしない。
- まず軽量条件、既存 cache、短縮 config、局所再現入口を使い、NaN の最初の発生境界を特定する。
- 通常 config 全実行は、短縮・局所再現で原因を特定できない場合だけ、明示的な長時間 troubleshooting ジョブとして扱う。

## 診断対象

### NaN / 非有限値の検出

計算が壊れた地点を明確にするため、以下の境界で非有限値を検出する。

- `_integrate_k_stage1()` / `_integrate_k_stage2()` の `K`
- `_calculate_stress_state_at_crack_depth()` の `sigma_remote`, `Delta_sigma`
- `_evaluate_ctsd_at_crack_depth()` に入る `Delta_sigma`
- `_solve_stage1_slip_band_length()` に入る `a`, `sigma_friction_ratio`, `first_boundary_depth`
- `_solve_multilayer_slip_band_length()` に入る `sigma_friction_ratio`, `boundary_depths`

### 解析有効範囲の逸脱検出

NaN の発生源を特定するため、補間入力が解析データの有効範囲外に出ていないかを確認する。

- Stage I weight function: `at = aii / thickness`, `ac = aii / rt1`
- Stage II weight function: `at`, `asp`
- remote stress function: `aii / thickness`, `asp`
- Abaqus field lookup: `x`, `y`, `z`

`griddata(method="linear")` は凸包外で `nan` を返すため、単純な min/max 範囲内でも安全とは限らない。まずは NaN を検出し、診断値を出すところから始める。

## 現時点の一次見立て

`G_R008_T24` の Stage I weight function table は `at <= 0.1` の線形補間点群で `ac` 最大が `4.0` である。一方、G 材の ferrite grain aspect ratio 分布は `_make_cdfr_aspect()` で `sqrt(DF[:,0])` として使われ、初期き裂の Stage I `ac = aii / rt1` は最大で概ね `DF[:,0] = 5.2075` まで到達し得る。

実データ点群に対して `griddata(method="linear")` を直接確認すると、`(at, ac) = (0.01, 4.5)` や `(0.01, 5.2)` では全成分 `nan` を返す。このため、報告された `K` 全成分 `nan` は Stage I weight function の凸包外補間と整合する。

現在の診断実装では、Stage I weight function 点群の `at/ac` min/max を読み込み時に構築し、`griddata` 実行前に明らかな範囲外を `stage1_weight_function_domain` として停止する。min/max 内だが凸包外のケースは、`griddata` 後の非有限値検査で停止する。

したがって現段階では、単純なリファクタリングミスよりも、G 材の一部 candidate が weight function table の適用範囲を超えるというアルゴリズム制約の可能性が高い。ただし、報告された active element `17/20` そのものを診断例外で再現するまでは最終確定とはしない。

## 例外設計

`UnboundLocalError` のような実装都合の例外ではなく、計算診断として読める例外へ置き換える。

例外メッセージに含めたい情報:

- condition / config file 由来の model name
- load index / nominal stress
- iteration index
- active element rank と total
- symmetry index
- candidate crack location: `y`, `z`
- evaluation index
- crack depth: `aii`
- initial crack dimensions: `r1`, `rt1`
- crack aspect: `asp`, `at`, `ac`
- stress state branch
- NaN が検出された値の名前

ただし、最初の実装では関数境界で自然に渡っている情報だけを使い、診断情報のために過剰な context object を計算核へ流し込まない。

## 実装方針

1. 小さな診断例外クラスを追加する。
2. 非有限値検査 helper を追加する。
3. `_solve_stage1_slip_band_length()` の `c_root` 未代入を、根なしを説明する例外へ置き換える。
4. `_calculate_stress_state_at_crack_depth()` で、`K`, `sigma_remote`, `Delta_sigma` の非有限値を検出する。
5. `_interpolate_stage1_weight_function()` で、weight function 補間が `nan` を返した場合に `at`, `ac` と一緒に止める。
6. 必要に応じて Stage II weight function / remote stress function / field lookup の診断を追加する。
7. 通常全実行ではなく、まず `G_R008_T24` の軽量 config または診断用短縮 config で追加診断が正常に機能することを確認する。
8. 報告された active element `17/20` 付近を直接再現できる小さな診断入口を検討する。
9. 短縮・局所再現で再現できない場合に限り、通常 `G_R008_T24` 全実行を長時間ジョブとして実施する。

## 検証方針

- 計算結果を変えない正常系変更であることを確認する。
- 1タスク完了ごとは通常:
  - `.venv\Scripts\python.exe -m compileall src verification`
  - `scripts\verification\Invoke-StaticAnalysis.ps1`
  - `scripts\verification\Invoke-ConditionPreflight.ps1`
  - `scripts\verification\Invoke-SmokeVerification.ps1`
- `N50R_CS_T50` の計算経路に影響する場合:
  - `scripts\verification\Invoke-CandidateComparison.ps1`
- `G_R008_T24` 通常条件の全実行は 24 時間以上かかる可能性があるため、通常の検証には含めない。
- `G_R008_T24` の原因特定では、まず短縮・局所再現を使い、通常全実行は明示的な長時間 troubleshooting ジョブとしてだけ実施する。
- 長時間ジョブを実行した場合は、条件、出力先、cache 前提、開始時刻、停止位置、診断メッセージを記録する。

## 成功条件

- `G_R008_T24` の異常停止が `UnboundLocalError` ではなく、意味のある診断例外として報告される。
- NaN が weight function、remote stress function、Abaqus field lookup、CTSD root solving のどこで発生したか切り分けられる。
- 正常に通っていた条件の計算結果を変更しない。
- 補正・外挿・候補棄却などの研究判断をコード側で勝手に行わない。
