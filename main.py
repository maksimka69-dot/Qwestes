import logging
import json
import os
import random
import sys
import time
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

# 🎮 Расширенный гейм-текст (все главы)
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
        'items': ['notebook']  # предмет добавляется при входе в состояние
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
    },

    # =============== НОВЫЙ СЮЖЕТ: Глава 2 ===============
    'chapter_1_notebook': {
        'text': """📘 *Первая запись Элиаса Вейна, 12 марта 1923 г.*

> "Сегодня мы нашли вход. За тройной дверью — Комната Времени.  
> Она показывает не прошлое, а *возможности*. Но за каждое видение — цена.  
> Марта говорит: 'Не смотри слишком долго'. Но как устоять, когда видишь своё будущее...?"

На последней странице — *пятно крови* и рисунок: три символа: 🔑, 💉, 🔥.

*Что вы делаете?*""",
        'choices': [
            {'text': 'Искать тройную дверь', 'next_state': 'chapter_2_gate'},
            {'text': 'Вернуться к карте', 'next_state': 'chapter_1_map'},
            {'text': 'Позвать на помощь', 'next_state': 'chapter_1_call_for_help'}
        ],
        'image': 'notebook.jpg'
    },

    'chapter_1_call_for_help': {
        'text': """🗣️ *Вы кричите в пустоту...*

Через минуту появляется *Марта* — уборщица.  
> "О, вы нашли его. Я знала, что вы особенный."  
Она протягивает вам *шоколадку*.  
> "Съешьте. Вам понадобится энергия."

*Что вы делаете?*""",
        'choices': [
            {'text': 'Взять шоколадку', 'next_state': 'chapter_1_trusting', 'items': ['chocolate'], 'achievement': 'trusting'},
            {'text': 'Отказаться', 'next_state': 'chapter_1_skeptic', 'achievement': 'skeptic'}
        ],
        'image': 'marta.jpg'
    },

    'chapter_1_trusting': {
        'text': """🍫 *Сладкий вкус... и странное головокружение.*

Марта улыбается.  
> "Теперь вы готовы. Идём к тройной двери."

Она ведёт вас вглубь подвала, где стена украшена тремя символами: 🔑, 💉, 🔥.

*Что вы делаете?*""",
        'choices': [
            {'text': 'Довериться Марте', 'next_state': 'chapter_2_gate'},
            {'text': 'Потребовать объяснений', 'next_state': 'chapter_1_confront_marta'}
        ]
    },

    'chapter_1_skeptic': {
        'text': """🤨 *Вы отступаете.*

Марта вздыхает.  
> "Жаль. Значит, вы пойдёте один. Дверь откроется... но не для всех."

Она исчезает в темноте. Перед вами — стена с тремя символами.

*Что вы делаете?*""",
        'choices': [
            {'text': 'Искать тройную дверь', 'next_state': 'chapter_2_gate'}
        ]
    },

    'chapter_1_confront_marta': {
        'text': """⚔️ *Вы хватаете её за руку.*

> "Кто вы? Что происходит?"

Марта смеётся — её глаза *на миг вспыхивают золотом*.  
> "Я — Хранительница. Как и вы *будете*, если выберете верно."

Она отступает, указывая на дверь.  
> "Выбирай: Ключ. Кровь. Огонь. Но помни — цена всегда одинакова."

*Что вы делаете?*""",
        'choices': [
            {'text': 'Подойти к двери', 'next_state': 'chapter_2_gate'}
        ]
    },

    'chapter_1_map': {
        'text': """🗺️ *Карта подвала*

Символы образуют путь:  
→ люк → лестница → зеркало → **тройная дверь**.

На обороте — надпись:  
> "Открой дверь: не ключом, не силой, а *жертвой*."

*Что вы делаете?*""",
        'choices': [
            {'text': 'Следовать по карте', 'next_state': 'chapter_2_gate'},
            {'text': 'Вернуться к дневнику', 'next_state': 'chapter_1_notebook'}
        ],
        'image': 'map.jpg'
    },

    'chapter_2_gate': {
        'text': """🚪 *Тройная дверь*

Перед вами три арки под одной сводчатой дверью.  
Каждая имеет символ и надпись:

1️⃣ 🔑 *«Путь Разума»* — *найди ключ, спрятанный в подвале*  
2️⃣ 💉 *«Путь Сердца»* — *проколи палец и дай каплю крови*  
3️⃣ 🔥 *«Путь Души»* — *сожги что-то дорогое*

На полу — *тень*, которая шевелится.

*Что вы выбираете?*""",
        'choices': [
            {'text': 'Путь Разума (ключ)', 'next_state': 'chapter_2_key_path', 'required_item': 'key'},
            {'text': 'Путь Сердца (кровь)', 'next_state': 'chapter_2_blood_path'},
            {'text': 'Путь Души (жертва)', 'next_state': 'chapter_2_fire_path'}
        ],
        'image': 'triple_gate.jpg'
    },

    'chapter_2_key_path': {
        'text': """🗝️ *Вы вставляете ключ...*

Дверь открывается со скрипом. За ней — *Комната Знаний*: полки с книгами, в центре — глобус из света.

> "Добро пожаловать, Хранитель."

*Конец: Хранитель Тайн* 🏆""",
        'choices': [],
        'end': True,
        'achievement': 'keeper'
    },

    'chapter_2_blood_path': {
        'text': """💉 *Капля крови падает на символ...*

Символ вспыхивает. Дверь растворяется. Вы входите в *Комнату Времени*.

Перед вами — *зеркало будущего*. Вы видите себя:  
— как вы уходите с архива…  
— как вы остаётесь и становитесь директором…  
— как вы **исчезаете в 1923 году**.

Голос Элиаса:  
> "Выбери одно. Но знай: остальные пути *умрут*."

*Что вы выбираете?*""",
        'choices': [
            {'text': 'Уйти и забыть всё', 'next_state': 'end_leave', 'achievement': 'ash'},
            {'text': 'Остаться — стать директором', 'next_state': 'end_director'},
            {'text': 'Войти в 1923 — найти Элиаса', 'next_state': 'chapter_2_time_jump'}
        ],
        'image': 'time_mirror.jpg'
    },

    'chapter_2_fire_path': {
        'text': """🔥 *Вы достаёте фляжку виски.*

> "Прости, Элиас."

Вы бросаете её в огонь символа. Пламя вспыхивает синим.  
Дверь *растворяется*, но из неё выходит **Тень** — силуэт в плаще.

> "Ты выбрал жертву. Теперь служи Теням."

*Конец: Преданный Тайной* 🗡️""",
        'choices': [],
        'end': True,
        'achievement': 'betrayed'
    },

    'chapter_2_time_jump': {
        'text': """🌀 *Вы шагаете в зеркало...*

Вихрь времени уносит вас. Вы падаете в снег.  
**12 марта 1923 года.**

Перед вами — молодой Элиас Вейн. Он улыбается.  
> "Я ждал тебя. Помоги мне не открыть дверь... а *запечатать её навсегда*."

В руке он держит *амулет времени*.

*Что вы делаете?*""",
        'choices': [
            {'text': 'Взять амулет и запечатать дверь', 'next_state': 'end_seal', 'items': ['amulet']},
            {'text': 'Предложить другое решение', 'next_state': 'chapter_2_altar'}
        ],
        'image': '1923_snow.jpg'
    },

    'chapter_2_altar': {
        'text': """🕯️ *Алтарь Времени*

Элиас ведёт вас к каменному алтарю, на котором лежат три предмета:  
- 📔 Дневник  
- 🍫 Шоколадка (если есть)  
- 🍾 Фляжка (если есть)  

> "Чтобы запечатать дверь, нужно *жертвовать не вещь, а память*.  
> То, что ты больше всего ценишь в этой истории."

*Что вы жертвуете?*""",
        'choices': [
            {'text': 'Дневник Элиаса', 'next_state': 'end_seal', 'required_item': 'notebook'},
            {'text': 'Шоколадку Марты', 'next_state': 'end_seal_trust', 'required_item': 'chocolate'},
            {'text': 'Фляжку виски', 'next_state': 'end_seal_courage', 'required_item': 'whiskey'}
        ]
    },

    'end_director': {
        'text': """👔 *Новый директор*

Год спустя вы сидите в кабинете. На стене — фотография *вас и Элиаса*.  
Вы пишете в дневнике:  
> "Тайна жива. И я — её хранитель."

Мимо окна проходит Марта и кивает.

*Конец: Новый Хранитель* 🕊️""",
        'choices': [],
        'end': True
    },

    'end_seal': {
        'text': """🔒 *Запечатывание*

Вы кладёте амулет на алтарь. Свет поглощает дверь.  
Элиас исчезает, шепча:  
> "Спасибо. Теперь никто не узнает правду."

Вы просыпаетесь в подвале... в 2025 году.  
Чемодан *исчез*. Осталась только *старая фотография* — с вами и Элиасом.

*Конец: Хранитель Памяти* ⏳""",
        'choices': [],
        'end': True,
        'achievement': 'keeper'
    },

    'end_seal_trust': {
        'text': """❤️ *Жертва доверия*

Вы кладёте шоколадку на алтарь. Она тает в свете.  
Марта появляется из воздуха:  
> "Ты выбрал доверие. Даже к той, что обманула."

Она дарит вам *лупу* — теперь вы видите скрытые символы везде.

*Конец: Прозрение* 🔍""",
        'choices': [],
        'end': True,
        'achievement': 'detective'
    },

    'end_seal_courage': {
        'text': """🥃 *Жертва храбрости*

Вы разбиваете фляжку о камень. Виски вспыхивает золотым.  
Элиас смеётся:  
> "Вот оно — мужество стажёра!"

Вы возвращаетесь... но теперь *слышите шепот времени*.

*Конец: Слышащий Время* 👂""",
        'choices': [],
        'end': True
    }
}


# ==============================
# 🛠️ Функции
# ==============================

def validate_game_states():
    all_states = set(GAME_TEXTS.keys())
    referenced = set()
    for state in GAME_TEXTS.values():
        for choice in state.get('choices', []):
            referenced.add(choice['next_state'])
        puzzle = state.get('puzzle')
        if puzzle:
            referenced.add(puzzle.get('success_state', ''))
            referenced.add(puzzle.get('fail_state', ''))

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
        'choices_log': [],
        '_prev_state': None  # для отслеживания входа в новое состояние
    }


def save_user_data(user_id: int,  Dict[str, Any]):
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
        except Exception as e:
            logger.error(f"Ошибка загрузки статистики: {e}")
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


def add_item_to_inventory(user_ Dict[str, Any], item: str):
    """Добавляет предмет, если его ещё нет. Обновляет статистику."""
    if item and item not in user_data['inventory']:
        user_data['inventory'].append(item)
        stats = load_stats()
        stats['items_found'][item] = stats['items_found'].get(item, 0) + 1
        save_stats(stats)


def unlock_achievement(user_ Dict[str, Any], achievement_key: str) -> Optional[str]:
    """Разблокирует достижение. Возвращает сообщение или None."""
    if achievement_key and achievement_key not in user_data['achievements']:
        if achievement_key in ACHIEVEMENTS:
            user_data['achievements'].append(achievement_key)
            ach = ACHIEVEMENTS[achievement_key]
            logger.info(f"Achievement unlocked for {user_data.get('user_id', '?')}: {ach['name']}")
            return f"🎉 Достижение получено: {ach['emoji']} {ach['name']} — {ach['desc']}"
        else:
            logger.warning(f"Unknown achievement: {achievement_key}")
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
) -> Tuple[str, List[Dict[str, Any]], bool, Optional[str], List[str]]:
    """
    Возвращает: (текст, выборы, is_end, путь_к_изображению, [сообщения_о_достижениях])
    """
    user_data = load_user_data(user_id)
    achievement_messages = []

    # === Команды ===
    if command == '/inventory':
        return get_inventory_text(user_data['inventory']), [], False, None, []
    if command == '/achievements':
        return get_achievements_text(user_data['achievements']), [], False, None, []
    if command == '/stats':
        stats = load_stats()
        endings = "\n".join([f"{k}: {v}" for k, v in stats.get('endings', {}).items()])
        text = f"📊 Статистика\nВсего игр: {stats.get('total_games', 0)}\n\nКонцовки:\n{endings or 'Нет данных'}"
        return text, [], False, None, []
    if command == '/hint':
        if user_data.get('hints_used', 0) >= 3:
            return "У вас закончились подсказки (макс. 3) 🧠", [], False, None, []
        user_data['hints_used'] += 1
        save_user_data(user_id, user_data)
        return "Подсказка: исследуйте все углы подвала. Фонарик и фото могут помочь.", [], False, None, []
    if command == '/restart':
        user_data = get_default_user_data()
        user_data['games_played'] += 1
        save_user_data(user_id, user_data)
        state_data = get_game_text('start')
        text = state_data['text']
        choices = state_data.get('choices', [])
        image = get_image_path(state_data.get('image'))
        return text, choices, False, image, []

    current_state = user_data['state']
    state_data = get_game_text(current_state)

    # === Головоломка ===
    if 'puzzle' in state_
        and user_input:
        puzzle = state_data['puzzle']
        next_state = puzzle['success_state'] if user_input.strip() == puzzle['answer'] else puzzle['fail_state']
        user_data['state'] = next_state
        save_user_data(user_id, user_data)
        new_data = get_game_text(next_state)
        text = new_data['text']
        image = get_image_path(new_data.get('image'))
        return text, new_data.get('choices', []), new_data.get('end', False), image, []

    # === Вход в новое состояние: предметы и достижения из state_data (1 раз) ===
    prev_state = user_data.get('_prev_state')
    if current_state != prev_state:
        # Предметы из состояния
        if 'items' in state_
            for item in state_data['items']:
                add_item_to_inventory(user_data, item)

        # Достижение из состояния
        if 'achievement' in state_
            msg = unlock_achievement(user_data, state_data['achievement'])
            if msg:
                achievement_messages.append(msg)

        # Авто-достижение "Коллекционер"
        if len(user_data['inventory']) >= len(INVENTORY_ITEMS):
            msg = unlock_achievement(user_data, 'collector')
            if msg:
                achievement_messages.append(msg)

        user_data['_prev_state'] = current_state
        save_user_data(user_id, user_data)

    # === Выбор игрока ===
    if choice_index is not None and 0 <= choice_index < len(state_data.get('choices', [])):
        choice = state_data['choices'][choice_index]
        next_state = choice['next_state']

        # Проверка требуемого предмета
        required = choice.get('required_item')
        if required and required not in user_data['inventory']:
            item_name = INVENTORY_ITEMS.get(required, required)
            return f"❌ У вас нет {item_name}! Проверьте инвентарь (/inventory).", state_data.get('choices', []), False, None, []

        # Лог выбора
        user_data['choices_log'].append({
            'state': current_state,
            'choice': choice['text'],
            'next_state': next_state,
            'timestamp': int(time.time())
        })

        # Достижение из выбора
        if 'achievement' in choice:
            msg = unlock_achievement(user_data, choice['achievement'])
            if msg:
                achievement_messages.append(msg)

        # Предметы из выбора
        if 'items' in choice:
            for item in choice['items']:
                add_item_to_inventory(user_data, item)

        # Обновляем состояние
        user_data['state'] = next_state
        save_user_data(user_id, user_data)

        # Обработка конца игры
        new_data = get_game_text(next_state)
        if new_data.get('end', False):
            stats = load_stats()
            stats['total_games'] += 1
            ending_name = next_state.replace('end_', '', 1)
            stats['endings'][ending_name] = stats['endings'].get(ending_name, 0) + 1
            save_stats(stats)

        # Формируем финальный текст
        text = new_data['text']
        if achievement_messages:
            text = "\n\n".join([text] + achievement_messages)
        return text, new_data.get('choices', []), new_data.get('end', False), get_image_path(new_data.get('image')), achievement_messages

    # === Случайное событие ===
    event = state_data.get('random_event')
    if event and random.random() < event['chance']:
        return event['text'], event['choices'], False, None, []

    # === Обычный текст состояния ===
    text = state_data['text']
    if achievement_messages:
        text = "\n\n".join([text] + achievement_messages)
    return text, state_data.get('choices', []), state_data.get('end', False), get_image_path(state_data.get('image')), achievement_messages


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
    text, choices, is_end, image, ach_msgs = process_game_step(user_id, command='/restart')

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
    if not update.message or not update.effective_user:
        return

    if not update.message.text:
        await update.message.reply_text("Пожалуйста, выберите вариант из клавиатуры или введите текст.")
        return

    user_id = update.effective_user.id
    text_input = update.message.text.strip()

    if text_input.startswith('/'):
        return  # команды обрабатываются отдельно

    current_data = load_user_data(user_id)
    current_state = current_data['state']
    state_data = get_game_text(current_state)

    # === Головоломка ===
    if 'puzzle' in state_
        text, choices, is_end, image, ach_msgs = process_game_step(user_id, user_input=text_input)
        if image and os.path.exists(image):
            try:
                await update.message.reply_photo(photo=open(image, 'rb'))
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")
        full_text = "\n\n".join([text] + ach_msgs) if ach_msgs else text
        await update.message.reply_text(full_text, parse_mode="Markdown" if not is_end else None)
        if choices:
            keyboard = [[c['text']] for c in choices]
            markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text("Выберите действие:", reply_markup=markup)
        elif is_end:
            await update.message.reply_text("Игра окончена. /play чтобы начать заново.", reply_markup=ReplyKeyboardRemove())
        return

    # === Обычный выбор ===
    _, current_choices, _, _, _ = process_game_step(user_id)
    choice_index = next((i for i, c in enumerate(current_choices) if c['text'] == text_input), None)

    if choice_index is not None:
        text, choices, is_end, image, ach_msgs = process_game_step(user_id, choice_index=choice_index)
        full_text = "\n\n".join([text] + ach_msgs) if ach_msgs else text

        if image and os.path.exists(image):
            try:
                await update.message.reply_photo(photo=open(image, 'rb'))
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")

        if choices and not is_end:
            keyboard = [[c['text']] for c in choices]
            markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(full_text, reply_markup=markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(full_text, reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown" if not is_end else None)
            if is_end:
                await update.message.reply_text("Игра окончена. Напишите /play, чтобы начать заново.")
    else:
        # Неизвестный ввод — мягко напоминаем
        await update.message.reply_text("Неизвестная команда. Выберите вариант из клавиатуры.")


# ==============================
# 🌐 Webhook обработчики
# ==============================

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        if not json_
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
        # Перезапуск невозможен из потока, но логируем


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
