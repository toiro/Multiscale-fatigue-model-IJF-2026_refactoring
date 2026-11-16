# N50R_CS_T50・135 MPa: 旧実装のCTSD NaN検証

## 結論

旧プログラム `multiscale-fatigue-model/Multiscale_fatigue_model.py` を直接実行し、
**N50R_CS_T50・135 MPaでCTSD NaNの発生を確認した。**
保存入力を旧関数だけで再評価して、同じすべり帯長さとNaNを再現した。
今回の1件は [B_Smooth_T16の報告](../03_troubleshooting/B_Smooth_T16_ctsd_nan_report.md) と同じく、
すべり帯が届いていない粒界をCTSD積分に含め、負の平方根引数を評価する経路だった。
旧コードと整理版の計算核、モデルの式・分岐は変更していない。

## 実行条件と観測範囲

- 実行日: 2026-11-16。最初の実行は日本時間19:40:39〜19:51:20、約641秒。
  入力ハッシュの事後確認・局所再評価はこの計算時間の後にも行った。
- seed42をPython randomとNumPyへ設定。応力135 MPa、1試行、応力上位1要素、対称領域1つ。
- Python 3.12.7、NumPy 1.26.4、SciPy 1.17.1。プロジェクトの `.venv` から実行。
- 旧ディレクトリの既存 `N50R_CS_FieldValues.pkl` / `N50R_CS_gData.pkl` を使用した。
  cacheの元の生成履歴はこの検証では確定していない。使用実体とSHA-256をmanifestに保存した。
- `sys.settrace` により旧コードの `CTSD()` の戻り値を検査した。
  警告の表示や通常CSVからの推定ではなく、非採用候補も含めた実行中の値を対象とした。
- 最初の非有限CTSDで入力を保存して診断停止した。CTSDは595回、`evalCTSD`も595回、
  き裂寿命候補は7回目の呼び出しまで到達した。試行・要素全体は完走させていない。
- 入力、cache、旧ソース、旧ディレクトリの既存CSVの事前・事後ハッシュは一致した。

## 捕捉位置と直接原因

以下の番号は0始まり。

| 項目 | 値 |
| --- | --- |
| 試行 / 要素順位 / 対称領域 | 0 / 0 / 0 |
| 実要素番号 | 4 |
| 粒候補 `Grain_i` / 評価点 `i` | 6 / 3 |
| き裂深さ `a` [mm] | 0.008730086041487034 |
| すべり帯長さ `c` [mm] | 0.03231851609047286 |
| CTSDの引数 `n` / 積分対象粒界数 | 4 / 5 |
| 実際に `c` 以下にある対象粒界数 | 4 |
| 第5粒界位置 `ad` [mm] | 0.032603231193217466 |
| 第5粒界の `c**2 - ad**2` [mm²] | -1.8484201948235513e-05 |

CTSD入力自体は有限だった。第5粒界では `x != ad` のため、`gg()` 内で粒界位置の調整はなく、
`np.sqrt(c**2 - ad**2)` がNaNになった。他の4粒界の幾何積分は有限だった。

粒層更新の `m=3` では、判定対象の `sigma_fr[3] = 0.9294301967` は1未満だが、
新しく計算した `sigma_fr[4] = 1.4800379474` は1を超えていた。
この時点では根探索を行わず、次の `m=4` で `CCn()` を呼び、上記の `c` を得た。
その後の `m=5` で5粒界をCTSDに渡している。

根探索の第5粒界の引数 `ad / (c + 1e-10)` は `1.008809655773384` であり、
`safe_arccos()` のclipで角度項は0になる。方程式残差は約 `1.78e-15` だった。
したがって、根探索では未到達粒界の項が0となる一方、CTSDでは同じ粒界の幾何積分を評価している。
保存した `CCn()` 入力から再計算した根は、捕捉値と完全一致した。

## 実行・再評価方法

リポジトリルートのPowerShellから実行する。

```powershell
# 旧プログラムを実行。最初の非有限CTSDを保存して停止する。
.\scripts\verification\Invoke-LegacyCTSDNaNDiagnosis.ps1

# 保存した最小入力だけを旧関数で再評価。応力場の準備は不要。
.\scripts\verification\Invoke-LegacyCTSDNaNDiagnosis.ps1 `
    -ReplayFile .\verification\fixtures\N50R_CS_T50_legacy_ctsd_nan_seed42.json
```

実行本体は `verification/legacy_ctsd_nan.py`。
`-Seed`、`-Iterations`、`-Symmetries`、`-MaxElements`、`-OutputDir` を指定できる。
応力は135 MPaに固定している。出力先が既存の場合は上書きせず拒否する。
`-MaxElements 0` は旧コード既定の対象要素範囲を意味する。
最初の実行の保存先は
`outputs/troubleshooting/N50R_CS_T50_legacy_ctsd_nan/stage1_seed42/`。

- `capture.json`: 未使用の末尾配列も含む捕捉状態。
- `capture.replay.json`: 捕捉入力を旧関数で再評価した解析結果。
- `manifest.json`: 旧コード、使用入力、cacheのパス・サイズ・SHA-256。
- `summary.json` / `random_state.json`: 実行概要と停止時の乱数状態。
- 同ディレクトリ名の `.log`: 標準出力・標準エラー。

`verification/fixtures/N50R_CS_T50_legacy_ctsd_nan_seed42.json` は、
上記の捕捉から局所評価で未使用の末尾を除いた最小入力である。
完全な捕捉入力と最小入力の両方で、旧関数の根とNaNを再現した。
`.ps1` による再評価の出力先は上記の出力ルート内の `replays/`。

最初の実行は捕捉・停止・入力不変確認までは成功したが、その後の自動再評価で
スカラーと1要素配列が混在する摩擦強度比の復元に失敗し、プロセス終了コードは1となった。
復元処理を修正し、保存入力からの独立した再評価は成功した。
この修正は捕捉した旧計算の値や計算核を変更するものではない。

## 検証記録

- compileall、静的解析、smokeは成功。条件表10条件と、別実行のcontext境界10条件も成功。
- 通常の条件検証スクリプトは、既存の `B_Smooth_T16_report` と `N50R_CS_T50_ctsdnan` を
  通常config一覧が拒否して停止。該当configと検証ツールは今回変更していない。
- 観測ありの完走実行（`comparison_observed_sequential`）は成功。
  約732秒、8候補、806回のCTSD呼び出し。最初の捕捉状態は `stage1_seed42/capture.json` と
  SHA-256も一致した。捕捉後の自動再評価も成功した。
- 出力はsummary/detailの2 CSV。最終寿命は `335256.10371405707` 回。
  採用履歴のき裂深さが記録された154行では、CTSDはすべて有限で欠損もなかった。
  今回は実行中の非採用候補にNaNが存在しても、有限寿命と有限CTSDの履歴が出力される例となった。
- 観測なしの完走実行（`comparison_unobserved_sequential`）も成功。約481秒。
  観測あり／なしの2 CSVは許容誤差0で一致し、ファイルのバイト列・SHA-256も一致した。
  Python／NumPyの終了時乱数状態と入力manifestもバイト単位で一致した。
  両実行で入力・cache・旧ソースの事後ハッシュ一致を確認した。
  比較根拠は出力ルートの `comparison.json` に保存した。
  観測なしのsummaryにある呼び出し回数0は計数を行っていない初期値であり、未評価を意味しない。
- 観測ありの2 CSVの形式検証も成功した（summary 1本、detail 1本）。
  今回は旧コードの観測の影響を調べるために旧実装同士を再実行して比較した。
  整理版の計算核は変更しておらず、旧実装対整理版の追加full baselineは実施していない。
- 比較用2実行の最初の並行起動はメモリ不足を避けて準備中に停止した。
  `comparison_observed` / `comparison_unobserved` は結果比較に使用しない。

完走比較の再実行例（出力先は未作成のディレクトリを指定する）:

```powershell
$base = ".\outputs\troubleshooting\N50R_CS_T50_legacy_ctsd_nan"
.\scripts\verification\Invoke-LegacyCTSDNaNDiagnosis.ps1 `
    -ContinueAfterCapture -OutputDir "$base\recheck_observed"
.\scripts\verification\Invoke-LegacyCTSDNaNDiagnosis.ps1 `
    -NoObserve -OutputDir "$base\recheck_unobserved"
.\.venv\Scripts\python.exe -m verification.compare_csv_outputs `
    "$base\recheck_unobserved\csv" "$base\recheck_observed\csv" --rtol 0 --atol 0
Get-FileHash "$base\recheck_observed\random_state.json", "$base\recheck_unobserved\random_state.json"
```

## 結果の限界

今回の1件で、旧実装のN50R_CS_T50・135 MPaでも同じNaN経路が存在することを確認した。
最初の1件で停止しているので、全候補の発生件数・発生率や最終寿命への影響は確定していない。
要素数・対称領域数を減らした独立したseed固定実行であり、過去のseed未固定実行や、
全要素・全対称領域の後半における乱数履歴を再現したという意味ではない。
粒層の進め方や積分範囲の修正は行っていない。
