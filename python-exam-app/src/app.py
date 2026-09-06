"""
app.py
------
Streamlitで動く「繰り返し解く！ Python3 エンジニア認定基礎試験 公式比率準拠
Webテスト400問」のメイン画面です。

このファイルは大きく5つの「画面(screen)」を、st.session_state["screen"] の
値によって切り替える作りになっています。
    "select"         : 学習モードを選ぶ画面（トップ画面）
    "chapter_select" : 章指定モードで、出題する章を選ぶ画面
    "quiz"           : 実際に問題を解く画面
    "result"         : 採点結果を表示する画面
    "review"         : 全問の解説を見る画面（総復習リスト）

Streamlitは「ボタンが押される」などの操作のたびに、このファイルの中身が
上から下まで丸ごと再実行される、という特徴があります。そのため、
「今どの画面を表示しているか」「今何問目か」といった情報は
st.session_state（ブラウザのタブごとに保持される辞書のようなもの）に
保存しておく必要があります。

このアプリはスマホでの利用を主に想定しているため、Streamlit標準の見た目に
加えて、CSS（見た目を調整するための言語）をコードの中に埋め込み、
ボタンを大きく・タップしやすくするなどの調整を行っています。
"""

# re: 問題文の中から ```python ... ``` の部分を検索するための正規表現ライブラリです。
import re
# time: タイマー（経過時間・残り時間）を計算するために、現在時刻を取得するライブラリです。
import time
# Path: OSの違い(Windows/Mac/Linux)を気にせずファイルパスを組み立てられる標準ライブラリです。
from pathlib import Path

# streamlit: このWebアプリの画面(UI)を作るためのライブラリです。
# 「as st」と書くことで、以降は streamlit ではなく st という短い名前で呼び出せます。
import streamlit as st

# 同じsrcフォルダ内にある自作モジュールを読み込みます。
import quiz_engine
import utils

# ── 定数 ──────────────────────────────────────────────
# 認証に使う合言葉。実運用では外部に漏れないよう管理する必要がありますが、
# Phase 1では要件通りシンプルな固定文字列にしています。
PASSPHRASE = "python2026"

# 問題データ(JSON)のファイルパス。
# __file__ は「このapp.pyファイル自身のパス」を表すので、そこから
# 一つ上の階層(src -> プロジェクト直下)に上がり、data/questions.jsonを指します。
# .resolve() は相対パスを絶対パスに変換し、.parent は「1つ上のフォルダ」を表します。
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.json"

# アプリの正式名称（認証画面・トップ画面で3行に分けて表示します）。
APP_TITLE_LINES = [
    "繰り返し解く！",
    "Python3 エンジニア認定基礎試験",
    "公式比率準拠 Webテスト400問",
]
# 問題を解いている最中など、画面のスペースを節約したい場面で使う略式名称です。
APP_TITLE_SHORT = "Python3 基礎試験400"

# 画面上に表示する、モードごとの日本語ラベルをまとめた辞書です。
# キー(quiz_engine.MODE_EXAMなど)から、表示用の文字列を引けるようにしています。
# このラベル文字列は、そのままモード選択ボタンの表示テキストとして使われます。
MODE_LABELS = {
    quiz_engine.MODE_EXAM: "① 本番想定モード\n40問・60分カウントダウン",
    quiz_engine.MODE_SHORT: "② 短時間モード\n10問・カウントアップ",
    quiz_engine.MODE_CHAPTER: "③ 章指定モード\n指定した章から10問",
    quiz_engine.MODE_RETRY: "④ 間違い再挑戦\n前回間違えた問題のみ",
}

# 章指定モードの「章選択画面」に表示する、各章の簡単な説明文です。
# キーは quiz_engine 側のデータと合わせて2桁の文字列("01"など)にしています。
CHAPTER_DESCRIPTIONS = {
    "01": "Pythonの特徴・対話モードの基本操作",
    "02": "インタープリタの起動・終了とコマンドラインオプション",
    "03": "数値・文字列・リストの基礎、簡単な繰り返し処理",
    "04": "制御構文（if・for・match）と関数の定義",
    "05": "データ構造（リスト操作・タプル・集合・辞書・内包表記）",
    "06": "モジュールとパッケージ",
    "07": "文字列フォーマットとファイル入出力",
    "08": "エラーと例外処理",
    "09": "クラスとオブジェクト指向プログラミング",
    "10": "標準ライブラリ概観（前編）：ファイル操作・正規表現・テストなど",
    "11": "標準ライブラリ概観（後編）：便利なツール集",
    "12": "仮想環境とパッケージ管理（venv・pip）",
    "13": "（出題範囲外）",
    "14": "対話型インタープリタの便利な使い方（補完・ヒストリなど）",
}
# 出題範囲外のため、章選択画面でボタンを押せないようにする章番号です。
EXCLUDED_CHAPTER_FOR_UI = "13"

# 選択肢の頭に付ける「A, B, C, D」の丸文字（Unicodeの丸囲み文字）です。
# 普通のアルファベット "A" ではなく "Ⓐ" を使うことで、
# HTMLを使わなくても選択肢がバッジ（円形のラベル）のように見えるようにしています。
CHOICE_LETTERS = ["Ⓐ", "Ⓑ", "Ⓒ", "Ⓓ"]


# ── 見た目(CSS)の設定 ───────────────────────────────────
def inject_global_css() -> None:
    """
    アプリ全体で使う見た目調整用のCSSを、まとめてページに埋め込みます。

    st.markdown(..., unsafe_allow_html=True) を使うと、Streamlitの部品だけでは
    できない細かい見た目の調整（文字サイズを画面幅に応じて変える、ボタンの角を
    丸くする、など）をCSSで行うことができます。

    ポイント：st.container(key="任意の名前") のように key を指定すると、
    そのコンテナを囲むdiv要素に "st-key-任意の名前" というCSSクラスが
    自動的に付きます。これを利用して、「この部分のボタンだけ」に
    スタイルを適用する、といった細かい指定を行っています。
    """
    st.markdown(
        """
        <style>
        /* ボタン全体を、スマホでタップしやすい見た目に調整します
           （角を丸く、文字を少し大きく、上下に余裕を持たせる）。 */
        div[data-testid="stButton"] > button {
            border-radius: 14px;
            padding: 0.7em 1em;
            font-size: 1.02rem;
            min-height: 2.6em;
        }

        /* --- アプリ名（フルネーム・3行表示） --- */
        .app-title-full {
            text-align: center;
            margin: 0.2rem 0 0.8rem 0;
            line-height: 1.35;
        }
        .app-title-full div {
            font-weight: 700;
            color: #1f2937;
            white-space: nowrap;
            /* clamp(最小, 基準, 最大) を使うと、画面幅(vw)に応じて
               文字サイズが自動で変わります。画面が狭いスマホでも
               1行の途中で折り返さないようにするための調整です。 */
            font-size: clamp(11px, 4vw, 17px);
        }

        /* --- アプリ名（略式・1行表示） --- */
        .app-title-short {
            text-align: center;
            font-weight: 700;
            font-size: 1.15rem;
            color: #1f2937;
            margin: 0.2rem 0 0.6rem 0;
        }

        /* --- 問題文と選択肢の間の区切り線 --- */
        .question-divider {
            border: none;
            border-top: 1px solid #d9d9d9;
            margin: 1rem 0 1.1rem 0;
        }

        /* --- モード選択ボタン／中央揃えの単独ボタン共通 ---
           幅を最大420px（かつ画面幅の92%まで）に制限してから
           左右の余白を自動(auto)にすることで、中央揃えかつ
           横幅の揃ったボタンにしています。 */
        [class*="st-key-mode_btn_"],
        [class*="st-key-center_wrap_"] {
            max-width: min(92vw, 420px);
            margin: 0 auto 0.9rem auto;
        }

        /* --- 章選択ボタン（説明文があるので少し高さを持たせる） --- */
        [class*="st-key-chapter_btn_"] div[data-testid="stButton"] > button {
            text-align: left;
            white-space: normal;
            line-height: 1.4;
        }
        [class*="st-key-chapter_btn_"] {
            margin-bottom: 0.7rem;
        }

        /* --- 選択肢カード（A/B/C/D） --- */
        .st-key-choice_area div[data-testid="stButton"] {
            margin-bottom: 1em;
        }
        .st-key-choice_area div[data-testid="stButton"] > button {
            border-radius: 16px;
            text-align: left;
            white-space: normal;
            line-height: 1.55;
            padding: 0.9em 1.1em;
        }

        /* --- 問題画面の「途中終了／次へ」ボタンを左右に離す --- */
        .st-key-quiz_exit_wrap {
            display: flex;
            justify-content: flex-start;
        }
        .st-key-quiz_next_wrap {
            display: flex;
            justify-content: flex-end;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_full_title() -> None:
    """アプリの正式名称を3行に分けて中央に表示します（認証画面・トップ画面用）。"""
    lines_html = "".join(f"<div>{line}</div>" for line in APP_TITLE_LINES)
    st.markdown(f'<div class="app-title-full">{lines_html}</div>', unsafe_allow_html=True)


def render_short_title() -> None:
    """アプリの略式名称を1行で中央に表示します（問題画面など、省スペースが必要な場面用）。"""
    st.markdown(f'<div class="app-title-short">{APP_TITLE_SHORT}</div>', unsafe_allow_html=True)


def centered_button(label: str, key: str, **kwargs) -> bool:
    """
    中央揃え・幅を統一したボタンを1つ表示するための共通部品(ヘルパー関数)です。

    st.container(key=f"center_wrap_{key}") でボタンを囲むことで、
    その部分だけに「st-key-center_wrap_◯◯」というCSSクラスが付き、
    inject_global_css() で定義した中央揃えのスタイルが適用されます。

    戻り値は st.button() と同じで、ボタンが押された直後の再実行時だけ True になります。
    """
    with st.container(key=f"center_wrap_{key}"):
        return st.button(label, key=key, **kwargs)


@st.cache_data
def get_all_questions() -> list[dict]:
    """
    問題データを読み込みます。
    @st.cache_data を付けておくと、Streamlitがボタン操作のたびに
    このファイルを再実行しても、JSONの読み込み処理は最初の1回だけになり、
    動作が軽くなります。
    """
    # Path型のDATA_PATHを、load_questions関数が受け取れるstr型に変換して渡します。
    return quiz_engine.load_questions(str(DATA_PATH))


def format_seconds(total_seconds: float) -> str:
    """秒数を「分:秒」の見やすい形式（例: 03:07）に変換します。"""
    # 残り時間の計算結果がマイナスになることがあるため、max(0, ...)で0未満にならないようにします。
    # int()で小数点以下を切り捨てて整数にしています。
    total_seconds = max(0, int(total_seconds))
    # divmod(a, b) は「aをbで割った商とあまり」を同時に求める関数です。
    # 例: divmod(125, 60) -> (2, 5) となり、125秒は「2分5秒」だと分かります。
    minutes, seconds = divmod(total_seconds, 60)
    # f"{値:02d}" は「整数を2桁になるようゼロ埋めして文字列にする」書き方です（f文字列のフォーマット指定）。
    # 例: 5 -> "05"、12 -> "12"。これにより "03:07" のような表示になります。
    return f"{minutes:02d}:{seconds:02d}"


def render_question_body(question_text: str) -> None:
    """
    問題文を画面に表示します。
    問題文の中に ```python ... ``` という形式のコードが含まれている場合は、
    地の文とコード部分を分けて、コード部分は st.code() でハイライト表示します。
    """
    # re.search(パターン, 対象文字列, フラグ) で、問題文の中から
    # ```python ... ``` の部分を探します。
    # ・(.*?) は「できるだけ短く」何か文字列にマッチする、という意味(非貪欲マッチ)。
    # ・re.DOTALL を付けると、コードが複数行になっていても「.」が改行文字にもマッチします。
    match = re.search(r"```python\n(.*?)\n```", question_text, re.DOTALL)

    if match:
        # マッチした場合: コードブロックより前の部分(地の文)と、コードの中身を分けて表示します。
        # match.start() は「マッチした部分が始まる位置」なので、それより前がプレーンな問題文です。
        # .strip() で前後の余分な空白・改行を取り除いています。
        prose = question_text[: match.start()].strip()
        # match.group(1) は、パターン中の (.*?) で囲んだ部分（=コードの中身だけ）を取り出します。
        code = match.group(1)
        st.write(prose)
        # st.code() を使うと、黒背景でPythonのシンタックスハイライト付きのコード表示になります。
        st.code(code, language="python")
    else:
        # コードブロックが無い問題文は、そのまま普通の文章として表示します。
        st.write(question_text)


# ── 認証まわり ──────────────────────────────────────────
def render_auth_screen() -> None:
    """
    URLに user パラメータが無い（＝まだ認証していない）ときに表示する画面です。
    名前と合言葉を入力してもらい、合言葉が正しければ名前をBase64で難読化して
    URLパラメータに付け加え、認証済みの状態にします。
    """
    render_full_title()
    st.subheader("受講者認証")
    st.write("お名前と合言葉を入力してください。")

    # st.form() を使うと、フォーム内の入力欄をまとめて扱えます。
    # 「with st.form(...) as ブロック」の中に置いた入力欄は、
    # フォーム内の送信ボタン(form_submit_button)が押されたときに、
    # まとめて値が確定する仕組みになっています（入力するたびに画面全体が再実行されるのを防げます）。
    with st.form("auth_form"):
        name = st.text_input("お名前")
        # type="password" にすると、入力内容が「●●●」のように隠されて表示されます。
        passphrase = st.text_input("合言葉", type="password")
        # フォーム専用の送信ボタン。これが押されたときだけ True が返ります。
        submitted = st.form_submit_button("認証する")

    # フォームが送信された(ボタンが押された)ときだけ、以下の判定処理を行います。
    if submitted:
        # name.strip() で前後の空白を除いたうえで、空文字列(未入力)かどうかを判定します。
        if not name.strip():
            st.error("お名前を入力してください。")
        elif passphrase != PASSPHRASE:
            st.error("合言葉が正しくありません。")
        else:
            # 認証成功。名前をBase64で難読化してURLに載せ、再描画する。
            encoded = utils.encode_name(name.strip())
            # st.query_params は、ブラウザのURLの「?user=...」の部分を辞書のように読み書きできる機能です。
            # ここで値をセットすると、実際にブラウザのURLにパラメータが追加されます。
            st.query_params["user"] = encoded
            # st.rerun() を呼ぶと、app.pyの処理を最初からもう一度実行し直します。
            # これにより、次の実行では st.query_params["user"] が設定された状態からスタートします。
            st.rerun()


def get_authenticated_name() -> str | None:
    """
    URLパラメータから user を取り出し、デコードした名前を返します。
    パラメータが無い場合や、デコードに失敗した場合は None を返します。
    """
    # st.query_params.get("user") は、URLに ?user=... が無ければ None を返します
    # （辞書のget()と同じ考え方で、キーが存在しないときにエラーにならないのが利点です）。
    encoded = st.query_params.get("user")
    if encoded is None:
        return None
    # utils.decode_name() は、デコードに失敗した場合も例外を出さずNoneを返す設計になっています。
    return utils.decode_name(encoded)


# ── モード選択画面(トップ画面) ───────────────────────────────
def start_quiz(all_questions: list[dict], mode: str, chapter: str | None) -> None:
    """
    選ばれたモードに応じて問題を抽出し、session_stateを初期化して
    「quiz」画面に遷移するための下準備をします。
    """
    # 間違い再挑戦モードのときだけ、前回の不正解idリストをsession_stateから取り出します。
    # それ以外のモードでは None のままにしておき、quiz_engine側で無視されます。
    # 「A if 条件 else B」は「条件がTrueならA、そうでなければB」という1行で書ける条件分岐です。
    wrong_ids = st.session_state.get("last_wrong_ids") if mode == quiz_engine.MODE_RETRY else None

    # ここまでの入力(モード・章・前回の間違いid)を元に、実際に出題する問題一覧を作ってもらいます。
    # 頭脳部分(ロジック)はすべてquiz_engine.py側に任せている点がポイントです。
    quiz_items = quiz_engine.select_quiz_questions(
        all_questions, mode, chapter=chapter, wrong_ids=wrong_ids
    )

    # 万が一、出題できる問題が0件だった場合(章に問題が無い等)はエラーメッセージを出して処理を中断します。
    if not quiz_items:
        st.error("出題できる問題がありませんでした。モードや章の選択を見直してください。")
        return

    # ここから、出題を開始するために必要な情報をすべてsession_stateに保存していきます。
    # session_stateはブラウザのタブごとに保持される「状態を覚えておく場所」で、
    # 辞書と同じように [キー] = 値 で読み書きできます。
    st.session_state["quiz_items"] = quiz_items      # 出題される問題一覧(選択肢つき)
    st.session_state["current_index"] = 0             # 今何問目を表示しているか(0始まり)
    st.session_state["user_answers"] = {}              # { 問題id: 選んだ選択肢の番号 }
    st.session_state["start_time"] = time.time()       # タイマー計算の基準となる開始時刻
    st.session_state["mode"] = mode                    # 今回選ばれた学習モード
    st.session_state["screen"] = "quiz"                 # 表示する画面を「出題画面」に切り替える
    # 画面を「quiz」に切り替えたことを反映させるため、再実行します。
    st.rerun()


def render_select_screen(all_questions: list[dict]) -> None:
    """
    トップ画面(モード選択画面)です。
    4つの学習モードがそれぞれ大きなボタンになっており、タップするとそのまま
    出題が始まります（③章指定モードだけは、先に章を選ぶ画面に移動します）。
    """
    st.subheader("学習モードを選んでください")

    # session_state.get("last_wrong_ids") は、まだ一度もテストを終えていない場合は None になります。
    # 「or set()」を付けることで、Noneのときは代わりに空の集合を使うようにしています。
    last_wrong_ids = st.session_state.get("last_wrong_ids") or set()
    # 前回間違えた問題が無い場合は、④間違い再挑戦モードのボタンを押せなくします。
    retry_disabled = not last_wrong_ids

    # ① 本番想定モード：タップした瞬間にそのまま40問の出題が始まります。
    with st.container(key="mode_btn_exam"):
        if st.button(MODE_LABELS[quiz_engine.MODE_EXAM], key="mode_exam_button", type="primary"):
            start_quiz(all_questions, quiz_engine.MODE_EXAM, chapter=None)

    # ② 短時間モード：タップした瞬間にそのまま10問の出題が始まります。
    with st.container(key="mode_btn_short"):
        if st.button(MODE_LABELS[quiz_engine.MODE_SHORT], key="mode_short_button", type="primary"):
            start_quiz(all_questions, quiz_engine.MODE_SHORT, chapter=None)

    # ③ 章指定モード：出題する章を選んでもらう必要があるため、
    #    まずは「章選択画面」に切り替えるだけにします。
    with st.container(key="mode_btn_chapter"):
        if st.button(MODE_LABELS[quiz_engine.MODE_CHAPTER], key="mode_chapter_button", type="primary"):
            st.session_state["screen"] = "chapter_select"
            st.rerun()

    # ④ 間違い再挑戦モード：前回間違えた問題が無いときはボタンを無効化します。
    with st.container(key="mode_btn_retry"):
        if st.button(
            MODE_LABELS[quiz_engine.MODE_RETRY],
            key="mode_retry_button",
            type="primary",
            disabled=retry_disabled,
        ):
            start_quiz(all_questions, quiz_engine.MODE_RETRY, chapter=None)

    if retry_disabled:
        st.caption("④間違い再挑戦：前回のテスト結果がまだありません。先に他のモードで一度テストを受けてください。")


def render_chapter_select_screen(all_questions: list[dict]) -> None:
    """
    ③章指定モードで、実際に出題する章を選ぶ画面です。
    第1〜14章のボタンを縦に並べ、それぞれ簡単な説明文を表示します。
    第13章は出題データが存在しない章のため、ボタンを押せないようにしています。
    """
    st.subheader("出題する章を選んでください")

    # quiz_engine側で実際に問題データが存在する章の一覧を取得します。
    # （EXCLUDED_CHAPTERSに含まれる章や、そもそも問題が無い章はここには含まれません）
    available_chapters = set(quiz_engine.get_available_chapters(all_questions))

    # range(1, 15) は 1, 2, 3, ..., 14 という14個の数値を順に生成します。
    for chapter_num in range(1, 15):
        # f"{数値:02d}" で "1" を "01" のように2桁のゼロ埋め文字列に変換します。
        # 問題データ側の chapter の値（"01"など）と形式を合わせるためです。
        chapter_code = f"{chapter_num:02d}"
        description = CHAPTER_DESCRIPTIONS.get(chapter_code, "")
        label = f"第{chapter_num}章　{description}"

        with st.container(key=f"chapter_btn_{chapter_code}"):
            if chapter_code == EXCLUDED_CHAPTER_FOR_UI:
                # 第13章は出題範囲外なので、ボタンを無効化(disabled=True)して押せなくします。
                st.button(label, key=f"chapter_button_{chapter_code}", disabled=True, width="stretch")
                st.caption("13章は出題範囲外のため選択できません。")
            elif chapter_code in available_chapters:
                if st.button(label, key=f"chapter_button_{chapter_code}", width="stretch"):
                    start_quiz(all_questions, quiz_engine.MODE_CHAPTER, chapter=chapter_code)
            else:
                # 想定外に問題データが無い章があった場合も、念のため押せないようにしておきます。
                st.button(label, key=f"chapter_button_{chapter_code}", disabled=True, width="stretch")

    if centered_button("トップ画面へ戻る", key="chapter_back_button"):
        st.session_state["screen"] = "select"
        st.rerun()


# ── 出題画面 ────────────────────────────────────────────
def finish_quiz() -> None:
    """
    現在の回答状況で採点し、結果をsession_stateに保存して
    「result」画面に切り替えます。
    """
    quiz_items = st.session_state["quiz_items"]
    user_answers = st.session_state["user_answers"]
    # 出題内容と回答内容を突き合わせて採点してもらいます(頭脳部分はquiz_engine.py側)。
    result = quiz_engine.grade_answers(quiz_items, user_answers)

    st.session_state["result"] = result
    # 経過時間 = 「今の時刻」-「テストを開始した時刻」で計算します。
    st.session_state["elapsed_seconds"] = time.time() - st.session_state["start_time"]
    # 今回不正解だった問題のidを、次回「間違い再挑戦モード」で使えるように保存しておきます。
    # リストのままだと重複チェックなどがしづらいため、set(...)で集合に変換しています。
    st.session_state["last_wrong_ids"] = set(result["wrong_ids"])
    st.session_state["screen"] = "result"


# 「@st.fragment(run_every=1)」を付けると、この関数の中身だけを1秒ごとに
# 自動的に再実行してくれる「部品(フラグメント)」になります。
@st.fragment(run_every=1)
def render_timer() -> None:
    """
    タイマー表示だけを1秒ごとに更新する部品(フラグメント)です。
    st.fragmentを使うことで、この関数の中だけが再実行され、
    画面全体（選択肢や他のボタン）が毎秒ちらついたり、
    回答の選択状態がリセットされたりするのを防いでいます。
    """
    mode = st.session_state["mode"]
    # 経過時間(秒) = 現在時刻 - 開始時刻。
    elapsed = time.time() - st.session_state["start_time"]

    if mode == quiz_engine.MODE_EXAM:
        # 本番想定モードは「残り時間」を表示するカウントダウン方式です。
        remaining = quiz_engine.EXAM_TIME_LIMIT_SECONDS - elapsed
        if remaining <= 0:
            # 制限時間切れ。自動的に採点画面へ切り替える。
            finish_quiz()
            # フラグメント内であっても、st.rerun()を呼べばアプリ全体を再実行できます。
            # これによって、次の再実行では screen が "result" になっているため結果画面が表示されます。
            st.rerun()
        # st.metric()は「ラベル + 大きな数値」を見やすく表示するウィジェットです。
        st.metric("残り時間", format_seconds(remaining))
    elif mode == quiz_engine.MODE_SHORT:
        # 短時間モードは「経過時間」を表示するカウントアップ方式です。
        st.metric("経過時間", format_seconds(elapsed))


def render_quiz_screen() -> None:
    quiz_items = st.session_state["quiz_items"]
    current_index = st.session_state["current_index"]
    total = len(quiz_items)
    # 今表示すべき問題(辞書)を、リストの中から取り出します。
    item = quiz_items[current_index]

    # タイマーが必要なモード(本番想定・短時間)のときだけ、タイマー部品を表示します。
    if st.session_state["mode"] in (quiz_engine.MODE_EXAM, quiz_engine.MODE_SHORT):
        render_timer()

    # st.progress()は0.0〜1.0の割合でプログレスバー(進捗バー)を表示します。
    # 例えば10問中3問目(current_index=2)なら 2/10 = 0.2 (20%)というバーになります。
    st.progress((current_index) / total)
    # st.caption()は小さめの文字でちょっとした説明を表示するのに使います。
    st.caption(f"第{item['chapter']}章 ／ 問題 {item['code']} ／ {current_index + 1} / {total} 問")

    # 問題文(コードブロック込み)を表示します。
    render_question_body(item["question"])

    # 問題文と選択肢の間に、薄いグレーの区切り線を入れます。
    st.markdown('<hr class="question-divider">', unsafe_allow_html=True)

    choices = item["choices"]

    # 選んだ選択肢の番号を覚えておくためのsession_stateのキーです。
    # 問題のid・出題順(current_index)ごとに異なるキーにすることで、
    # 別の問題に切り替わったときに前の問題の選択状態が引き継がれてしまう
    # (バグの原因になる)のを防いでいます。
    selected_key = f"selected_choice_{item['id']}_{current_index}"
    # まだ何も選んでいない場合は None になります。
    selected_index = st.session_state.get(selected_key)

    # A, B, C, D の4枚の「カード」として選択肢を表示します。
    # st.container(key="choice_area") で囲むことで、この中のボタンだけに
    # inject_global_css() で定義したカード風のスタイルが適用されます。
    with st.container(key="choice_area"):
        for i, choice_text in enumerate(choices):
            is_selected = selected_index == i
            # タップして選択中の選択肢だけ type="primary"（目立つ色）にすることで、
            # どれを選んでいるかが一目で分かるようにしています。
            if st.button(
                f"{CHOICE_LETTERS[i]}　{choice_text}",
                key=f"choice_{item['id']}_{current_index}_{i}",
                type="primary" if is_selected else "secondary",
                width="stretch",
            ):
                # 選んだ番号をsession_stateに記録し、画面を再描画して
                # 選んだカードの色が変わった状態を反映させます。
                st.session_state[selected_key] = i
                st.rerun()

    # 今表示している問題が、出題リストの最後の1問かどうかを判定します。
    # current_indexは0始まりなので、「最後の問題の番号」は total - 1 になります。
    is_last_question = current_index == total - 1
    # 最後の問題かどうかで、次へ進むボタンのラベル文字列を変えています。
    next_label = "採点して結果を見る" if is_last_question else "次の問題へ ▶"

    # st.columns(2)で画面を横に2分割し、ボタンを左右に離して配置します。
    # 誤って意図しないボタンをタップしてしまわないようにするためです。
    col_exit, col_next = st.columns(2)

    with col_exit:
        # 「途中で終了して採点」ボタンは、左詰め（画面の左側）に配置します。
        # どの問題番号にいても常に押せます。
        with st.container(key="quiz_exit_wrap"):
            if st.button("途中で終了して採点", key="quiz_exit_button"):
                if selected_index is not None:
                    st.session_state["user_answers"][item["id"]] = selected_index
                finish_quiz()
                st.rerun()

    with col_next:
        # 「次の問題へ」ボタンは、右詰め（画面の右側）に配置します。
        with st.container(key="quiz_next_wrap"):
            if st.button(next_label, key="quiz_next_button", type="primary"):
                # 選択肢が選ばれていれば(None出なければ)、回答を記録します。
                # 何も選ばずに次へ進んだ場合は記録されず、grade_answers側で「未回答(不正解扱い)」になります。
                if selected_index is not None:
                    st.session_state["user_answers"][item["id"]] = selected_index

                if is_last_question:
                    # 最後の問題だった場合は、そのまま採点処理へ進みます。
                    finish_quiz()
                else:
                    # 最後でなければ、問題番号を1つ進めるだけです。
                    st.session_state["current_index"] += 1
                # session_stateの変更を画面に反映させるため、再実行します。
                st.rerun()


# ── 結果画面 ────────────────────────────────────────────
def reset_to_select_screen() -> None:
    """モード選択画面に戻るために、テスト関連のsession_stateを消去します。"""
    # for文で、消去したいキーの名前を1つずつ処理します。
    # tupleの中にキー名をまとめて書くことで、複数のキーをまとめて扱いやすくしています。
    for key in ("quiz_items", "current_index", "user_answers", "start_time",
                "mode", "result", "elapsed_seconds"):
        # dict.pop(キー, None) は「そのキーがあれば削除して値を返す、無ければNoneを返す」メソッドです。
        # 存在しないキーをdel文で消そうとするとエラーになりますが、pop(key, None)ならエラーになりません。
        st.session_state.pop(key, None)
    # 最後に画面を「select(モード選択画面)」に戻します。
    st.session_state["screen"] = "select"


def render_result_screen(all_questions: list[dict]) -> None:
    result = st.session_state["result"]
    mode = st.session_state["mode"]

    st.subheader("結果発表")

    # 合否によって、緑色の成功メッセージか赤色のエラーメッセージを出し分けます。
    # f"{値:.1f}" は「小数点以下1桁までの数値」として文字列に埋め込む書き方です。
    if result["passed"]:
        st.success(f"合格です！ 🎉（正答率 {result['percentage']:.1f}%）")
    else:
        st.error(f"不合格でした（正答率 {result['percentage']:.1f}%）")

    # 得点・正答率・タイマー結果を3列に並べて表示します。
    col1, col2, col3 = st.columns(3)
    col1.metric("得点", f"{result['correct_count']} / {result['total']} 問")
    col2.metric("正答率", f"{result['percentage']:.1f}%")

    elapsed = st.session_state["elapsed_seconds"]
    if mode == quiz_engine.MODE_EXAM:
        # 本番想定モードは「制限時間 - 経過時間」で残り時間を表示します。
        # マイナスにならないよう、max(0, ...)で下限を0に揃えています。
        remaining = max(0, quiz_engine.EXAM_TIME_LIMIT_SECONDS - elapsed)
        col3.metric("残り時間", format_seconds(remaining))
    else:
        # それ以外のモードは、単純に「かかった時間」を表示します。
        col3.metric("所要時間", format_seconds(elapsed))

    st.write("### 章別の正答率")
    # 章ごとの正答率を、テーブル表示用のリストに組み立てていきます。
    chapter_rows = []
    # sorted(result["chapter_stats"].items()) で、章番号の昇順に並べ替えながら
    # (章番号, {"correct": 正答数, "total": 出題数}) のペアを1つずつ取り出します。
    for chapter, stats in sorted(result["chapter_stats"].items()):
        # その章の出題数が0のとき(理論上は起きない想定)のゼロ除算を避けています。
        rate = stats["correct"] / stats["total"] * 100 if stats["total"] else 0
        # 1章分の行データを辞書として作り、リストに追加します。
        chapter_rows.append(
            {"章": chapter, "正答数": stats["correct"], "出題数": stats["total"], "正答率": f"{rate:.1f}%"}
        )
    # st.table()に「辞書のリスト」を渡すと、キーを列見出しにした表を自動で作ってくれます。
    st.table(chapter_rows)

    st.write("### 次のアクション")

    # スマホで見たときに窮屈にならないよう、3つのボタンを横並びではなく
    # 縦に並べて、それぞれ中央揃えで表示します（centered_button()を使用）。

    # 1問も間違えていない場合は、再挑戦するボタンを押せないようにします。
    has_wrong = len(result["wrong_ids"]) > 0
    if centered_button(
        "今回間違えた問題だけに再挑戦する",
        key="result_retry_button",
        disabled=not has_wrong,
    ):
        # 間違えた問題だけを対象に、もう一度出題を組み立てて「quiz」画面へ進みます。
        start_quiz(all_questions, quiz_engine.MODE_RETRY, chapter=None)

    if centered_button("全問題の解説を見る（総復習リスト）", key="result_review_button"):
        st.session_state["screen"] = "review"
        st.rerun()

    if centered_button("トップ画面へ戻る", key="result_top_button"):
        reset_to_select_screen()
        st.rerun()


# ── 総復習リスト画面 ───────────────────────────────────────
def render_review_screen() -> None:
    st.subheader("総復習リスト（全問の解説）")

    quiz_items = st.session_state["quiz_items"]
    user_answers = st.session_state["user_answers"]

    # enumerate(リスト, start=1) を使うと、「1番目から始まる連番(i)」と「中身(item)」を
    # 同時に取り出せます（start=1を付けないと0番目から始まってしまいます）。
    for i, item in enumerate(quiz_items, start=1):
        selected_index = user_answers.get(item["id"])
        is_correct = selected_index is not None and selected_index == item["correct_index"]
        mark = "✅ 正解" if is_correct else "❌ 不正解"

        # st.expander()は、クリックすると中身が開閉する「折りたたみ表示」のウィジェットです。
        # 全問を最初から表示すると画面が長くなりすぎるため、1問ずつ折りたたんでいます。
        with st.expander(f"{mark}　問題{i}（{item['code']}）"):
            render_question_body(item["question"])
            # Markdownの「**文字**」という書き方で太字にしています。st.write()はMarkdown記法に対応しています。
            st.write(f"**正解：** {item['answer']}")
            if selected_index is not None:
                st.write(f"**あなたの回答：** {item['choices'][selected_index]}")
            else:
                st.write("**あなたの回答：** （未回答）")
            # st.info()は青色の背景で、補足情報(ここでは解説文)を目立たせて表示します。
            st.info(item["commentary"])

    if centered_button("結果画面に戻る", key="review_back_button"):
        st.session_state["screen"] = "result"
        st.rerun()


# ── メイン処理 ──────────────────────────────────────────
def main() -> None:
    # st.set_page_config()は、ブラウザのタブに表示されるタイトルやアイコンを設定します。
    # この関数は必ずファイルの中で最初に呼ばれるStreamlitの命令である必要があります。
    st.set_page_config(page_title="繰り返し解く！Python3基礎試験400問", page_icon="🐍")
    # アプリ全体で使う見た目調整用のCSSを埋め込みます。
    inject_global_css()

    # URLパラメータから、認証済みの受講者名を取得しようとします(未認証ならNone)。
    name = get_authenticated_name()

    if name is None:
        # user パラメータが無い、またはデコードに失敗した(=不正なURL)場合は
        # 認証画面を表示して処理を打ち切る。
        # ここで「パラメータ自体は存在するがデコードに失敗した」ケースと、
        # 「そもそもパラメータが無い」ケースを区別しています。
        if st.query_params.get("user") is not None:
            st.error("URLが正しくありません。もう一度認証してください。")
            # 壊れた値がURLに残ったままだと再認証してもループしてしまうため、削除しておきます。
            del st.query_params["user"]
        render_auth_screen()
        # return でこの関数の実行をここで終了します(この先の画面表示処理には進みません)。
        return

    all_questions = get_all_questions()
    # st.session_state.setdefault("screen", "select") は、
    # 「screenというキーがまだ無ければ"select"を入れる、既にあればその値をそのまま使う」という意味です。
    # これにより、アプリを開いた直後は自動的に「モード選択画面」からスタートします。
    screen = st.session_state.setdefault("screen", "select")

    # 画面によって、ヘッダーに表示するアプリ名を切り替えます。
    # トップ画面(select)と章選択画面(chapter_select)ではフルネームの3行表示、
    # それ以外(quiz/result/review)では省スペースな略式の1行表示にしています。
    if screen in ("select", "chapter_select"):
        render_full_title()
    else:
        render_short_title()

    # st.success() は緑色の背景で強調表示するための関数です。
    st.success(f"受講者：{name} さん（読者限定版）")

    # 現在の画面(screen)の値に応じて、対応する描画関数を呼び出します。
    # これがこのアプリの「画面切り替え」の中心となる分岐です。
    if screen == "select":
        render_select_screen(all_questions)
    elif screen == "chapter_select":
        render_chapter_select_screen(all_questions)
    elif screen == "quiz":
        render_quiz_screen()
    elif screen == "result":
        render_result_screen(all_questions)
    elif screen == "review":
        render_review_screen()


# 「if __name__ == "__main__":」は、「このファイルが直接実行されたときだけ、
# 以下の処理を行う」という、Pythonでよく使われるお決まりの書き方です。
# streamlit run src/app.py で実行されたとき、Python内部ではこのファイルが
# 直接実行される扱いになるため、main()が呼び出されます。
if __name__ == "__main__":
    main()
