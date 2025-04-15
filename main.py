import tkinter as tk
from tkinter import messagebox, scrolledtext
import requests
import json
import sqlite3
import os
from dotenv import load_dotenv
import threading
# import time # Unused import

# --- Configuration ---
DB_NAME = 'english_quiz.db'
QUESTIONS_PER_GENERATION = 10
# Consider adding a model choice here if needed, e.g., "openai/gpt-3.5-turbo"
# Get model from environment variable or use a default
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL", "google/gemma-3-12b-it"
    # "OPENROUTER_MODEL", "arliai/qwq-32b-arliai-rpr-v1:free"
)  # Example model


# --- Database Setup ---
def initialize_database():
    """Creates the database and table if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            option1 TEXT NOT NULL,
            option2 TEXT NOT NULL,
            option3 TEXT NOT NULL,
            option4 TEXT NOT NULL,
            answer INTEGER NOT NULL CHECK(answer >= 1 AND answer <= 4),
            explanation TEXT NOT NULL,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


# --- API Interaction ---
def _generate_via_openrouter(api_key, model, difficulty, assist_prompt):
    """Generates questions using the OpenRouter API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Map difficulty selection to CEFR levels for the prompt
    difficulty_map = {
        "Beginner (A2)": "CEFR A2レベル",
        "Intermediate (B1)": "CEFR B1レベル",
        "Advanced (B2)": "CEFR B2レベル",
    }
    target_level = difficulty_map.get(
        difficulty, "CEFR B1レベル")  # Default to B1

    # Carefully crafted prompt based on requirements
    prompt_text = f"""
    Generate {QUESTIONS_PER_GENERATION} multiple-choice English grammar and
    simple sentence completion questions suitable for beginner to intermediate
    English learners at the {target_level}. Focus on common grammar points like
    tenses, phrasal verbs, prepositions, articles, and basic sentence structure.

    Provide the output strictly as a JSON array of objects. Each object must
    have the following keys:
    - "question": The question text (string). For sentence completion, use "..."
                  to indicate the blank.
    - "options": An array of 4 strings representing the choices.
    - "answer": The index (starting from 1) of the correct option in the
                "options" array (integer).
    - "explanation": A brief explanation of why the answer is correct and
                     potentially why others are incorrect (string). **解説内容 (explanation) は日本語で記述してください。**

    {f'Additionally, consider the following request for the questions: {assist_prompt}' if assist_prompt else ''}

    Example format for one question object:
    {{
      "question": "She ___ watching TV when I arrived.",
      "options": ["is", "was", "be", "are"],
      "answer": 2,
      "explanation": "Use the past continuous tense 'was watching' because the
                      action was in progress when another past action (arrived)
                      occurred."
    }}

    Ensure you provide exactly {QUESTIONS_PER_GENERATION} distinct question
    objects in the JSON array. Do not include any text before or after the
    JSON array.
    """

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an AI assistant that "
             "generates English multiple-choice "
             "questions in JSON format."},
            {"role": "user", "content": prompt_text}
        ]
        # Add other parameters if needed (temperature, max_tokens etc.)
        # "max_tokens": 2048, # Example limit
    }

    try:
        # Use a reasonable timeout (90 seconds)
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=90
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx/5xx)

        response_json = response.json()

        # Extract the content which should be the JSON string
        content_string = response_json.get(
            "choices", [{}]
        )[0].get("message", {}).get("content", "")

        if not content_string:
            raise ValueError(
                "OpenRouter API response did not contain text content.")

        # Replace literal newlines within the string content that might break JSON parsing
        # Also remove potential markdown code block formatting
        if content_string.startswith("```json"):
            content_string = content_string.strip("```json\n ")
        if content_string.endswith("```"):
            content_string = content_string.strip("\n ```")
        content_string = content_string.replace('\n', ' ')
        questions_data = json.loads(content_string)

        # --- Validation (common for both API responses) ---
        if not isinstance(questions_data, list):
            raise ValueError("Generated data is not a list.")
        if len(questions_data) != QUESTIONS_PER_GENERATION:
            print(f"Warning: API generated {len(questions_data)} questions "
                  f"instead of {QUESTIONS_PER_GENERATION}. Using what was "
                  "generated.")
            # Allow partial generation for robustness
        for q in questions_data:
            if not all(k in q for k in ["question", "options", "answer",
                                        "explanation"]):
                raise ValueError(
                    "Generated question object missing required keys.")
            if not isinstance(q["options"], list) or len(q["options"]) != 4:
                raise ValueError(
                    "Generated 'options' is not a list of 4 elements.")
            if not isinstance(q["answer"], int) or not (1 <= q["answer"] <= 4):
                raise ValueError(
                    "Generated 'answer' must be an integer between 1 and 4."
                )
        return questions_data

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to OpenRouter API: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response from OpenRouter API: {e}")
        # Log the problematic content
        print("Received content:",
              content_string if 'content_string' in locals() else response.text)
        return None
    except ValueError as e:
        print(f"Error validating generated data: {e}")
        return None
    except Exception as e:  # Catch unexpected errors
        print(f"An unexpected error occurred during OpenRouter API call: {e}")
        return None


def _generate_via_gemini(api_key, model, difficulty, assist_prompt):
    """Generates questions using the Google Gemini API."""
    # Define the Gemini API endpoint (adjust model name if needed)
    # Make sure the model passed in `model` is compatible with this endpoint
    gemini_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    difficulty_map = {
        "Beginner (A2)": "CEFR A2レベル",
        "Intermediate (B1)": "CEFR B1レベル",
        "Advanced (B2)": "CEFR B2レベル",
    }
    target_level = difficulty_map.get(difficulty, "CEFR B1レベル")

    # Construct the prompt specifically for Gemini
    # Ensure it strongly requests JSON output only
    prompt_text = f"""
    Generate {QUESTIONS_PER_GENERATION} multiple-choice English grammar and
    simple sentence completion questions suitable for English learners at the {target_level}.
    Focus on common grammar points like tenses, phrasal verbs, prepositions,
    articles, and basic sentence structure.

    Provide the output *strictly* as a raw JSON array of objects. Each object must
    have the following keys:
    - "question": The question text (string). For sentence completion, use "..."
                  to indicate the blank.
    - "options": An array of 4 strings representing the choices.
    - "answer": The index (starting from 1) of the correct option in the
                "options" array (integer).
    - "explanation": A brief explanation of why the answer is correct and
                     potentially why others are incorrect (string).
                     **解説内容 (explanation) は日本語で記述してください。**

    {f'Additionally, consider the following request for the questions: {assist_prompt}' if assist_prompt else ''}

    Example format for one question object:
    {{
      "question": "She ___ watching TV when I arrived.",
      "options": ["is", "was", "be", "are"],
      "answer": 2,
      "explanation": "過去進行形 'was watching' を使います。なぜなら、別の過去の動作（到着した）が発生したときに、その動作が進行中だったからです。"
    }}

    Ensure you provide exactly {QUESTIONS_PER_GENERATION} distinct question
    objects in the JSON array. **Output *only* the raw JSON array, with no
    introductory text, code block formatting (like ```json), or closing text.**
    """

    data = {
        "contents": [{
            "role": "user",
            "parts": [{
                "text": prompt_text
            }]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",  # Request JSON output
        }
    }

    try:
        # Add the API key as a query parameter
        response = requests.post(
            f"{gemini_endpoint}?key={api_key}",
            headers={"Content-Type": "application/json"},
            json=data,
            timeout=90
        )
        response.raise_for_status()

        response_json = response.json()

        # Extract the generated text containing the JSON array
        if not response_json.get('candidates'):
            raise ValueError(
                "Gemini API response missing 'candidates'. Response: " + response.text)
        content = response_json['candidates'][0].get('content')
        if not content or not content.get('parts'):
            raise ValueError(
                "Gemini API response missing 'content' or 'parts'. Response: " + response.text)
        content_string = content['parts'][0].get('text', '')

        if not content_string:
            raise ValueError(
                "Gemini API response did not contain text content.")

        # Gemini might still wrap the JSON in ```json ... ```, attempt to remove it
        if content_string.startswith("```json"):
            content_string = content_string.strip("```json\n ")
        if content_string.endswith("```"):
            content_string = content_string.strip("\n ```")

        # Replace literal newlines that might break JSON parsing
        content_string = content_string.replace('\n', ' ')

        questions_data = json.loads(content_string)

        # --- Validation (common for both API responses) ---
        if not isinstance(questions_data, list):
            raise ValueError("Generated data is not a list.")
        if len(questions_data) != QUESTIONS_PER_GENERATION:
            print(f"Warning: API generated {len(questions_data)} questions "
                  f"instead of {QUESTIONS_PER_GENERATION}. Using what was "
                  "generated.")
            # Allow partial generation for robustness
        for q in questions_data:
            if not all(k in q for k in ["question", "options", "answer",
                                        "explanation"]):
                raise ValueError(
                    "Generated question object missing required keys.")
            if not isinstance(q["options"], list) or len(q["options"]) != 4:
                raise ValueError(
                    "Generated 'options' is not a list of 4 elements.")
            if not isinstance(q["answer"], int) or not (1 <= q["answer"] <= 4):
                raise ValueError(
                    "Generated 'answer' must be an integer between 1 and 4."
                )
        return questions_data

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Gemini API: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response from Gemini API: {e}")
        print("Received content string attempt:",
              content_string if 'content_string' in locals() else "Error before extraction")
        print("Raw response:", response.text)
        return None
    except ValueError as e:
        print(
            f"Error validating generated data or Gemini response structure: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during Gemini API call: {e}")
        return None

# --- Main Application Class ---


class EnglishQuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("English Quiz Tool")
        self.root.geometry("600x600")  # Increased height for new controls

        # Load API Key
        load_dotenv()
        self.api_provider = os.getenv("API_PROVIDER", "openrouter").lower()
        self.api_key = None
        self.model_name = None  # Store the actual model name being used

        if self.api_provider == "gemini":
            self.api_key = os.getenv("GEMINI_API_KEY")
            # Use a default gemini model if not specified via OPENROUTER_MODEL
            self.model_name = os.getenv(
                "OPENROUTER_MODEL", "gemini-1.5-flash-latest")  # Or gemini-pro
            if not self.api_key:
                messagebox.showerror(
                    "Error", "API_PROVIDER is 'gemini' but GEMINI_API_KEY not found in .env file.")
                self.root.destroy()
                return
        elif self.api_provider == "openrouter":
            self.api_key = os.getenv("OPENROUTER_API_KEY")
            self.model_name = os.getenv(
                "OPENROUTER_MODEL", "mistralai/mistral-7b-instruct")
            if not self.api_key:
                messagebox.showerror(
                    "Error", "API_PROVIDER is 'openrouter' but OPENROUTER_API_KEY not found in .env file.")
                self.root.destroy()
                return
        else:
            messagebox.showerror(
                "Error", f"Invalid API_PROVIDER '{self.api_provider}' in .env file. Use 'gemini' or 'openrouter'.")
            self.root.destroy()
            return

        # Database connection (only used in main thread)
        try:
            self.conn = sqlite3.connect(DB_NAME)
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            messagebox.showerror(
                "Database Error", f"Could not connect to database: {e}")
            self.root.destroy()
            return

        # State variables
        self.questions = []
        self.current_question_index = -1  # Becomes 0 for first question
        self.score = 0
        self.generating = False  # Flag to prevent concurrent generation
        # Variable to hold the selected radio button value
        self.selected_option = tk.IntVar()
        self.difficulty_var = tk.StringVar(
            value="Intermediate (B1)")  # Default difficulty
        self.prompt_assist_var = tk.StringVar()  # For auxiliary prompt input

        # Setup UI
        self.setup_ui()

        # Make window always on top
        self.root.attributes('-topmost', True)
        # Reassert topmost after interaction (can be annoying, keep commented unless needed)
        # self.root.bind("<FocusOut>", lambda e: self.root.attributes('-topmost', True))
        # self.root.bind("<FocusIn>", lambda e: self.root.attributes('-topmost', True))

        # Load initial state
        self.info_label.config(
            text=f"Click 'Generate New Questions' to start.\n"
            f"Provider: {self.api_provider.capitalize()} | Using model: {self.model_name}"
        )

    def setup_ui(self):
        # Font settings
        default_font = ("Yu Gothic UI", 11)  # Example Japanese-friendly font
        question_font = ("Yu Gothic UI", 14, "bold")
        button_font = ("Yu Gothic UI", 12)
        feedback_font = ("Yu Gothic UI", 12, "bold")

        # Main frame
        main_frame = tk.Frame(self.root, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Top Control Frame ---
        control_frame = tk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # --- Generation Button --- (Moved to its own sub-frame for layout)
        gen_button_frame = tk.Frame(control_frame)
        gen_button_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        self.generate_button = tk.Button(
            gen_button_frame, text="Generate New Questions",
            font=button_font, command=self.start_generation_thread
        )
        self.generate_button.pack(side=tk.LEFT, padx=(0, 10))

        self.info_label = tk.Label(
            gen_button_frame, text="", font=default_font, justify=tk.LEFT
        )
        self.info_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Options Frame (Difficulty and Prompt Assist) ---
        options_frame = tk.Frame(control_frame)
        options_frame.pack(side=tk.TOP, fill=tk.X)

        # Difficulty Selection
        difficulty_label = tk.Label(
            options_frame, text="Difficulty:", font=default_font)
        difficulty_label.pack(side=tk.LEFT, padx=(0, 5))
        difficulty_options = [
            "Beginner (A2)", "Intermediate (B1)", "Advanced (B2)"]
        difficulty_menu = tk.OptionMenu(
            options_frame, self.difficulty_var, *difficulty_options)
        difficulty_menu.config(font=default_font)
        difficulty_menu.pack(side=tk.LEFT, padx=(0, 15))

        # Prompt Assist Input
        prompt_assist_label = tk.Label(
            options_frame, text="Prompt Assist:", font=default_font)
        prompt_assist_label.pack(side=tk.LEFT, padx=(0, 5))
        self.prompt_assist_entry = tk.Entry(
            options_frame, textvariable=self.prompt_assist_var, font=default_font, width=40)
        self.prompt_assist_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Generation Button and Info ---
        # Keep this for reference if needed elsewhere, but controls moved
        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        # --- Middle Section: Question and Options ---
        self.question_label = tk.Label(
            main_frame, text="Press 'Generate New Questions'",
            font=question_font, wraplength=550, justify=tk.LEFT
        )
        self.question_label.pack(pady=(10, 15), anchor='w')

        self.option_buttons = []
        self.radio_buttons = []  # Store radio buttons
        for i in range(4):
            rb = tk.Radiobutton(
                main_frame, text=f"Option {i+1}", variable=self.selected_option,
                value=i + 1, font=button_font, state=tk.DISABLED,
                anchor='w', justify=tk.LEFT,  # Align text left
                command=self.check_answer  # Call check_answer directly on selection
            )
            rb.pack(pady=2, fill=tk.X)  # Reduced padding
            self.radio_buttons.append(rb)

        # --- Bottom Section: Feedback, Explanation, Navigation ---
        self.feedback_label = tk.Label(
            main_frame, text="", font=feedback_font, pady=10
        )
        self.feedback_label.pack()

        # Use a Frame to contain ScrolledText and prevent resizing issues
        explanation_frame = tk.Frame(
            main_frame, height=100)  # Set desired height
        explanation_frame.pack(fill=tk.X, pady=(0, 10))
        # Prevent child widgets from resizing the frame
        explanation_frame.pack_propagate(False)

        self.explanation_area = scrolledtext.ScrolledText(
            explanation_frame, wrap=tk.WORD, font=default_font,
            state=tk.DISABLED, relief=tk.FLAT, bg=self.root.cget('bg')
        )
        # Pack ScrolledText inside the frame
        self.explanation_area.pack(fill=tk.BOTH, expand=True)

        self.next_button = tk.Button(
            main_frame, text="Next Question", font=button_font,
            command=self.next_question, state=tk.DISABLED
        )
        self.next_button.pack(pady=(5, 0))

    def start_generation_thread(self):
        """Starts the question generation in a separate thread."""
        if self.generating:
            return  # Don't start multiple generation threads
        self.generating = True
        self.generate_button.config(state=tk.DISABLED, text="Generating...")
        self.info_label.config(text="Contacting OpenRouter API...")
        self.clear_quiz_area()  # Clear previous state

        # Create and start the thread
        thread = threading.Thread(
            target=self.fetch_questions_worker, daemon=True)
        thread.start()

    def fetch_questions_worker(self):
        """Worker function: Calls API. Result passed back to main thread."""
        api_data = None
        error_message = None
        try:
            print("Fetching questions from API...")
            difficulty = self.difficulty_var.get()
            assist_prompt = self.prompt_assist_var.get().strip()

            # Dispatch to the correct API function based on provider
            if self.api_provider == "gemini":
                api_data = _generate_via_gemini(
                    self.api_key, self.model_name, difficulty, assist_prompt)
            elif self.api_provider == "openrouter":
                api_data = _generate_via_openrouter(
                    self.api_key, self.model_name, difficulty, assist_prompt)
            else:
                # This case should be caught in __init__, but as a safeguard:
                error_message = f"Invalid API provider configured: {self.api_provider}"
                api_data = None

            if not api_data:
                error_message = ("API did not return question data. "
                                 "Check console.")
        except Exception as e:
            print(f"Error in API fetch worker: {e}")
            error_message = f"An error occurred during API call: {e}"

        # Pass result (or error) back to main thread for DB/UI updates
        self.root.after(0, self.handle_generation_result,
                        api_data, error_message)

    def handle_generation_result(self, generated_data, error_message):
        """Handles the result from the generation thread in the main thread."""
        try:
            if error_message:
                messagebox.showerror("Generation Failed", error_message)
                self.info_label.config(
                    text="Generation failed. Please try again.")
            elif generated_data:
                print(f"Successfully fetched {len(generated_data)} questions.")
                if self.save_questions_to_db(generated_data):
                    self.load_questions_from_db()  # Load and display if save was successful
                else:
                    self.info_label.config(
                        text="Failed to save questions. Check logs.")
                    messagebox.showerror(
                        "Error", "Failed to save generated questions to the "
                        "database.")
            elif generated_data is None:  # Handle case where API returns None
                # This case might happen if generate_questions_via_api returns None without error
                messagebox.showerror(
                    "Generation Failed", "Could not generate questions. "
                    "Unknown API issue.")
                self.info_label.config(
                    text="Generation failed. Please try again.")

        except Exception as e:
            # Catch errors during DB save or loading
            print(f"Error handling generation result: {e}")
            messagebox.showerror(
                "Error", f"An error occurred processing results: {e}")
            self.info_label.config(text="An error occurred.")
        finally:
            # Always ensure state is reset and button re-enabled
            self.generation_finished()

    def save_questions_to_db(self, questions_data):
        """Saves generated questions to the DB. Called from main thread."""
        saved_count = 0
        try:
            # Clear old questions before inserting new ones
            self.cursor.execute("DELETE FROM problems")
            self.conn.commit()

            for q in questions_data:
                try:
                    self.cursor.execute("""
                        INSERT INTO problems (question, option1, option2, option3, option4, answer, explanation)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        q['question'], q['options'][0], q['options'][1],
                        q['options'][2], q['options'][3], q['answer'],
                        q['explanation']
                    ))
                    saved_count += 1
                except sqlite3.Error as insert_err:
                    print(f"Error inserting question into DB: {insert_err}\n"
                          f"Data: {q}")
                    # Optionally decide whether to continue or stop on error
            self.conn.commit()
            print(
                f"Saved {saved_count} out of {len(questions_data)} questions "
                "to database.")
            return saved_count > 0  # Indicate success if at least one question saved
        except sqlite3.Error as e:
            print(f"Database error during save: {e}")
            messagebox.showerror(
                "Database Error", f"Failed to save questions to database: {e}")
            # Attempt to rollback changes if commit failed? Might be complex.
            return False  # Indicate failure

    def generation_finished(self):
        """Called from main thread after generation attempt finishes."""
        self.generating = False
        self.generate_button.config(
            state=tk.NORMAL, text="Generate New Questions")
        # Info label is updated by handle_generation_result

    def load_questions_from_db(self):
        """Loads questions from the database. Called from main thread."""
        try:
            self.cursor.execute(
                "SELECT id, question, option1, option2, option3, "
                "option4, answer, explanation FROM problems ORDER BY id"
            )
            rows = self.cursor.fetchall()
            self.questions = []
            for row in rows:
                self.questions.append({
                    "id": row[0],
                    "question": row[1],
                    "options": [row[2], row[3], row[4], row[5]],
                    "answer": row[6],
                    "explanation": row[7]
                })

            if self.questions:
                self.current_question_index = -1  # Reset index
                self.score = 0
                self.info_label.config(
                    text=f"{len(self.questions)} questions loaded. Ready."
                )
                self.next_question()  # Display the first question
            else:
                self.info_label.config(
                    text="No questions found in the database.")
                self.clear_quiz_area()
                # Don't show popup if just generated and saved 0 questions
                # messagebox.showinfo("No Questions", "No questions were loaded.")

        except sqlite3.Error as e:
            messagebox.showerror(
                "Database Error",
                f"Failed to load questions from database: {e}"
            )
            self.clear_quiz_area()

    def display_question(self):
        """Updates the UI to show the current question."""
        if 0 <= self.current_question_index < len(self.questions):
            q = self.questions[self.current_question_index]
            self.question_label.config(
                text=f"{self.current_question_index + 1}. {q['question']}"
            )
            for i, option_text in enumerate(q['options']):
                self.radio_buttons[i].config(
                    text=option_text, state=tk.NORMAL  # Enable and set text
                )
            self.selected_option.set(0)  # Deselect all radio buttons

            self.feedback_label.config(text="")
            self.explanation_area.config(state=tk.NORMAL)
            self.explanation_area.delete('1.0', tk.END)
            self.explanation_area.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)  # Disable 'Next'
        else:
            # This case should ideally be handled by finish_quiz
            print("Warning: display_question called with invalid index.")
            self.clear_quiz_area()

    def check_answer(self):
        """Checks the selected radio button answer, provides feedback."""
        if not (0 <= self.current_question_index < len(self.questions)):
            return  # Should not happen if called via radio button

        selected_option_number = self.selected_option.get()
        if selected_option_number == 0:
            return  # No selection made yet (or called prematurely)

        q = self.questions[self.current_question_index]
        correct_answer = q['answer']

        # Disable option buttons after selection
        for rb in self.radio_buttons:
            rb.config(state=tk.DISABLED)

        is_correct = (selected_option_number == correct_answer)

        if is_correct:
            self.score += 1
            self.feedback_label.config(text="正解！ (Correct!)", fg="green")
            # Highlighting radio buttons directly is less common, feedback label is primary
        else:
            self.feedback_label.config(
                text=f"残念！ (Incorrect!) 正解は {correct_answer}", fg="red"
            )
            # Optionally, you could change the text color of the correct radio button
            # if 1 <= correct_answer <= 4:
            #     self.radio_buttons[correct_answer - 1].config(fg='darkgreen')

        # Display explanation
        self.explanation_area.config(state=tk.NORMAL)
        self.explanation_area.delete('1.0', tk.END)
        self.explanation_area.insert(
            tk.END, f"解説 (Explanation):\n{q['explanation']}"
        )
        self.explanation_area.config(state=tk.DISABLED)

        # Enable the Next button
        self.next_button.config(state=tk.NORMAL)

    def next_question(self):
        """Moves to the next question or finishes the quiz."""
        self.current_question_index += 1
        if self.current_question_index < len(self.questions):
            self.display_question()
        else:
            self.finish_quiz()

    def finish_quiz(self):
        """Displays the final score and resets the quiz area."""
        message = (f"Quiz Finished!\n\n"
                   f"Your score: {self.score} / {len(self.questions)}")
        self.clear_quiz_area(clear_info=False)  # Keep info label
        self.question_label.config(text=message)
        self.info_label.config(text="Generate new questions to play again.")
        self.next_button.config(state=tk.DISABLED)

    def clear_quiz_area(self, clear_info=True):
        """Resets the question, options, feedback, and explanation areas."""
        self.question_label.config(text="")
        for rb in self.radio_buttons:
            rb.config(text="", state=tk.DISABLED)
        self.selected_option.set(0)  # Reset selection
        self.feedback_label.config(text="")
        self.explanation_area.config(state=tk.NORMAL)
        self.explanation_area.delete('1.0', tk.END)
        self.explanation_area.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)
        if clear_info:
            self.info_label.config(text="")

    def on_closing(self):
        """Handles cleanup when the window is closed."""
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
                print("Database connection closed.")
            except sqlite3.Error as e:
                print(f"Error closing database connection: {e}")
        self.root.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    initialize_database()
    root = tk.Tk()
    app = EnglishQuizApp(root)
    # Handle closing cleanly
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
