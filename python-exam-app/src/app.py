"""
app.py
------
Streamlitで動く「繰り返し解く！ Python3 基礎試験 Webテスト」のメイン画面です。

このファイルは大きく4つの「画面(screen)」を、st.session_state["screen"] の
値によって切り替える作りになっています。
    "select" : 学習モードを選ぶ画面
    "quiz"   : 実際に問題を解く画面
    "result" : 採点結果を表示する画面
    "review" : 全問の解説を見る画面（総復習リスト）

Streamlitは「ボタンが押される」などの操作のたびに、このファイルの中身が
上から下まで丸ごと再実行される、という特徴があります。そのため、
「今どの画面を表示しているか」「今何問目か」といった情報は
st.session_state（ブラウザのタブごとに保持される辞書のようなもの）に
保存しておく必要があります。
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

# 画面上に表示する、モードごとの日本語ラベルをまとめた辞書です。
# キー(quiz_engine.MODE_EXAMなど)から、表示用の文字列を引けるようにしています。
MODE_LABELS = {
    quiz_engine.MODE_EXAM: "① 本番想定モード（40問・60分カウントダウン）",
    quiz_engine.MODE_SHORT: "② 短時間モード（10問・カウントアップ）",
    quiz_engine.MODE_CHAPTER: "③ 章指定モード（指定した章から10問）",
    quiz_engine.MODE_RETRY: "④ 間違い再挑戦（前回間違えた問題のみ）",
}


# 「@st.cache_data」はデコレータと呼ばれる書き方で、関数の直前に付けることで
# 関数の動作に「キャッシュ機能」を追加できます。
# Streamlitはボタン操作のたびにapp.py全体を再実行しますが、キャッシュを付けておくと
# 「同じ引数で呼ばれた場合は、前回の結果を使い回す」ようになり、
# 毎回JSONファイルを読み直す無駄な処理を防げます（動作が軽くなります）。
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
    st.title("繰り返し解く！ Python3 基礎試験 Webテスト")
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


def render_header(name: str) -> None:
    """画面上部に受講者名のバッジを表示します。"""
    st.title("繰り返し解く！ Python3 基礎試験 Webテスト")
    # st.success() は緑色の背景で強調表示するための関数です。
    # f"..." は f文字列で、{name}の部分が実際の変数の値に置き換わります。
    st.success(f"受講者：{name} さん（読者限定版）")


# ── モード選択画面 ────────────────────────────────────────
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
    st.subheader("学習モードを選んでください")

    # st.radio() はラジオボタン(1つだけ選べる選択肢)を表示するウィジェットです。
    # options には内部的な値のリスト(quiz_engine.MODE_EXAMなどの文字列)を渡し、
    # format_func で「画面に表示するときだけ日本語ラベルに変換する」ようにしています。
    # こうすることで、画面表示用の文字列と、プログラム内部で使う値を分離できます。
    selected_mode = st.radio(
        "モード",
        options=list(MODE_LABELS.keys()),
        format_func=lambda m: MODE_LABELS[m],
        # label_visibility="collapsed" は、上の "モード" というラベル文字列を
        # 画面上には表示しない(隠す)という設定です。
        label_visibility="collapsed",
    )

    # 章指定モードが選ばれているときだけ、章を選ぶプルダウン(selectbox)を追加で表示します。
    chapter = None
    if selected_mode == quiz_engine.MODE_CHAPTER:
        chapters = quiz_engine.get_available_chapters(all_questions)
        chapter = st.selectbox("章を選択してください", chapters)

    # session_state.get("last_wrong_ids") は、まだ一度もテストを終えていない場合は None になります。
    # 「or set()」を付けることで、Noneのときは代わりに空の集合を使うようにしています。
    last_wrong_ids = st.session_state.get("last_wrong_ids") or set()

    # 間違い再挑戦モードが選ばれていて、かつ前回間違えた問題が無い場合は注意文を表示します。
    if selected_mode == quiz_engine.MODE_RETRY and not last_wrong_ids:
        st.warning(
            "前回のテスト結果がまだありません。先に他のモードで一度テストを受けてください。"
        )

    # 上と同じ条件のときは、開始ボタン自体も押せないようにします(disabled=True)。
    start_disabled = selected_mode == quiz_engine.MODE_RETRY and not last_wrong_ids
    # st.button()は、押されたときだけTrueを返すボタンです。
    # type="primary" にすると、目立つ色(強調スタイル)のボタンになります。
    if st.button("テストを開始する", type="primary", disabled=start_disabled):
        start_quiz(all_questions, selected_mode, chapter)


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

    choices = item["choices"]
    # st.radio()で4つの選択肢を表示します。
    # options=range(len(choices)) として「0, 1, 2, 3」という番号そのものを選択肢の値にし、
    # format_func で「画面には choices[番号] の文字列を表示する」ようにしています。
    # こうすることで、st.radio()の戻り値がそのまま「選んだ選択肢の番号(インデックス)」になり、
    # 採点時にcorrect_indexと直接比較できます。
    # index=None にすることで、最初は何も選ばれていない状態からスタートします。
    # key=f"answer_{item['id']}_{current_index}" は、この部品を一意に識別するための名前です。
    # 問題ごとに異なるkeyを付けることで、問題が変わったときに前の問題の選択状態が
    # 引き継がれてしまう(バグの原因になる)のを防いでいます。
    selected_index = st.radio(
        "選択肢",
        options=range(len(choices)),
        format_func=lambda i: choices[i],
        index=None,
        key=f"answer_{item['id']}_{current_index}",
        label_visibility="collapsed",
    )

    # st.columns(2)で画面を横に2分割し、ボタンを横並びに配置します。
    col1, col2 = st.columns(2)

    # 今表示している問題が、出題リストの最後の1問かどうかを判定します。
    # current_indexは0始まりなので、「最後の問題の番号」は total - 1 になります。
    is_last_question = current_index == total - 1
    # 最後の問題かどうかで、次へ進むボタンのラベル文字列を変えています。
    next_label = "採点して結果を見る" if is_last_question else "次の問題へ ▶"

    # with col1: と書くと、そのブロックの中の部品は1列目(左側)に配置されます。
    with col1:
        if st.button(next_label, type="primary"):
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

    with col2:
        # 「途中で終了して採点」ボタンは、どの問題番号にいても常に押せます。
        if st.button("途中で終了して採点"):
            if selected_index is not None:
                st.session_state["user_answers"][item["id"]] = selected_index
            finish_quiz()
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
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        # 1問も間違えていない場合は、再挑戦するボタンを押せないようにします。
        has_wrong = len(result["wrong_ids"]) > 0
        if st.button("今回間違えた問題だけに再挑戦する", disabled=not has_wrong):
            # 間違えた問題だけを対象に、もう一度出題を組み立てて「quiz」画面へ進みます。
            start_quiz(all_questions, quiz_engine.MODE_RETRY, chapter=None)

    with col_b:
        if st.button("全問題の解説を見る（総復習リスト）"):
            st.session_state["screen"] = "review"
            st.rerun()

    with col_c:
        if st.button("トップ画面へ戻る"):
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

    if st.button("結果画面に戻る"):
        st.session_state["screen"] = "result"
        st.rerun()


# ── メイン処理 ──────────────────────────────────────────
def main() -> None:
    # st.set_page_config()は、ブラウザのタブに表示されるタイトルやアイコンを設定します。
    # この関数は必ずファイルの中で最初に呼ばれるStreamlitの命令である必要があります。
    st.set_page_config(page_title="繰り返し解く！ Python3 基礎試験 Webテスト", page_icon="🐍")

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

    # ここに到達した時点で、認証は済んでいることが保証されています。
    render_header(name)

    all_questions = get_all_questions()
    # st.session_state.setdefault("screen", "select") は、
    # 「screenというキーがまだ無ければ"select"を入れる、既にあればその値をそのまま使う」という意味です。
    # これにより、アプリを開いた直後は自動的に「モード選択画面」からスタートします。
    screen = st.session_state.setdefault("screen", "select")

    # 現在の画面(screen)の値に応じて、対応する描画関数を呼び出します。
    # これがこのアプリの「画面切り替え」の中心となる分岐です。
    if screen == "select":
        render_select_screen(all_questions)
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
