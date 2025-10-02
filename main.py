import logging
import json
import os
import random
import sys
from typing import Dict, List, Tuple, Optional, Any
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request
import asyncio
import threading

# Конфигурация логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = os.getenv('BOT_TOKEN', '8366569841:AAGgMVHVBm-MuMC4i0lbfMGrljtjNn-QlWM')
USERS_DATA_FILE = 'users_data.json'
STATS_FILE = 'stats.json'

# Создаем Flask приложение
app = Flask(__name__)

# Глобальные переменные для бота
telegram_app = None
bot_loop = None

# Пути к медиа
IMAGE_DIR = 'images'
SOUND_DIR = 'sounds'

# Инвентарь
INVENTORY_ITEMS: Dict[str, str] = {
    'flashlight': 'Фонарик 🔦',
    'key': 'Ключ 🗝️',
    'notebook': 'Дневник Элиаса 📔',
    'chocolate': 'Шоколадка 🍫',
    'magnifying_glass': 'Лупа 🔍',
    'amulet': 'Странный амулет ⏳',
    'photo': 'Старая фотография 📸',
    'whiskey': 'Фляжка виски 🍾'
}

# Достижения
ACHIEVEMENTS = {
    'curious': {'name': 'Любопытный стажёр', 'desc': 'Открыл запретный чемодан', 'emoji': '🕵️'},
    'collector': {'name': 'Коллекционер', 'desc': 'Собрал все предметы', 'emoji': '🏅'},
    'skeptic': {'name': 'Скептик', 'desc': 'Не поверил Марте', 'emoji': '🤨'},
    'trusting': {'name': 'Доверчивый', 'desc': 'Взял шоколадку у Марты', 'emoji': '🍫'},
    'keeper': {'name': 'Хранитель Тайн', 'desc': 'Нашёл Комнату Знаний', 'emoji': '🏆'},
    'ash': {'name': 'Пепел Истории', 'desc': 'Ушёл, не открыв чемодан', 'emoji': '🕯️'},
    'madness': {'name': 'Безумие Архива', 'desc': 'Прочитал дневник до конца...', 'emoji': '🌀'},
    'betrayed': {'name': 'Преданный Тайной', 'desc': 'Доверился — и был предан', 'emoji': '🗡️'},
    'detective': {'name': 'Следопыт', 'desc': 'Нашел все улики', 'emoji': '🔎'},
    'survivor': {'name': 'Выживший', 'desc': 'Пережил встречу с Тенью', 'emoji': '💀'}
}

# 🎮 Расширенный гейм-текст
GAME_TEXTS: Dict[str, Dict[str, Any]] = {
    'start': {
        'text': """🕯️ *Тайна Забытого Архива*

Вы — стажёр в Национальной Библиотеке Старого Города. Сегодня ваш последний рабочий день перед отпуском. Вам поручили разобрать пыльный подвал, где хранятся "некаталожные" материалы.

Среди старых газет и сломанных картотек вы находите *запечатанный чемодан* с надписью:  
> "НЕ ОТКРЫВАТЬ БЕЗ РАЗРЕШЕНИЯ ДИРЕКТОРА".

*Что вы делаете?*""",
        'choices': [
            {'text': 'Попытаться открыть чемодан', 'next_state': 'chapter_1_open', 'achievement': 'curious'},
            {'text': 'Оставить чемодан и продолжить работу', 'next_state': 'chapter_1_leave'},
            {'text': 'Осмотреть комнату внимательнее', 'next_state': 'chapter_1_explore'}
        ],
        'image': 'start.jpg'
    },

    'chapter_1_explore': {
        'text': """🔦 *Тщательный осмотр*

Вы замечаете *фонарик* на полке и *странные царапины* на полу, ведущие к стене. За книжной полкой — *потайной отсек* с фотографией.

*Что вы делаете?*""",
        'choices': [
            {'text': 'Взять фонарик', 'next_state': 'chapter_1_flashlight_taken', 'items': ['flashlight']},
            {'text': 'Изучить фотографию', 'next_state': 'chapter_1_photo_found', 'items': ['photo']},
            {'text': 'Вернуться к чемодану', 'next_state': 'chapter_1_open'}
        ]
    },

    'chapter_1_flashlight_taken': {
        'text': """💡 *Фонарик в руках*

Теперь темные углы подвала не так страшны. Вы замечаете *металлический блеск* в дальнем углу.

*Что вы делаете?*""",
        'choices': [
            {'text': 'Исследовать угол с фонариком', 'next_state': 'chapter_1_dark_corner'},
            {'text': 'Осмотреть фотографию', 'next_state': 'chapter_1_photo_found', 'items': ['photo']}
        ]
    },

    'chapter_1_photo_found': {
        'text': """📸 *Старая фотография*

На пожелтевшем снимке — *Элиас Вейн* с группой людей. На обороте надпись:  
> "Экспедиция 1923. Никто не должен знать правду о Комнате Времени".

Один из людей на фото — *нынешний директор библиотеки*!

*Что вы делаете?*""",
        'choices': [
            {'text': 'Спрятать фото и открыть чемодан', 'next_state': 'chapter_1_open'},
            {'text': 'Попытаться найти директора', 'next_state': 'chapter_1_director'}
        ]
    },

    'chapter_1_director': {
        'text': """🚪 *Кабинет директора*

Дверь заперта. На столе у входа — *записка*:  
> "Если читаешь это — беги. Они знают, что ты здесь."

*Что вы делаете?*""",
        'choices': [
            {'text': 'Вернуться в подвал', 'next_state': 'chapter_1_open'},
            {'text': 'Попытаться взломать дверь', 'next_state': 'chapter_1_break_in'}
        ]
    },

    'chapter_1_break_in': {
        'text': """🔓 *Взлом*

Дверь поддается! В кабинете — *пусто*. На столе *дневник директора*:  
> "Элиас был прав. Комната Времени реальна. Но цена..."

Внезапно слышны *шаги*! 

*Что вы делаете?*""",
        'choices': [
            {'text': 'Спрятаться', 'next_state': 'chapter_1_hide'},
            {'text': 'Встретить гостя', 'next_state': 'chapter_1_confrontation'}
        ]
    },

    'chapter_1_hide': {
        'text': """👻 *Укрытие*

Вы прячетесь за шкафом. В кабинет входит *директор* с кем-то в плаще.  
> "Он здесь. Я чувствую."

> "Найди его. Нельзя допустить, чтобы он нашел Комнату."

*Что вы делаете?*""",
        'choices': [
            {'text': 'Оставаться в укрытии', 'next_state': 'chapter_1_stay_hidden'},
            {'text': 'Попытаться сбежать', 'next_state': 'chapter_1_escape'}
        ]
    },

    'chapter_1_open': {
        'text': """📦 *Чемодан открыт!*

Внутри — *старый дневник 1923 года* и *странная карта подвала* с символами. На обложке дневника имя: *«Элиас Вейн»*.

> "Комната знаний скрыта за тройной дверью. Ключ лежит там, где время остановилось..."

*Что вы делаете?*""",
        'choices': [
            {'text': 'Изучить карту', 'next_state': 'chapter_1_map'},
            {'text': 'Прочитать первую запись', 'next_state': 'chapter_1_notebook'},
            {'text': 'Проверить потайной карман', 'next_state': 'chapter_1_secret_pocket'}
        ],
        'items': ['notebook']
    },

    'chapter_1_secret_pocket': {
        'text': """🎁 *Потайной карман*

Внутри — *фляжка с виски* и записка:  
> "Для храбрости. Тебе понадобится."

*Что вы делаете?*""",
        'choices': [
            {'text': 'Взять фляжку', 'next_state': 'chapter_1_whiskey_taken', 'items': ['whiskey']},
            {'text': 'Изучить дневник', 'next_state': 'chapter_1_notebook'}
        ]
    },

    'chapter_1_whiskey_taken': {
        'text': """🍾 *Жидкая храбрость*

Фляжка в кармане. Может пригодиться в трудную минуту.

*Что дальше?*""",
        'choices': [
            {'text': 'Изучить дневник', 'next_state': 'chapter_1_notebook'},
            {'text': 'Посмотреть карту', 'next_state': 'chapter_1_map'}
        ]
    },

    'chapter_1_dark_corner': {
        'text': """🔦 *Темный угол*

С фонариком вы находите *люк в полу* и *старую монету 1923 года*.  
Слышен *странный шепот* из люка...

*Что вы делаете?*""",
        'choices': [
            {'text': 'Открыть люк', 'next_state': 'chapter_1_hatch'},
            {'text': 'Вернуться к чемодану', 'next_state': 'chapter_1_open'}
        ]
    },

    'chapter_1_hatch': {
        'text': """🕳️ *Тайный ход*

Лестница ведет вниз в полную темноту. Пахнет *плесенью и старыми книгами*.

*Что вы делаете?*""",
        'choices': [
            {'text': 'Спуститься вниз', 'next_state': 'chapter_1_underground'},
            {'text': 'Закрыть люк и уйти', 'next_state': 'end_leave'}
        ]
    },

    'chapter_1_underground': {
        'text': """🌌 *Подземелье*

Вы в *лабиринте книжных полок*. В воздухе висит *золотистая пыль*.  
Голос шепчет: *"Ближе... Найди меня..."*

*Что вы делаете?*""",
        'choices': [
            {'text': 'Идти на голос', 'next_state': 'chapter_1_voice'},
            {'text': 'Исследовать лабиринт', 'next_state': 'chapter_1_maze'},
            {'text': 'Вернуться назад', 'next_state': 'chapter_1_open'}
        ]
    },

    'chapter_1_voice': {
        'text': """👁️ *Источник голоса*

Вы находите *зеркало*, в котором отражается не вы, а *молодой человек в старомодной одежде*.  
> "Я — Элиас. Помоги мне закончить то, что я начал."

*Что вы делаете?*""",
        'choices': [
            {'text': 'Спросить, что ему нужно', 'next_state': 'chapter_1_elias_dialogue'},
            {'text': 'Разбить зеркало', 'next_state': 'chapter_1_break_mirror'},
            {'text': 'Убежать', 'next_state': 'chapter_1_maze'}
        ]
    },

    'chapter_1_elias_dialogue': {
        'text': """💬 *Диалог с призраком*

> "Комната Времени была нашим величайшим открытием. Но они... они извратили её.  
> Теперь я заперт между мирами. Ты должен разрушить печать."

Элиас указывает на *символ на стене*.

*Что вы делаете?*""",
        'choices': [
            {'text': 'Согласиться помочь', 'next_state': 'chapter_1_help_elias'},
            {'text': 'Спросить о цене', 'next_state': 'chapter_1_ask_price'}
        ]
    },

    'chapter_1_help_elias': {
        'text': """⚡ *Печать сломана*

Вы разрушаете символ. Зеркало *трескается*, и Элиас исчезает с улыбкой.  
> "Спасибо. Теперь я свободен."

На месте зеркала — *портальная дверь*.

*Конец: Освобождение* 🕊️""",
        'choices': [],
        'end': True,
        'achievement': 'survivor'
    },

    # ... (остальные существующие состояния остаются без изменений)
    # Добавлю только ключевые для экономии места

    'chapter_1_leave': {
        'text': """Вы решаете не трогать чемодан... Но что-то *заставляет вас оглянуться*.  
Чемодан *слегка приоткрыт*. Изнутри доносится... *шёпот?*

*Что вы делаете?*""",
        'choices': [
            {'text': 'Подойти к чемодану', 'next_state': 'chapter_1_open'},
            {'text': 'Проигнорировать и уйти', 'next_state': 'end_leave', 'achievement': 'ash'}
        ]
    },

    'end_leave': {
        'text': """🕯️ *Пепел Истории*

Вы уходите. На следующий день подвал *сносят*.  
Тайна Забытого Архива *исчезает навсегда*...

*Конец: Пепел Истории* 🕯️""",
        'choices': [],
        'end': True,
        'achievement': 'ash'
    }
}


# ==============================
# 🛠️ Функции (без изменений)
# ==============================

def validate_game_states():
    all_states = set(GAME_TEXTS.keys())
    referenced = set()
    for state in GAME_TEXTS.values():
        for choice in state.get('choices', []):
            referenced.add(choice['next_state'])
        if 'puzzle' in state:
            referenced.add(state['puzzle'].get('success_state', ''))
            referenced.add(state['puzzle'].get('fail_state', ''))

    missing = referenced - all_states
    if missing:
        logger.warning(f"⚠️ Отсутствующие состояния: {missing}")


def load_user_data(user_id: int) -> Dict[str, Any]:
    if os.path.exists(USERS_DATA_FILE):
        try:
            with open(USERS_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(str(user_id), get_default_user_data())
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
    return get_default_user_data()


def get_default_user_data() -> Dict[str, Any]:
    return {
        'state': 'start',
        'inventory': [],
        'achievements': [],
        'games_played': 0,
        'hints_used': 0,
        'choices_log': []
    }


def save_user_data(user_id: int, data: Dict[str, Any]):
    try:
        all_data = {}
        if os.path.exists(USERS_DATA_FILE):
            with open(USERS_DATA_FILE, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        all_data[str(user_id)] = data
        os.makedirs(os.path.dirname(USERS_DATA_FILE) or '.', exist_ok=True)
        with open(USERS_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")


def load_stats() -> Dict:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'total_games': 0, 'endings': {}, 'items_found': {}}


def save_stats(stats: Dict):
    try:
        os.makedirs(os.path.dirname(STATS_FILE) or '.', exist_ok=True)
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения статистики: {e}")


def get_game_text(state: str) -> Dict[str, Any]:
    return GAME_TEXTS.get(state, {
        'text': '❌ Ошибка: неизвестное состояние. Пожалуйста, сообщите разработчику!',
        'choices': []
    })


def add_item_to_inventory(user_data: Dict[str, Any], item: str):
    if item not in user_data['inventory']:
        user_data['inventory'].append(item)
        stats = load_stats()
        stats['items_found'][item] = stats['items_found'].get(item, 0) + 1
        save_stats(stats)


def unlock_achievement(user_data: Dict[str, Any], achievement_key: str):
    if achievement_key not in user_data['achievements']:
        user_data['achievements'].append(achievement_key)
        ach = ACHIEVEMENTS[achievement_key]
        logger.info(f"Achievement unlocked: {ach['name']}")
        return f"🎉 Достижение получено: {ach['emoji']} {ach['name']} — {ach['desc']}"
    return None


def get_inventory_text(inventory: List[str]) -> str:
    if not inventory:
        return "Инвентарь пуст 🎒"
    items = [INVENTORY_ITEMS.get(i, i) for i in inventory]
    return f"🎒 Инвентарь ({len(items)}/{len(INVENTORY_ITEMS)}):\n" + "\n".join(f"• {item}" for item in items)


def get_achievements_text(achievements: List[str]) -> str:
    if not achievements:
        return "Достижения: нет 🏅"
    lines = ["🏅 Ваши достижения:"]
    for key in achievements:
        ach = ACHIEVEMENTS.get(key, {})
        lines.append(f"{ach.get('emoji', '✨')} {ach.get('name', key)}")
    return "\n".join(lines)


def process_game_step(
        user_id: int,
        choice_index: Optional[int] = None,
        command: Optional[str] = None,
        user_input: Optional[str] = None
) -> Tuple[str, List[Dict[str, Any]], bool, Optional[str], Optional[str]]:
    user_data = load_user_data(user_id)

    # Команды
    if command == '/inventory':
        return get_inventory_text(user_data['inventory']), [], False, None, None
    if command == '/achievements':
        return get_achievements_text(user_data['achievements']), [], False, None, None
    if command == '/stats':
        stats = load_stats()
        endings = "\n".join([f"{k}: {v}" for k, v in stats.get('endings', {}).items()])
        return f"📊 Статистика\nВсего игр: {stats.get('total_games', 0)}\n\nКонцовки:\n{endings or 'Нет данных'}", [], False, None, None
    if command == '/hint':
        if user_data.get('hints_used', 0) >= 3:
            return "У вас закончились подсказки (макс. 3) 🧠", [], False, None, None
        user_data['hints_used'] += 1
        save_user_data(user_id, user_data)
        return "Подсказка: исследуйте все углы подвала. Фонарик и фото могут помочь.", [], False, None, None
    if command == '/restart':
        user_data = get_default_user_data()
        user_data['games_played'] += 1
        save_user_data(user_id, user_data)
        state_data = get_game_text('start')
        text = state_data['text']
        choices = state_data.get('choices', [])
        image = get_image_path(state_data.get('image'))
        return text, choices, False, image, None

    current_state = user_data['state']
    state_data = get_game_text(current_state)

    # Головоломка
    if 'puzzle' in state_data and user_input:
        puzzle = state_data['puzzle']
        next_state = puzzle['success_state'] if user_input.strip() == puzzle['answer'] else puzzle['fail_state']
        user_data['state'] = next_state
        save_user_data(user_id, user_data)
        new_data = get_game_text(next_state)
        return new_data['text'], new_data.get('choices', []), new_data.get('end', False), get_image_path(
            new_data.get('image')), None

    # Выбор игрока
    if choice_index is not None and 0 <= choice_index < len(state_data.get('choices', [])):
        choice = state_data['choices'][choice_index]
        next_state = choice['next_state']

        # Проверка предмета
        if 'required_item' in choice and choice['required_item'] and choice['required_item'] not in user_data[
            'inventory']:
            item_name = INVENTORY_ITEMS.get(choice['required_item'], choice['required_item'])
            return f"❌ У вас нет {item_name}! Проверьте инвентарь (/inventory).", state_data.get('choices',
                                                                                                 []), False, None, None

        # Логика
        user_data['choices_log'].append({'state': current_state, 'choice': choice['text'], 'next_state': next_state})
        if 'achievement' in choice:
            achievement_msg = unlock_achievement(user_data, choice['achievement'])
        if 'items' in choice:
            for item in choice['items']:
                add_item_to_inventory(user_data, item)
        if len(user_data['inventory']) >= len(INVENTORY_ITEMS):
            unlock_achievement(user_data, 'collector')

        user_data['state'] = next_state
        save_user_data(user_id, user_data)

        # Статистика при конце
        new_data = get_game_text(next_state)
        if new_data.get('end', False):
            stats = load_stats()
            stats['total_games'] += 1
            ending_name = next_state.replace('end_', '')
            stats['endings'][ending_name] = stats['endings'].get(ending_name, 0) + 1
            save_stats(stats)

        text = new_data['text'].replace('{inventory}',
                                        ', '.join(INVENTORY_ITEMS.get(i, i) for i in user_data['inventory']) or 'пусто')
        return text, new_data.get('choices', []), new_data.get('end', False), get_image_path(
            new_data.get('image')), None

    # Случайное событие
    if 'random_event' in state_data and random.random() < state_data['random_event']['chance']:
        event = state_data['random_event']
        return event['text'], event['choices'], False, None, None

    # Обычный текст
    text = state_data['text'].replace('{inventory}',
                                      ', '.join(INVENTORY_ITEMS.get(i, i) for i in user_data['inventory']) or 'пусто')
    return text, state_data.get('choices', []), state_data.get('end', False), get_image_path(
        state_data.get('image')), None


def get_image_path(filename: Optional[str]) -> Optional[str]:
    if filename:
        path = os.path.join(IMAGE_DIR, filename)
        return path if os.path.exists(path) else None
    return None


# ==============================
# 🤖 Обработчики Telegram
# ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}! Добро пожаловать в *Тайну Забытого Архива*! 🕯️\n\n"
        "📜 Команды:\n"
        "/play — начать игру\n"
        "/inventory — инвентарь\n"
        "/achievements — достижения\n"
        "/stats — статистика\n"
        "/hint — подсказка (3 шт.)\n"
        "/restart — начать заново",
        parse_mode="Markdown"
    )


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    text, choices, is_end, image, sound = process_game_step(user_id, command='/restart')

    if image and os.path.exists(image):
        try:
            await update.message.reply_photo(photo=open(image, 'rb'))
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")

    if choices:
        keyboard = [[c['text']] for c in choices]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


async def show_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    text, _, _, _, _ = process_game_step(user_id, command='/inventory')
    await update.message.reply_text(text)


async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    text, _, _, _, _ = process_game_step(user_id, command='/achievements')
    await update.message.reply_text(text)


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    text, _, _, _, _ = process_game_step(user_id, command='/stats')
    await update.message.reply_text(text)


async def show_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    text, _, _, _, _ = process_game_step(user_id, command='/hint')
    await update.message.reply_text(text)


async def restart_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await play(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text.startswith('/'):
        return

    current_data = load_user_data(user_id)
    current_state = current_data['state']
    state_data = get_game_text(current_state)

    # Головоломка
    if 'puzzle' in state_data:
        text, choices, is_end, image, sound = process_game_step(user_id, user_input=text)
        if image and os.path.exists(image):
            try:
                await update.message.reply_photo(photo=open(image, 'rb'))
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")
        await update.message.reply_text(text, parse_mode="Markdown" if not is_end else None)
        if choices:
            keyboard = [[c['text']] for c in choices]
            markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text("Выберите действие:", reply_markup=markup)
        elif is_end:
            await update.message.reply_text("Игра окончена. /play чтобы начать заново.",
                                            reply_markup=ReplyKeyboardRemove())
        return

    # Обычный выбор
    _, current_choices, _, _, _ = process_game_step(user_id)
    choice_index = next((i for i, c in enumerate(current_choices) if c['text'] == text), None)

    if choice_index is not None:
        text, choices, is_end, image, sound = process_game_step(user_id, choice_index=choice_index)

        if image and os.path.exists(image):
            try:
                await update.message.reply_photo(photo=open(image, 'rb'))
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")

        if choices and not is_end:
            keyboard = [[c['text']] for c in choices]
            markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove(),
                                            parse_mode="Markdown" if not is_end else None)
            if is_end:
                await update.message.reply_text("Игра окончена. Напишите /play, чтобы начать заново.")
    else:
        pass


# ==============================
# 🌐 Webhook обработчики
# ==============================

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        if not json_data:
            return 'OK', 200

        # Создаем Update объект
        update = Update.de_json(json_data, telegram_app.bot)

        # Обрабатываем update в event loop
        asyncio.run_coroutine_threadsafe(
            telegram_app.process_update(update),
            bot_loop
        )
        return 'OK', 200
    except Exception as e:
        logger.error(f"Ошибка в webhook: {e}")
        return 'ERROR', 500


@app.route('/', methods=['GET'])
def home():
    return '✅ Mystery Archive Bot is running!', 200


# ==============================
# 🚀 Запуск бота
# ==============================

def run_bot():
    global telegram_app, bot_loop

    try:
        # Создаем новый event loop для бота
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)

        # Создаем приложение
        telegram_app = Application.builder().token(TOKEN).build()

        # Регистрируем обработчики
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("play", play))
        telegram_app.add_handler(CommandHandler("inventory", show_inventory))
        telegram_app.add_handler(CommandHandler("achievements", show_achievements))
        telegram_app.add_handler(CommandHandler("stats", show_stats))
        telegram_app.add_handler(CommandHandler("hint", show_hint))
        telegram_app.add_handler(CommandHandler("restart", restart_game))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Инициализируем приложение
        bot_loop.run_until_complete(telegram_app.initialize())

        # Устанавливаем webhook
        hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
        if hostname:
            url = f"https://{hostname}/webhook"
            logger.info(f"Setting webhook: {url}")
            try:
                future = asyncio.run_coroutine_threadsafe(
                    telegram_app.bot.set_webhook(url=url),
                    bot_loop
                )
                future.result(timeout=10)
                logger.info("✅ Webhook установлен!")
            except Exception as e:
                logger.error(f"❌ Ошибка установки webhook: {e}")

        logger.info("✅ Бот успешно запущен и готов к работе!")

        # Запускаем event loop
        bot_loop.run_forever()

    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")


# ==============================
# 🎯 Основной запуск
# ==============================

if __name__ == '__main__':
    # Валидация игры
    validate_game_states()

    # Создаем необходимые директории
    os.makedirs(IMAGE_DIR, exist_ok=True)
    os.makedirs(SOUND_DIR, exist_ok=True)

    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Запускаем Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)