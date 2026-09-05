# Incorporate Several Parameter Conditions Summary

## 概要

これまで整理版実装は、実質的に `N50R_CS_T50` の単一条件を前提にしていた。
今回の作業では、論文実装由来の複数パラメータ条件を同じ形式で扱えるようにし、
入力ファイル配置、通常実行手順、検証手順、条件ごとの計算設定の見通しを整えた。

対応対象は以下の10条件である。

- `B_Smooth_T16`, `G_Smooth_T16`, `N50R_Smooth_T16`
- `B_R008_T24`, `G_R008_T24`, `N50R_R008_T24`
- `B_R100_T24`, `G_R100_T24`, `N50R_R100_T24`
- `N50R_CS_T50`

## 達成したこと

### 1. 条件ごとの入力リソースを並列に配置できるようにした

入力ファイルは `resources/<condition>/` に条件ごとにまとめる構成へ整理した。
各条件ディレクトリには `.inp`, `.dat` または `.dat.zip`, 材料 CSV,
`CombinedData_Ellipse_WF_CF.json` を置く。

設定 JSON 以外の実行入力は条件ディレクトリ内にまとまるため、
どの条件がどの入力ファイルを使うかをディレクトリ単位で確認できるようになった。

### 2. 通常計算と確認用 config を分離した

通常計算用 config は `resources/configs/<condition>.json` に揃えた。
これらは `.org.py` 由来の通常設定を明示し、`random_seed` や
`max_active_elements` は含めない。

一方、短時間で動作確認するための軽量 config は
`verification/configs/conditions/lightweight_<condition>.json` に残した。

これにより、通常計算に使う設定と、短時間の確認に使う設定を取り違えにくくなった。
通常計算入口は `scripts/Invoke-ConditionResourcesRun.ps1` に揃えている。

### 3. 条件パラメータから決まる内容を追いやすくした

`steel` / `specimen_type` / `thickness_sign` からは、板厚、幅、active zone、
評価点数、Abaqus nominal stress の読み方、weight function の種類などが決まる。

これらの関係を入力準備の段階で解決し、計算本体では試験片名そのものではなく、
計算上の意味を持つ値を見る形へ整理した。これにより、条件名がどの計算設定に
効いているかを追いやすくなった。

### 4. Abaqus nominal stress の読み方を条件ごとに明確にした

`Smooth`, `R008/R100`, `CS` では Abaqus 出力から nominal stress を作る方法が異なる。
整理版実装に不足していた `Smooth` / `R008` / `R100` 向けの読み取り処理は、
`Fatigue-ferrite-pearlite-life-prediction-IJMS-2020` 内の
`L135_U175_S20_R-1.py` の実装をベースに補完した。

現在は、条件ごとに以下の読み方を明示している。

- `smooth_dsload`
- `three_point_bending_rf1`
- `compact_specimen_dsload`

これにより、分岐の意味が「試験片名」ではなく
「Abaqus 入力・出力から nominal stress をどう読むか」として読めるようになった。

### 5. Weight Function 周辺の見通しを改善した

Weight Function の補間方法の違いを入力準備側で吸収し、
計算本体は Stage II weight function の評価だけを見る形に整理した。

また、weight function constants と remote stress constants の選択は、
試験片名を直接見るのではなく、weight function table の種類で行うようにした。

これにより、`Smooth`, `R008/R100`, `CS` がそれぞれどの weight function table family を
使うかを追いやすくなった。

### 6. 軽量な事前確認手順を作った

寿命計算を毎回最後まで回すのは時間がかかるため、重い Abaqus 出力の読み込みや
`gData.pkl` 生成を行わずに、入力配置や設定の整合性を確認できる手順を整備した。

`scripts/verification/Invoke-ConditionPreflight.ps1` では、主に以下を確認する。

- 対応条件表が期待どおりであること
- `resources/` に必要な条件ディレクトリと入力ファイルが揃っていること
- 通常計算 config が10条件分揃っていること
- 通常計算 config に確認用の `random_seed` や `max_active_elements` が混入していないこと
- 軽量 config でも入力ディレクトリや出力先が期待どおり解決されること

### 7. 追加条件の比較基準を用意した

追加9条件については、当面は旧実装再実行との一致を要求せず、
軽量 config で通過した出力を参照 CSV として固定した。

以後は `scripts/verification/Invoke-ConditionReferenceComparison.ps1` により、
現在出力と固定済み参照 CSV の完全一致を確認できる。

既存基準条件 `N50R_CS_T50` については、従来の基準 CSV との一致を確認している。

### 8. 対応条件の範囲を明確にした

今回扱う `steel` / `specimen_type` / `thickness_sign` の組み合わせは、
`SUPPORTED_PARAMETER_CONDITIONS` として明示している。

これにより、今回の実装で扱える条件と、まだ扱わない条件の境界が明確になった。
未対応条件は早い段階で止まるため、入力不足や条件の取り違えに気づきやすい。

一方で、今後対応条件を頻繁に増やす場合には、条件表、通常計算用設定、
入力ファイル検査の更新が重複しやすくなる。その段階では、条件定義の
持ち方を見直し、単一の条件カタログから検証や config を派生させるほうがよい。

## 改善された点

- 対応条件の範囲が明確になり、未対応条件を誤って進めにくくなった。
- 条件ごとの入力ファイルが `resources/<condition>/` にまとまり、入力対応を確認しやすくなった。
- 通常計算 config と軽量確認 config の置き場が分かれ、実行導線が分かりやすくなった。
- `steel` / `specimen_type` / `thickness_sign` がどの計算設定に効くかを追いやすくなった。
- Abaqus nominal stress 抽出や weight function table 選択の意味が読みやすくなった。
- 重い計算を回す前に、条件表・入力配置・config・入出力先の解決を確認できるようになった。
- 追加条件について、CSV 形式確認と参照 CSV 比較による回帰確認の入口ができた。

## 検証状況

主な検証として以下を実施し、通過を確認している。

- `.venv\Scripts\python.exe -m compileall src verification`
- `scripts\verification\Invoke-StaticAnalysis.ps1`
- `scripts\verification\Invoke-ConditionPreflight.ps1`
- `scripts\verification\Invoke-SmokeVerification.ps1`
- `scripts\verification\Invoke-CandidateComparison.ps1`
- `scripts\verification\Invoke-ConditionReferenceComparison.ps1`

また、B/G/N50R の `Smooth`, `R008`, `R100` 条件では、軽量 config による
pkl 生成と CSV 形式確認の通過を確認している。

## 残している判断

以下は今回の10条件対応の範囲外として残している。

- `T25`, `CSS`, `B/G_T50`, `SmoothT` など、今回対象外の条件追加。
- Smooth の Bainite/Martensite 専用 nominal stress 抽出分岐。
- microstructure 生成に残る `steel` / `specimen_type` 由来の条件分岐の整理。
- 条件表の JSON/YAML 外部化。

これらは、今回の目的である「10条件を安全に扱い、計算本体へ条件文脈を過剰に入れない」
こととは別の作業として扱う。
