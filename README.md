# English Quiz Tool (英語クイズツール)

## 概要

このアプリケーションは、OpenRouter API または Google Gemini API を使用して、英語の多肢選択式クイズ問題を生成し、Tkinter GUI を通じてユーザーに出題するツールです。生成された問題は SQLite データベースに保存され、後で利用できます。

## 機能

* **AIによる問題生成:** OpenRouter または Google Gemini API を利用して、指定した難易度 (CEFRレベル) に合わせた英文法・文章補完問題を自動生成します。
* **カスタマイズ可能なプロンプト:** 「Prompt Assist」フィールドを使用して、問題生成の要望をAIに追加で伝えることができます。
* **難易度選択:** 初級 (A2) から最上級 (C2) までのCEFRレベルを選択できます。
* **GUIインターフェース:** Tkinter を使用したシンプルなグラフィカルユーザーインターフェースを提供します。
* **データベース保存:** 生成された問題、選択肢、正解、日本語訳、解説を SQLite データベース (`english_quiz.db`) に保存します。
* **即時フィードバック:** 回答を選択するとすぐに正誤判定と解説が表示されます。
* **日本語訳と解説:** 各問題には日本語訳と、なぜその答えが正しいのか（または他の選択肢が間違いなのか）を示す日本語の解説が含まれます。

## 要件

* Python 3.6 以降
* 必要なライブラリ:
    * `requests`
    * `python-dotenv`
    * `tkinter` (通常はPythonに同梱されています)

## セットアップ

1.  **リポジトリのクローン (任意):**
    ```bash
    git clone <リポジトリのURL>
    cd <リポジトリのディレクトリ>
    ```
2.  **依存ライブラリのインストール:**
    ```bash
    pip install requests python-dotenv
    ```
    (もし `requirements.txt` ファイルがあれば `pip install -r requirements.txt` を使用)

3.  **.env ファイルの作成:**
    スクリプトと同じディレクトリに `.env` という名前のファイルを作成し、以下の内容を記述します。

    ```dotenv
    # --- API Provider Configuration ---
    # 使用するAPIプロバイダーを指定します ('openrouter' または 'gemini')
    API_PROVIDER=openrouter

    # --- API Keys (使用するプロバイダーに応じて設定) ---
    # OpenRouterを使用する場合:
    OPENROUTER_API_KEY=your_openrouter_api_key_here

    # Google Geminiを使用する場合:
    GEMINI_API_KEY=your_gemini_api_key_here

    # --- Model Selection (Optional) ---
    # 使用するAIモデルを指定します。プロバイダーに合わせて適切なモデル名を記述してください。
    # 指定しない場合は、スクリプト内のデフォルトモデルが使用されます。
    # 例:
    # OPENROUTER_MODEL=mistralai/mistral-7b-instruct:free
    # OPENROUTER_MODEL=google/gemma-3-12b-it
    # OPENROUTER_MODEL=google/gemini-1.5-flash-latest # Geminiの場合もこの変数を使用
    OPENROUTER_MODEL=google/gemma-3-12b-it
    ```

    * `API_PROVIDER`: `openrouter` または `gemini` のいずれかを指定します。
    * `OPENROUTER_API_KEY`: OpenRouter を使用する場合、あなたの API キーに置き換えます。
    * `GEMINI_API_KEY`: Gemini を使用する場合、あなたの API キーに置き換えます。
    * `OPENROUTER_MODEL`: 使用したいモデル名を指定します。指定しない場合、スクリプト内のデフォルト値が使われます。Gemini を使う場合でも、この変数名でモデルを指定します (例: `google/gemini-1.5-flash-latest`)。

## 使い方

1.  **スクリプトの実行:**
    ```bash
    python your_script_name.py
    ```
    (`your_script_name.py` は実際のファイル名に置き換えてください)

2.  **GUI操作:**
    * **Difficulty:** ドロップダウンメニューから問題の難易度 (CEFRレベル) を選択します。
    * **Prompt Assist:** (任意) 問題生成に関する追加の要望があれば入力します (例: 「句動詞の問題を多めに」)。
    * **Generate New Questions:** ボタンをクリックすると、設定に基づいてAPIから新しい問題が生成され、データベースに保存されます。生成中はボタンが無効になります。
    * **問題表示:** 生成が完了すると、最初の問題と選択肢が表示されます。
    * **回答:** 4つの選択肢の中から正しいと思うものをクリックします。
    * **フィードバック:** 回答後すぐに、正解/不正解、正解の選択肢番号、日本語訳、解説が表示されます。
    * **Next Question:** ボタンをクリックして次の問題に進みます。最後の問題に回答すると、クイズの結果が表示されます。

## データベース

* 生成されたクイズ問題は、スクリプトと同じディレクトリにある `english_quiz.db` という SQLite ファイルに保存されます。
* `problems` テーブルには、問題文、選択肢、正解番号、日本語訳、解説などが格納されます。
* 新しい問題を生成すると、既存の問題はデータベースから削除され、新しい問題セットに置き換えられます。

## エラーハンドリング

* APIキーが見つからない場合や無効な場合、アプリケーションは起動時にエラーメッセージを表示します。
* API通信中やデータベース操作中にエラーが発生した場合、エラーメッセージがポップアップ表示されたり、コンソールに出力されたりします。

## 貢献 (任意)

バグ報告や機能改善の提案は、Issue トラッカーを通じて歓迎します。プルリクエストも歓迎です。

## ライセンス (任意)

このプロジェクトは [ライセンス名 (例: MIT License)] の下で公開されています。詳細は `LICENSE` ファイルをご覧ください。
