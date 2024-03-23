# Импортируем нужные библиотеки
import telebot
import logging
from gpt import count_tokens, ask_gpt
from telebot.types import Message, ReplyKeyboardMarkup
from database import create_table, create_db, execute_query
from config import TOKEN, MAX_TASK_TOKENS, DB_NAME, text_help

# Создаем бота
bot = telebot.TeleBot(TOKEN)

# Список доступных комманд
commandss = ['/help', '/about', '/start', '/solve_task', '/continue', '/finish']
subjects = ['математика', 'физика']
levels = ['простой', 'сложный']

# Словарь с задачами и ответами
user_history = {}
current_options = {}

create_db(DB_NAME)
create_table('users')

logging.basicConfig(filename='log.txt', level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", filemode="w")
 
# Функция создания клавиатуры с переданными кнопками
def make_keyboard(buttons):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(*buttons)
    return markup

# Обработчики команд:
@bot.message_handler(commands=['help'])
def say_help(message: Message):
    bot.send_message(message.from_user.id, text_help)

@bot.message_handler(commands=['about'])
def about_command(message: Message):
    bot.send_message(message.from_user.id, 'Давай я расскажу тебе немного о себе: Я - твой бот-помощник, готовый помочь и ответить на любой вопрос по математике или физике. Я очень люблю точные науки (прям как мои ответы). Так что я постараюсь не оставить тебя в одиночестве;)',
                     reply_markup=make_keyboard(['/start', '/help']))

@bot.message_handler(commands=['start'])
def start(message: Message):
    global current_options
    user_name = message.from_user.first_name
    bot.send_message(message.chat.id,
                     text=f'Привет, {user_name}! Я твой бот-помощник для решения разных задач. Скорее задавай вопросы, а я постараюсь на них ответить! Для начала нажми на кнопку /solve_task!',
                     reply_markup=make_keyboard(['/solve_task', '/help', '/about']))
    current_options[message.from_user.id] = {'subject': '', 'level': ''}
    user_history[message.from_user.id] = {}
    logging.info('Отправка приветственного сообщения')

@bot.message_handler(commands=['solve_task'])
def solve_task(message: Message):
    bot.send_message(message.chat.id, 'Выбери предмет:', reply_markup=make_keyboard(subjects))
    bot.register_next_step_handler(message, choose_subject)

def choose_subject(message):
    global current_options
    bot.send_message(message.chat.id, 'Выбери уровень:', reply_markup=make_keyboard(levels))
    current_options[message.from_user.id]['subject'] = message.text
    bot.register_next_step_handler(message, choose_level)

def choose_level(message):
    global current_options
    bot.send_message(message.chat.id, 'Напиши свой вопрос')
    current_options[message.from_user.id]['level'] = message.text
    bot.register_next_step_handler(message, handle)

@bot.message_handler(commands=['continue'])
def continue_explanation(message):
    bot.send_message(message.from_user.id, 'Давайте продолжим.')
    bot.register_next_step_handler(message, handle)
   
@bot.message_handler(commands=['finish'])
def end_task(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Текущее решение завершено. Хотите начать заново?', reply_markup=make_keyboard(['/start', '/help']))
    user_history[user_id] = {}

# Обработка текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle(message, contin=False):
    user_id = message.from_user.id
    if message.content_type != 'text':
        logging.info('Error - Неверный формат данных')
        bot.send_message(user_id, 'Пока я умею работать только с текстовыми сообщениями. Пожалуйста, отправьте сообщение именно текстом.')
        bot.register_next_step_handler(message, handle)
        return
    if count_tokens(message.text) <= MAX_TASK_TOKENS:
        if user_id not in current_options or current_options[user_id] == {}:
            if user_id not in current_options or current_options[user_id]['subject'] not in subjects or current_options[user_id]['level'] not in levels:
                bot.send_message(user_id, 'Ты не зарегистрировался или не выбрал предмет и уровень.')
                start(message)
                return
        if current_options[user_id]['subject'] in subjects:
                cur_subject = current_options[user_id]['subject'][:-1] + 'е'
        if current_options[user_id]['level'] in levels:
                cur_level = current_options[user_id]['level'][:-2] + 'ым'
        user_history[user_id] = {'system_content': f'Ты - дружелюбный помощник для решения задач по {cur_subject}. Давай ответ {cur_level} языком. Давай ответ на русском языке.'}
        bot.send_message(message.chat.id, 'Подождите немного...')
        answer = ask_gpt(message.text, system_content=user_history[user_id]['system_content'])
        user_history[user_id]['task'] = message.text
        user_history[user_id]['answer'] = answer
        if answer == 'Error': # ответ с ошибкой
            bot.send_message(message.chat.id, 'Не удалось получить ответ от нейросети. Попробуйте позже.',
                                reply_markup=make_keyboard(['/solve_task', '/continue']))
            logging.info(f'Output: Error - ошибка при запросе.')
        elif answer == '': # пустой ответ
            bot.send_message(message.chat.id, 'Не удалось сформулировать ответ.',
                                reply_markup=make_keyboard(['/solve_task']))
            logging.info(f'Output: Error - пустой ответ от нейросети.')
        else: # ответ без ошибок
            execute_query(f"DELETE FROM users WHERE user_id={user_id}")
            execute_query(f"INSERT INTO users (user_id, subject, level, task, answer) "
                                f"VALUES ({user_id}, '{current_options[user_id]['subject']}', '{current_options[user_id]['level']}', '{user_history[user_id]['task']}', '{user_history[user_id]['answer']}')")
            bot.send_message(message.chat.id, answer,
                                reply_markup=make_keyboard(['/solve_task', '/continue', '/finish']))
    else:
        user_history[user_id] = None
        bot.send_message(message.chat.id, 'Запрос превышает максимальное количество символов. Пожалуйста, отправьте запрос покороче.')
        logging.info(f'Output: Error - Текст задачи слишком длинный.')

bot.polling()
