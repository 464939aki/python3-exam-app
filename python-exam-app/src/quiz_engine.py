"""
quiz_engine.py
--------------
「出題（問題の抽出）」「選択肢のシャッフル」「採点」といった、
Web画面の見た目に関係しない“頭脳部分”のロジックをまとめたモジュールです。

Streamlit(app.py)側からは、このファイルの関数を呼び出すだけで
問題データを扱えるようにしています。
"""

# json: JSON形式のファイル（questions.json）を読み込むための標準ライブラリです。
import json
# random: ランダムに問題や選択肢を選んだり、並び順をシャッフルしたりするための標準ライブラリです。
import random

# ここで4つの学習モードの名前を「文字列の定数」として定義しています。
# 文字列を直接あちこちに書くと、タイプミスをしても気づきにくいので、
# 定数としてまとめておくことで、app.py側からも安全に参照できます。
# （定数は「値が変わらない変数」のことで、Pythonでは慣習的に全て大文字で書きます）
MODE_EXAM = "exam"        # 本番想定モード（40問・60分カウントダウン）
MODE_SHORT = "short"      # 短時間モード（10問・カウントアップ）
MODE_CHAPTER = "chapter"  # 章指定モード（指定した章から10問）
MODE_RETRY = "retry"      # 間違い再挑戦（前回間違えた問題のみ）

# モードごとの出題数を辞書(dict)で管理しています。
# 例えば QUESTION_COUNTS[MODE_EXAM] と書くと 40 が取り出せます。
# retryモードは「間違えた問題の数」がそのまま出題数になるため、
# ここには含めていません（select_quiz_questions関数側で個別に扱います）。
QUESTION_COUNTS = {
    MODE_EXAM: 40,
    MODE_SHORT: 10,
    MODE_CHAPTER: 10,
}

# 本番想定モードの制限時間（秒）。60分 = 60秒 × 60分 = 3600秒。
EXAM_TIME_LIMIT_SECONDS = 60 * 60

# 章指定モードの選択肢から除外する章。
# {"13"} はPythonの「集合(set)」というデータ型で、「13という要素だけが1つ入った集合」です。
# 集合は「ある値が含まれているかどうか」を高速に判定できるのが特徴です。
# 「第13章は自動で除外される仕様」という要件に対応するための設定です。
EXCLUDED_CHAPTERS = {"13"}

# 合否判定のボーダーライン（0.7 = 70%以上で合格）。
PASS_THRESHOLD = 0.7


def load_questions(json_path: str) -> list[dict]:
    """
    問題データ(JSONファイル)を読み込んで、Pythonの辞書のリストとして返します。
    """
    # with文を使うと、ファイルを開いたあとの「閉じ忘れ」を防げます。
    # withブロックを抜けるタイミングで、Pythonが自動的にファイルを閉じてくれます。
    # encoding="utf-8" を指定しているのは、questions.json内の日本語を
    # 正しく読み込むためです（指定しないと環境によって文字化けする場合があります）。
    with open(json_path, encoding="utf-8") as f:
        # json.load(f) は、ファイルの中身(JSONテキスト)を、
        # Pythonのリストや辞書といったデータ構造に変換して返します。
        # questions.jsonはJSON配列なので、ここでは「辞書のリスト」が返ってきます。
        return json.load(f)


def get_available_chapters(all_questions: list[dict]) -> list[str]:
    """
    問題データの中から、章指定モードで選択できる章の一覧を作ります。
    EXCLUDED_CHAPTERS（第13章など）は選択肢から取り除き、
    重複を除いた上で番号順に並べ替えて返します。
    """
    # {q["chapter"] for q in all_questions} は「集合内包表記」という書き方です。
    # 全問題の chapter の値を集めていますが、集合(set)に入れることで
    # 自動的に重複が取り除かれます（例: "01"が10回出てきても、集合には1つだけ残る）。
    chapters = {q["chapter"] for q in all_questions}

    # 集合どうしの「-=」（差集合の代入）で、EXCLUDED_CHAPTERSに含まれる章を取り除きます。
    # 例: chapters = {"01", "13"} から EXCLUDED_CHAPTERS = {"13"} を引くと {"01"} になる。
    chapters -= EXCLUDED_CHAPTERS

    # sorted() で文字列としての昇順（"01", "02", ... の順）に並べ替えたリストにして返します。
    # 集合(set)のままだと並び順が保証されないため、画面に表示する前にリスト化して整列します。
    return sorted(chapters)


def build_choices(question: dict) -> dict:
    """
    1問分の問題データから、画面に表示する「選択肢」を作ります。

    手順:
    1. wrong_pool（6つの誤答）の中から、ランダムに3つを選ぶ。
    2. 選んだ3つの誤答と、正解(answer)を合わせて計4つの選択肢にする。
    3. 4つの選択肢の並び順をシャッフルする（毎回同じ位置に正解が来ないように）。
    4. シャッフル後、正解が何番目(インデックス)にあるかを記録しておく。
       この番号があれば、採点のときに「ユーザーが選んだ番号」と比較するだけで
       正誤判定ができます。

    戻り値: {"choices": [選択肢の文字列が4つ], "correct_index": 正解の番号}
    """
    # random.sample(リスト, k=個数) は、リストの中から重複なくランダムにk個選ぶ関数です。
    # question["wrong_pool"] には誤答が6つ入っているので、その中から3つを選びます。
    chosen_wrong = random.sample(question["wrong_pool"], 3)

    # リストの「+」は連結（くっつける）という意味です。
    # 誤答3つのリストに、正解1つを入れたリスト [question["answer"]] をくっつけて、
    # 要素数4つのリストにしています。この時点ではまだ「誤答, 誤答, 誤答, 正解」の順番です。
    choices = chosen_wrong + [question["answer"]]

    # random.shuffle(リスト) は、リストの中身をその場で（元のリストを直接書き換えて）
    # ランダムに並び替える関数です。これにより、正解がどこに来るかは毎回変わります。
    random.shuffle(choices)

    # シャッフル後のリストの中で、正解(question["answer"])が何番目にあるかを調べます。
    # list.index(値) は「その値が最初に見つかった位置(インデックス)」を返す関数です。
    # 例えば choices が ["誤答A", "正解", "誤答B", "誤答C"] なら、correct_index は 1 になります。
    correct_index = choices.index(question["answer"])

    # 選択肢のリストと、正解の位置(番号)をまとめて辞書として返します。
    # app.py側はこの戻り値を使って選択肢を表示したり、採点したりします。
    return {"choices": choices, "correct_index": correct_index}


def select_quiz_questions(
    all_questions: list[dict],
    mode: str,
    *,
    chapter: str | None = None,
    wrong_ids: set[str] | None = None,
) -> list[dict]:
    """
    学習モードに応じて出題する問題を選び、それぞれに選択肢(choices)を
    付け加えたリストを返します。

    引数:
        all_questions: 全問題データ
        mode: MODE_EXAM / MODE_SHORT / MODE_CHAPTER / MODE_RETRY のいずれか
        chapter: 章指定モードのときに選ばれた章番号（例: "01"）
        wrong_ids: 間違い再挑戦モードのときに使う「前回間違えた問題id」の集合

    引数名の前にある「*」は、これより後ろの引数(chapter, wrong_ids)を
    「キーワード引数」として名前付きで渡すことを強制するための書き方です。
    （select_quiz_questions(questions, "chapter", "01") のような、位置だけでの
      呼び出しを禁止し、chapter="01" のように書かせることで、呼び出し側のコードを
      読んだときに何を渡しているか分かりやすくしています）
    """
    # モードによって「どの問題を候補(pool)にするか」「何問出題するか(count)」を決めます。
    # if / elif / else は「条件によって処理を分岐させる」ためのPythonの制御構文です。

    if mode == MODE_CHAPTER:
        # 章指定モード: 全問題の中から、指定された章(chapter)と一致するものだけを候補にする。
        # [q for q in all_questions if q["chapter"] == chapter] は「リスト内包表記」で、
        # 「all_questionsの中から、条件(chapterが一致)を満たすqだけを集めた新しいリスト」を作ります。
        pool = [q for q in all_questions if q["chapter"] == chapter]
        count = QUESTION_COUNTS[MODE_CHAPTER]
    elif mode == MODE_RETRY:
        # 間違い再挑戦モード: wrong_idsが渡されなかった場合(None)に備えて、
        # 「or set()」で「Noneだったら空の集合を使う」というデフォルト値を用意しています。
        wrong_ids = wrong_ids or set()
        # 問題のidがwrong_idsに含まれているものだけを候補にする。
        pool = [q for q in all_questions if q["id"] in wrong_ids]
        # 間違い再挑戦は「間違えた問題ぜんぶ」が対象なので、件数の上限は設けません。
        count = len(pool)
    else:
        # 本番想定モード・短時間モードはどちらも「全問題からランダムに出題」なので、
        # 候補(pool)は絞り込まず、全問題をそのまま使います。
        pool = all_questions
        count = QUESTION_COUNTS[mode]

    # 母数(pool)が出題数(count)より少ない場合にrandom.sampleがエラーにならないよう、
    # min()で「countとpoolの件数のうち、小さい方」に丸めています。
    # （例: 章指定モードで対象章の問題が10問未満しか無い場合、その全問が出題される）
    selected = random.sample(pool, k=min(count, len(pool)))

    # 各問題に選択肢情報(choices・correct_index)を合体させて、最終的な出題リストを作ります。
    quiz_items = []
    # for文で、選ばれた問題(selected)を1問ずつ取り出して処理します。
    for q in selected:
        # {**q, **build_choices(q)} は「辞書の展開(アンパック)」という書き方です。
        # 元の問題データq(辞書)と、build_choices(q)が返す選択肢情報(辞書)を
        # 1つの新しい辞書にまとめて合体させています。
        # 元の辞書qを直接書き換えるのではなく、新しい辞書を作っているので、
        # 呼び出し元のall_questionsのデータには影響を与えません（安全な書き方です）。
        quiz_items.append({**q, **build_choices(q)})
    return quiz_items


def grade_answers(quiz_items: list[dict], user_answers: dict[str, int]) -> dict:
    """
    出題した問題(quiz_items)と、ユーザーが選んだ回答(user_answers)を
    突き合わせて採点します。

    引数:
        quiz_items: select_quiz_questions() が返した「出題リスト」
        user_answers: { 問題id: 選んだ選択肢のインデックス } という辞書
                      （未回答の問題はキーが存在しない想定）

    戻り値には、得点・正答率・合否・章別正答率・不正解だった問題idの
    一覧をまとめています。
    """
    # 出題数の合計。len()はリストや辞書の「要素数」を数える組み込み関数です。
    total = len(quiz_items)
    # 正解した数を数えるためのカウンター。最初は0から始めます。
    correct_count = 0
    # 不正解だった問題のidを集めておくための空リスト。
    wrong_ids = []
    # 章ごとの正答数・出題数を集計するための辞書。
    # 型ヒント dict[str, dict[str, int]] は「キーが文字列(章番号)で、値がさらに
    # {文字列: 整数} という辞書になっている辞書」という意味です。
    chapter_stats: dict[str, dict[str, int]] = {}

    # 出題した問題を1問ずつ順番にチェックしていきます。
    for item in quiz_items:
        chapter = item["chapter"]

        # setdefault(キー, 初期値) は「そのキーが辞書に無ければ初期値を入れる、
        # 既にあれば何もしない」という便利なメソッドです。
        # これにより、初めて登場した章のときだけ {"correct": 0, "total": 0} で初期化されます。
        chapter_stats.setdefault(chapter, {"correct": 0, "total": 0})
        # この章の出題数を1増やします。
        chapter_stats[chapter]["total"] += 1

        # dict.get(キー) は、キーが存在すれば値を、存在しなければ None を返します。
        # （辞書に無いキーを [] でアクセスするとエラーになりますが、get()ならエラーになりません）
        # つまり、その問題が「未回答」だった場合は selected_index が None になります。
        selected_index = user_answers.get(item["id"])

        # 「回答されていて(Noneでない)」かつ「選んだ番号が正解の番号と一致する」場合にのみ正解とみなします。
        # is not None のチェックが無いと、未回答(None)と「0番を選んだ」場合を区別できなくなってしまいます。
        is_correct = selected_index is not None and selected_index == item["correct_index"]

        if is_correct:
            correct_count += 1
            chapter_stats[chapter]["correct"] += 1
        else:
            # 不正解(未回答も含む)だった問題のidを記録しておきます。
            # これが「間違い再挑戦モード」で使われるリストの元になります。
            wrong_ids.append(item["id"])

    # 正答率(%)を計算します。
    # 出題数が0問のとき(total == 0)にゼロ除算エラーになるのを避けるため、
    # 三項演算子（if文を1行で書ける書き方）で「0問なら0.0%とする」という分岐を入れています。
    percentage = (correct_count / total * 100) if total > 0 else 0.0

    # 採点結果をまとめて辞書として返します。
    # app.py側はこの戻り値をそのまま結果画面の表示に使います。
    return {
        "total": total,
        "correct_count": correct_count,
        "percentage": percentage,
        # PASS_THRESHOLD(0.7)は割合(0〜1)なので、100倍して%表記のpercentageと比較します。
        "passed": percentage >= PASS_THRESHOLD * 100,
        "chapter_stats": chapter_stats,
        "wrong_ids": wrong_ids,
    }
