# Optimization Issues

現段階では実施しない高速化、または高速化・リファクタリングに見えても計算結果・乱数順序・診断順序を変えうる整理をここに集約する。

このファイルは実装 todo ではなく、保留理由を忘れないための置き場である。実装に移す場合は、対象 plan / todo に小さな作業単位として戻し、検証方針を決めてから行う。

## 基本方針

- 計算式、乱数呼び出し順序、分岐条件、丸め、CSV 形式を変える可能性がある高速化は通常リファクタリングに混ぜない。
- NaN、補間範囲外、root solving 失敗を補正して計算継続する変更は高速化ではなく、研究者判断を要するアルゴリズム変更として扱う。
- まずは計算結果を変えない定数準備・重複参照削減だけを通常リファクタリング候補にする。
- 対応条件拡張や表現整理に見えるものでも、入力データの意味・cache 前提・微視組織生成に触れる場合はここで保留理由を明示する。

## 保留中の高速化・整理

### Stage I / Stage II weight function 補間の cache 化

`_interpolate_stage1_weight_function()` / `_interpolate_stage2_weight_function()` の結果 cache 化は保留する。

理由:

- 浮動小数を cache key にする必要がある。
- `griddata`, `RBFInterpolator` の返り値 shape や dtype が絡む。
- NaN 発生タイミングや診断順序が変わる可能性がある。

### 複数 `at, ac` の一括 `griddata`

`griddata` は単一点ではなく複数問い合わせ点をまとめて受けられるため、Stage I 評価点を一括補間することは技術的には可能である。

ただし現状では採用しない。

理由:

- 現在は評価点ごとに stress state、CTSD、life integration を行い、途中で `break` する。
- 一括補間にすると、従来は到達しなかった評価点まで先に計算する可能性がある。
- NaN や例外の発生順序が変わる。
- 返り値 shape の扱いを変える必要がある。

### 数値型の正規化

Python scalar、NumPy scalar、ndarray、list、SciPy 補間器返り値の混在を整理する余地はある。

ただし、`float(...)`, `.item()`, `np.asarray(...)`, `list(...)` などは丸め、比較、ブロードキャスト、CSV 出力に影響しうるため、通常の読みやすさ改善としては扱わない。

### `Any` 削減

`crack_life.py` 内部の `Any` を減らすには、上記の数値型正規化が必要になる箇所がある。型注釈だけで安全に具体化できる境界と、実値の型変換を伴う箇所を分ける。

### `S_*` 履歴配列の dataclass 化

`S_Δδ0`, `S_K0`, `S_asp0`, `S_RR0`, `S_σ0`, `S_c0`, `S_cyc0`, `S_σ_op0` などを dataclass にまとめる案は保留する。

理由:

- これらは結果型ではなく、候補き裂の計算途中で更新される履歴配列である。
- `S_cyc0` は近傍点を巻き込んで補正されるため、単純な評価点ごとの履歴ではない。
- dataclass 化すると更新順序が隠れ、論文実装としての読み筋が逆に悪くなる可能性がある。

### `MaterialDataImporter` の残存作業属性一括削除

`MaterialDataImporter` に残る legacy 由来の作業属性名を一括削除する整理は保留する。

理由:

- 公開面は typed view に絞れているが、内部作業属性は入力読み込み、Abaqus cache、weight function、microstructure 生成の順序と結びついている。
- 一括削除は差分が大きく、読みやすさ改善より確認コストが大きい。
- 必要なら生成関数単位で小分けに扱う。

### `print` の logger / callback 化

`print` を logger や progress callback に置き換える案は保留する。

理由:

- この実装では、研究者が実行順を追う手がかりとして標準出力が機能している。
- 応用利用向けの logging 抽象化は、論文実装としては過剰になりやすい。
- 変更する場合も、既定の標準出力を保った最小変更に限る。

### 静的解析 rule の追加拡大

`ruff` は現在 `E9`, `F`, `I` を対象にしている。これ以上の rule 拡大は保留する。

理由:

- スタイル修正が大量に出ると、計算式や旧実装との対応確認がしづらくなる。
- 現段階の主目的は未定義名、未使用 import、import 整列など低リスクな検出に留めること。

### 乱数呼び出しの集約

surface grain sampling、orientation、grain boundary sampling、crack-initiation location の乱数呼び出しをまとめると見通しは良くなるが、乱数順序を変える可能性が高い。

また、`_crack_life_raw()` 冒頭には旧実装の乱数順序を保つために破棄される initial crack aspect sampling がある。これは無駄に見えても削除しない。

### cache 生成・読み込み順序の変更

`FieldValues.pkl` や `gData.pkl` の生成・読み込み順序変更は、実行時間やファイル配置を改善しうる一方、乱数順序や既存 baseline CSV の前提に影響しうる。

cache 再生成を伴う変更は、理由、config、出力先、比較方法を明示したうえで別タスクにする。

### cache filename への `thickness_sign` 追加

FieldValues / gData cache filename に `thickness_sign` を追加する案は保留する。

理由:

- 現在は条件別 `--cache-dir` root で分離する方針になっている。
- filename そのものを変えると既存 cache、baseline CSV、比較スクリプトの前提が変わる。
- `thickness_sign` が生成条件に効くことを確認したうえで別タスクにする。

### 条件表の JSON/YAML 外部化

`SUPPORTED_PARAMETER_CONDITIONS` や寸法・active zone・評価点表を外部 JSON/YAML に移す案は保留する。

理由:

- 今回の目的は論文実装としてコード上で条件の意味を追えること。
- 外部化すると、研究者がコードと設定ファイルを往復する必要が増える。
- 対応条件を頻繁に増やす段階になれば再検討する。

### 今回対象外条件の追加

`T25`, `CSS`, `B/G_T50`, `SmoothT` など、参照コードに痕跡があるが今回の10条件に含めていない条件追加は保留する。

理由:

- 入力ファイル、評価点、Abaqus nominal stress 抽出、weight function、microstructure 生成の前提確認が必要である。
- 条件追加は読みやすさ改善ではなく、対応範囲拡張として別 plan にするべきである。

### Smooth の Bainite/Martensite 専用 nominal stress 抽出分岐

参照コードには Smooth 条件の Bainite/Martensite 専用らしい nominal stress 抽出分岐があるが、現在の `B/G/N50R` 条件名とは直接対応しないため保留する。

理由:

- 条件名と材料相の対応がコードだけでは判断できない。
- 誤って導入すると、Abaqus field cache と nominal stress list の前提を変える。

### Smooth 条件の microstructure model size 推定変更

Smooth 条件の microstructure model size 推定に関わる挙動変更は保留する。

理由:

- 生成される `gData.pkl` の形と乱数消費に関わる。
- 既存参照 CSV の前提が変わる可能性がある。

### microstructure 生成の raw 条件分岐整理

`microstructure.py` に残る `steel` / `specimen_type` 由来の分岐を `MicrostructureGenerationMode` のような named decision へ移す案は保留する。

理由:

- weight function family と違い、生成データの形、相の扱い、乱数消費に直接触れる。
- 実施する場合は `N50R_CS_T50` baseline と追加9条件参照 CSV の両方で検証する必要がある。

### `specimen_type` / `type` / `T` 旧名の完全撤去

`PaperModelParameters.type` / `T` などの旧名 alias を完全に撤去する作業は保留する。

理由:

- 現在は `specimen_type` / `thickness_sign` の readable alias を優先しているが、旧名は旧実装対応の読解・snapshot・出力確認にまだ役立つ。
- 完全撤去は差分が大きく、計算核の単純化より移行確認コストが勝る可能性がある。

### `calculate_crack_life()` と `_crack_life_raw()` の二重構造解消

`calculate_crack_life()` が `_crack_life_raw()` を包む構造を解消する案は保留する。

理由:

- 現在は raw tuple 境界を同じファイル内で `CrackLifeResult` に変換する入口として機能している。
- どちらかを削ると、研究者向けの読み筋と legacy 互換確認のどちらを優先するか判断が必要になる。

## 既に実施済みの低リスク効率化

- `_integrate_k_stage1()` / `_integrate_k_stage2()` で、Gauss 点ごとの field lookup を6成分ループの外に出した。
- closure 計算で同一 candidate crack 内の surface reference principal stress を1回だけ計算するようにした。
- Stage I weight function の `griddata` 用定数点群を入力準備時に一度だけ構築するようにした。
