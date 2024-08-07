from fasthtml.common import *
import random
import time
import requests
import os
import re
import json
from gtts import gTTS
from gtts.lang import tts_langs
import base64

MAX_ITEMS = 180

app = FastHTML()
rt = app.route

SETTINGS_FILE = 'game_settings.json'

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return None

def get_tts_lang_code(language):
    language = language.lower()
    available_langs = tts_langs()

    # Direct mapping for common languages and their variants
    direct_map = {
        'afrikaans': 'af',
        'arabic': 'ar',
        'bengali': 'bn',
        'bosnian': 'bs',
        'catalan': 'ca',
        'czech': 'cs',
        'welsh': 'cy',
        'danish': 'da',
        'german': 'de',
        'greek': 'el',
        'english': 'en',
        'spanish': 'es',
        'estonian': 'et',
        'basque': 'eu',
        'finnish': 'fi',
        'french': 'fr',
        'galician': 'gl',
        'gujarati': 'gu',
        'hindi': 'hi',
        'croatian': 'hr',
        'hungarian': 'hu',
        'indonesian': 'id',
        'icelandic': 'is',
        'italian': 'it',
        'hebrew': 'iw',
        'japanese': 'ja',
        'javanese': 'jw',
        'khmer': 'km',
        'kannada': 'kn',
        'korean': 'ko',
        'latin': 'la',
        'lithuanian': 'lt',
        'latvian': 'lv',
        'malayalam': 'ml',
        'marathi': 'mr',
        'malay': 'ms',
        'burmese': 'my',
        'nepali': 'ne',
        'dutch': 'nl',
        'norwegian': 'no',
        'punjabi': 'pa',
        'polish': 'pl',
        'portuguese': 'pt',
        'romanian': 'ro',
        'russian': 'ru',
        'sinhala': 'si',
        'slovak': 'sk',
        'albanian': 'sq',
        'serbian': 'sr',
        'sundanese': 'su',
        'swedish': 'sv',
        'swahili': 'sw',
        'tamil': 'ta',
        'telugu': 'te',
        'thai': 'th',
        'filipino': 'tl',
        'turkish': 'tr',
        'ukrainian': 'uk',
        'urdu': 'ur',
        'vietnamese': 'vi',
        'chinese': 'zh',
        'chinese (simplified)': 'zh-CN',
        'chinese (traditional)': 'zh-TW',
        'chinese (mandarin)': 'zh',
    }

    # Check for exact match in direct map
    if language in direct_map:
        return direct_map[language]

    # Check for partial match in direct map
    for lang, code in direct_map.items():
        if language in lang or lang in language:
            return code

    # Try to find a match in available languages
    for code, lang in available_langs.items():
        if language.lower() in lang.lower():
            return code

    # If no match found, default to English
    print(f"Warning: Could not find TTS language code for '{language}'. Defaulting to English.")
    return 'en'


class GameState:
    def __init__(self):
        settings = load_settings()
        if settings:
            self.api_key = settings.get('api_key', "")
            self.language = settings.get('language', "Japanese")
            self.native_language = settings.get('native_language', "English")
            self.level = settings.get('level', "N1")
            self.n_items = settings.get('n_items', 60)
            self.theme = settings.get('theme', "")
            self.mode = settings.get('mode', "vocab")
            self.time_limit = settings.get('time_limit', 180)
            self.max_lives = settings.get('max_lives', 3)
            self.show_readings = settings.get('show_readings', True)
            self.use_tts = settings.get('use_tts', False)
        else:
            self.api_key = ""
            self.language = "Japanese"
            self.native_language = "English"
            self.level = "N1"
            self.n_items = 60
            self.theme = ""
            self.mode = "vocab"
            self.time_limit = 180
            self.max_lives = 3
            self.show_readings = True
            self.use_tts = False

        self.reset_game_state()

    def reset_game_state(self):
        self.time_left = self.time_limit
        self.lives = self.max_lives
        self.score = 0
        self.seen_items = set()
        self.current_pair = None
        self.is_correct_order = True
        self.is_correct_pair = True
        self.last_update_time = None
        self.game_over = False
        self.game_started = False
        self.pairs = []
        self.final_score = None

    def update_settings(self, api_key, language, native_language, level, n_items, theme, mode, time_limit, max_lives, show_readings, use_tts):
        self.api_key = api_key
        self.language = language
        self.native_language = native_language
        self.level = level
        self.n_items = n_items
        self.theme = theme
        self.mode = mode
        self.time_limit = time_limit
        self.max_lives = max_lives
        self.show_readings = show_readings
        self.use_tts = use_tts
        settings = {
            'api_key': api_key,
            'language': language,
            'native_language': native_language,
            'level': level,
            'n_items': n_items,
            'theme': theme,
            'mode': mode,
            'time_limit': time_limit,
            'max_lives': max_lives,
            'show_readings': show_readings,
            'use_tts': use_tts
        }
        save_settings(settings)

game_state = GameState()

def generate_pairs(api_key, language, native_language, level, n_items, theme, mode, show_readings):
    n_items = min(n_items, MAX_ITEMS)
    theme_prompt = f" related to the theme '{theme}'" if theme else ""
    reading_prompt = ", its reading," if show_readings else ""

    if mode == "vocab":
        prompt = f"Generate {n_items} {language} {level} difficulty vocabulary pairs{theme_prompt}. Each pair should consist of a {language} word{reading_prompt} and its {native_language} meaning. Format each pair as: {language} word{'|reading' if show_readings else ''}|meaning. Your response must have no other text."
    else:
        prompt = f"Generate {n_items} {language} {level} difficulty sentence pairs{theme_prompt}. Each pair should consist of a {language} sentence{reading_prompt} and its {native_language} translation. Format each pair as: {language} sentence{'| reading' if show_readings else ''}|{native_language} translation. Your response must have no other text."

    print('prompt: ',api_key)
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
    )
    print('response', response)
    generated_text = response.json()['choices'][0]['message']['content']
    pairs = [line.strip() for line in generated_text.split('\n') if line.strip()]
    pairs = [re.sub(r'^\d+\.\s*', '', pair) for pair in pairs]

    return [pair.split('|') for pair in pairs]

def update_time():
    if not game_state.game_started:
        return False
    current_time = time.time()
    elapsed = current_time - game_state.last_update_time
    game_state.time_left = max(0, game_state.time_left - elapsed)
    game_state.last_update_time = current_time
    if game_state.time_left <= 0 or game_state.lives <= 0:
        game_state.game_over = True
        game_state.final_score = game_state.score
        return True
    return False

def word_swap(sentence):
    # Count the number of spaces
    space_count = sentence.count(' ')

    if space_count > 1:
        # If there's more than one space, treat as a space-separated sentence
        # Split the sentence into words, preserving punctuation
        words_with_punct = re.findall(r'\S+|\s+', sentence)
        words = [word for word in words_with_punct if word.strip() and not word.isspace()]

        if len(words) > 1:
            # Choose two random indices to swap
            idx1, idx2 = random.sample(range(len(words)), 2)
            # Swap the words
            words[idx1], words[idx2] = words[idx2], words[idx1]

            # Reconstruct the sentence, preserving original spacing and punctuation
            result = []
            word_iter = iter(words)
            for item in words_with_punct:
                if item.strip() and not item.isspace():
                    result.append(next(word_iter))
                else:
                    result.append(item)
            return ''.join(result)
        else:
            return sentence  # Return original if only one word
    else:
        # For languages without word spaces or single words
        chars = re.findall(r'\w', sentence)

        if len(chars) > 1:
            # Choose two random indices to swap
            idx1, idx2 = random.sample(range(len(chars)), 2)

            # Swap the characters
            chars[idx1], chars[idx2] = chars[idx2], chars[idx1]

            # Reconstruct the sentence with swapped characters
            char_iter = iter(chars)
            return ''.join(next(char_iter) if c.isalnum() else c for c in sentence)
        else:
            return sentence  # Return original if too short to swap

def get_new_pair():
    unseen_pairs = [pair for pair in game_state.pairs if pair[0] not in game_state.seen_items]
    total_pairs = len(game_state.pairs)
    unseen_ratio = len(unseen_pairs) / total_pairs

    # Ensure at least 1 in 4 chance of new pair, but not lower than the actual unseen ratio
    new_pair_probability = max(0.25, unseen_ratio)

    if unseen_pairs and random.random() < new_pair_probability:
        # Show a new pair
        new_pair = random.choice(unseen_pairs)
        game_state.is_correct_pair = True
        game_state.is_correct_order = True
    else:
        # Show a seen pair
        seen_pairs = [pair for pair in game_state.pairs if pair[0] in game_state.seen_items]
        if not seen_pairs:  # If somehow all pairs are unseen, choose from all pairs
            seen_pairs = game_state.pairs
        seen_pair = random.choice(seen_pairs)

        if random.random() < 0.5:  # 50% chance of showing a correct pair
            new_pair = seen_pair
            game_state.is_correct_pair = True
            game_state.is_correct_order = True
        else:
            if game_state.mode == "sentence":
                new_pair = [word_swap(seen_pair[0])] + seen_pair[1:]
                game_state.is_correct_pair = True
                game_state.is_correct_order = False
            else:  # vocab mode
                wrong_translation = random.choice([p[-1] for p in game_state.pairs if p != seen_pair])
                new_pair = seen_pair[:-1] + [wrong_translation]
                game_state.is_correct_pair = False
                game_state.is_correct_order = True

    return new_pair

def format_time(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}:{seconds:02d}"


def generate_tts(text, language):
    lang_code = get_tts_lang_code(language)
    tts = gTTS(text=text, lang=lang_code)
    audio_file = f"temp_audio_{time.time()}.mp3"
    tts.save(audio_file)
    with open(audio_file, "rb") as audio:
        audio_data = base64.b64encode(audio.read()).decode('utf-8')
    os.remove(audio_file)
    return f"data:audio/mp3;base64,{audio_data}"

def render_game_content():
    if update_time() or game_state.game_over:
        return render_start_screen()

    if not game_state.current_pair:
        game_state.current_pair = get_new_pair()

    if game_state.mode == "vocab":
        if game_state.show_readings and len(game_state.current_pair) > 2:
            item, reading, translation = game_state.current_pair
        else:
            item, translation = game_state.current_pair
            reading = ""
        buttons = [
            Button("Seen (F)", hx_post="/answer/seen", id="seen-btn"),
            Button("New (Space)", hx_post="/answer/new", id="new-btn"),
            Button("Wrong Pair (J)", hx_post="/answer/wrong_pair", id="wrong-pair-btn")
        ]
    else:  # sentence mode
        if game_state.show_readings and len(game_state.current_pair) > 2:
            item, reading, translation = game_state.current_pair
        else:
            item, translation = game_state.current_pair
            reading = ""
        buttons = [
            Button("Seen (F)", hx_post="/answer/seen", id="seen-btn"),
            Button("New (Space)", hx_post="/answer/new", id="new-btn"),
            Button("Wrong Order (J)", hx_post="/answer/wrong_order", id="wrong-order-btn")
        ]

    audio_element = ""
    if game_state.use_tts:
        audio_src = generate_tts(item, game_state.language)
        audio_element = f'<audio id="tts-audio" autoplay><source src="{audio_src}" type="audio/mp3"></audio>'

    return (
        Div(
            Div(format_time(game_state.time_left), id="timer", style="font-size: 24px; font-weight: bold;"),
            Div("X" * game_state.lives, id="lives", style="font-size: 20px;"),
            Div(str(game_state.score), id="score", style="font-size: 18px;"),
            style="text-align: center; margin-bottom: 20px;"
        ),
        Div(reading, id="reading", style="font-size: 18px; margin-bottom: 10px; text-align: center;"),
        Div(item, id="item", style="font-size: 24px; margin: 20px 0; text-align: center;"),
        Div(translation, id="translation", style="text-align: center;"),
        Div(*buttons, style="margin-top: 20px; text-align: center;", id="buttons"),
        Div(NotStr(audio_element), id="audio-container")
    )

def render_start_screen():
    score_display = Div(f"Final Score: {game_state.final_score}", style="text-align: center; font-size: 24px; margin-bottom: 20px;") if game_state.final_score is not None else Div()

    return (
        Form(
            score_display,
            Div(
                Label("OpenAI API Key:", for_="api_key"),
                Input(id="api_key", name="api_key", value=game_state.api_key),
                style="margin-bottom: 20px;"
            ),
            Div(
                Label("Language:", for_="language"),
                Input(type="text", id="language", name="language", value=game_state.language),
                style="margin-bottom: 10px;"
            ),
            Div(
                Label("Native Language:", for_="native_language"),
                Input(type="text", id="native_language", name="native_language", value=game_state.native_language),
                style="margin-bottom: 10px;"
            ),
            Div(
                Label("Level:", for_="level"),
                Input(type="text", id="level", name="level", value=game_state.level),
                style="margin-bottom: 10px;"
            ),
            Div(
                Label("Number of Items:", for_="n_items"),
                Input(type="number", id="n_items", name="n_items", value=str(game_state.n_items)),
                style="margin-bottom: 10px;"
            ),
            Div(
                Label("Theme (optional):", for_="theme"),
                Input(type="text", id="theme", name="theme", value=game_state.theme),
                style="margin-bottom: 10px;"
            ),
            Div(
                Label("Time Limit (seconds):", for_="time_limit"),
                Input(type="number", id="time_limit", name="time_limit", value=str(game_state.time_limit)),
                style="margin-bottom: 10px;"
            ),
            Div(
                Label("Number of Lives:", for_="max_lives"),
                Input(type="number", id="max_lives", name="max_lives", value=str(game_state.max_lives)),
                style="margin-bottom: 10px;"
            ),
            Div(
                Label("Show Readings:", for_="show_readings"),
                Input(type="checkbox", id="show_readings", name="show_readings", checked=game_state.show_readings, value="on"),
                style="margin-bottom: 10px;"
            ),
            Div(
                Label("Use Text-to-Speech:", for_="use_tts"),
                Input(type="checkbox", id="use_tts", name="use_tts", checked=game_state.use_tts, value="on"),
                style="margin-bottom: 20px;"
            ),
            Div(
                Label("Mode:", for_="mode"),
                Select(
                    Option("Vocabulary", value="vocab", selected=(game_state.mode == "vocab")),
                    Option("Sentences", value="sentence", selected=(game_state.mode == "sentence")),
                    id="mode", name="mode"
                ),
                style="margin-bottom: 10px;"
            ),
            Button("Start Game", hx_post="/start_game", id="start-game-btn"),
            style="text-align: center; margin-top: 50px;"
        ),
    )

@rt("/")
def get():
    return Titled("Language Memory Game",
        Container(
            Div(id="game-content", *render_start_screen()),
            Script("""
                function updateGame() {
                    if (document.getElementById('timer')) {
                        htmx.ajax('GET', '/update_timer', '#timer');
                    }
                }
                setInterval(updateGame, 1000);

                function startOrRestartGame() {
                    const startButton = document.getElementById('start-game-btn');
                    if (startButton) {
                        startButton.click();
                    }
                }

                document.addEventListener('keydown', function(event) {
                    if (!document.getElementById('timer')) {
                        if (event.key === 'Enter') {
                            startOrRestartGame();
                        }
                    } else {
                        if (event.key === 'f') {
                            document.getElementById('seen-btn')?.click();
                        } else if (event.key === ' ') {
                            event.preventDefault();
                            document.getElementById('new-btn')?.click();
                        } else if (event.key === 'j') {
                            document.getElementById('wrong-order-btn')?.click() || document.getElementById('wrong-pair-btn')?.click();
                        }
                    }
                });
            """)
        )
    )

@rt("/start_game")
def post(
    api_key: str,
    language: str,
    native_language: str,
    level: str,
    n_items: int,
    theme: str,
    mode: str,
    time_limit: int,
    max_lives: int,
    show_readings: str = "off",
    use_tts: str = "off"
):
    global game_state

    # Convert show_readings and use_tts to boolean
    show_readings = show_readings.lower() == "on"
    use_tts = use_tts.lower() == "on"

    # Update settings
    game_state.update_settings(api_key, language, native_language, level, n_items, theme, mode, time_limit, max_lives, show_readings, use_tts)

    # Reset game state and generate new pairs
    game_state.reset_game_state()
    game_state.pairs = generate_pairs(api_key, language, native_language, level, n_items, theme, mode, show_readings)
    game_state.game_started = True
    game_state.last_update_time = time.time()

    return Div(id="game-content", hx_swap_oob="true", *render_game_content())

@rt("/reset")
def post():
    global game_state
    game_state.final_score = None
    game_state.reset_game_state()
    return Div(id="game-content", hx_swap_oob="true", *render_start_screen())

@rt("/answer/{choice}")
def post(choice: str):
    if game_state.game_over:
        return Div(id="game-content", hx_swap_oob="true", *render_start_screen())

    if update_time():
        return Div(id="game-content", hx_swap_oob="true", *render_start_screen())

    if choice == "seen":
        if game_state.current_pair[0] in game_state.seen_items and game_state.is_correct_pair:
            game_state.score += 1
        else:
            game_state.lives -= 1
            game_state.time_left = max(0, game_state.time_left - 10)
    elif choice == "new":
        if game_state.current_pair[0] not in game_state.seen_items and game_state.is_correct_pair:
            game_state.score += 1
        else:
            game_state.lives -= 1
            game_state.time_left = max(0, game_state.time_left - 10)
    elif choice == "wrong_pair":
        if game_state.mode == "vocab" and not game_state.is_correct_pair:
            game_state.score += 1
        else:
            game_state.lives -= 1
            game_state.time_left = max(0, game_state.time_left - 10)
    elif choice == "wrong_order":
        if game_state.mode == "sentence" and not game_state.is_correct_order:
            game_state.score += 1
        else:
            game_state.lives -= 1
            game_state.time_left = max(0, game_state.time_left - 10)

    game_state.seen_items.add(game_state.current_pair[0])
    game_state.current_pair = get_new_pair()
    return Div(id="game-content", hx_swap_oob="true", *render_game_content())

@rt("/update_timer")
def get():
    if not game_state.game_started:
        return ""
    if update_time():
        return Div(id="game-content", hx_swap_oob="true", *render_start_screen())
    return Div(format_time(game_state.time_left), id="timer", style="font-size: 24px; font-weight: bold;")

serve()
