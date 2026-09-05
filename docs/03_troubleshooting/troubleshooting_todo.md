# Troubleshooting Todo

完了済みの履歴は必要になった時点で `troubleshooting_log.md` を追加して分離する。このファイルは、現在の異常診断タスクだけを短く管理する。

## Current Focus

`G_R008_T24` 通常条件で発生した NaN と `_solve_stage1_slip_band_length()` の `UnboundLocalError` を、補正せず診断可能な停止へ変える。

## Active Todo

- [x] `crack_life.py` の NaN 発生経路を、Stage I weight function、Stage II weight function、remote stress function、Abaqus field lookup、CTSD root solving に分類する。
- [x] 計算補正を行わない診断例外クラスの置き場所と名前を決める。
- [x] 非有限値検査 helper を追加し、例外メッセージに値名と診断 context を含める。
- [x] `_solve_stage1_slip_band_length()` で `c_root` 未代入を起こさず、根なし状態を明示例外として止める。
- [x] `_calculate_stress_state_at_crack_depth()` で `K`, `sigma_remote`, `Delta_sigma` の非有限値を検出する。
- [x] `_interpolate_stage1_weight_function()` で Stage I weight function 補間結果の非有限値を検出し、`at`, `ac` を出す。
- [x] 追加した診断が正常系の計算結果を変えないことを、軽量検証で確認する。
- [x] 追加診断が既存 baseline CSV との candidate 比較で正常系結果を変えないことを確認する。
- [x] `G_R008_T24` の軽量 config または診断用短縮 config で、追加診断が正常に機能することを確認する。
- [x] 報告された active element `17/20` 付近を通常全実行なしで再現できる局所診断入口を検討する。
- [ ] 通常実行で active element `17/20` に到達するまでの乱数消費順序を再現できる診断入口を検討する。
- [x] データ範囲の直接確認により、Stage I weight function が `ac > 4.0` で NaN を返し、G 材 aspect ratio 分布がその範囲へ到達し得ることを確認する。
- [x] `G_R008_T24` の実 weight function 点群を使った最小再現で、`ac > 4.0` が `CrackLifeDiagnosticError` の `stage1_weight_function` として停止することを確認する。
- [x] Stage I weight function の `at/ac` min/max domain を読み込み時に構築し、`griddata` 前に明らかな範囲外を診断停止する。
- [ ] 報告事象そのものの NaN が Stage I weight function の凸包外補間であることを、通常実行順序を再現した診断例外の停止メッセージで最終確認する。
- [ ] 短縮・局所再現で原因を特定できない場合だけ、通常 `G_R008_T24` 全実行を長時間 troubleshooting ジョブとして実施する。

## Deferred

高速化や結果変更リスクを伴う整理は [../optimization_issues.md](../optimization_issues.md) に集約する。

- NaN を有限値に置き換える補正。
- 補間範囲外での外挿。
- root solving 失敗時の fallback 値導入。
- 失敗 candidate の自動棄却。
- `G_R008_T24` 専用の条件分岐。
- weight function table や Abaqus field の有効範囲を使った自動スクリーニング。まずは NaN 発生源の診断を優先する。

## Needs Researcher Decision

- Stage I weight function の補間範囲外が確認された場合、その候補をモデル適用外とするか、外挿を許すか。
- G 材 aspect ratio 分布が Stage I weight function table の `ac` 範囲を超える候補を生成し得る場合、その候補を論文実装の適用範囲外として扱うか。
- Abaqus field lookup の範囲外が確認された場合、active zone / active element selection を見直すか。
- CTSD root solving に有効な根がない場合、それを unstable fracture とみなすか、候補 invalid とするか、計算停止とするか。
- 追加条件の通常計算で発生する異常を、論文実装の範囲外として扱うか、アルゴリズム拡張対象とするか。

## Verification Rules

- ドキュメントだけの変更では実行検証を省略してよい。
- コードに触れた場合は通常 `.venv\Scripts\python.exe -m compileall src verification`, `scripts\verification\Invoke-StaticAnalysis.ps1`, `scripts\verification\Invoke-ConditionPreflight.ps1`, `scripts\verification\Invoke-SmokeVerification.ps1` を実行する。
- CSV 内容、乱数順序、計算分岐に影響しうる場合は、既存 baseline CSV との candidate 比較を行う。
- `G_R008_T24` 通常条件の全実行は 24 時間以上かかる可能性があるため、通常の検証には含めない。
- `G_R008_T24` 通常条件の全実行は、短縮・局所再現で原因を特定できない場合だけ、明示的な長時間 troubleshooting ジョブとして扱う。
