from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
import unicodedata
from pymongo import *
import re

updater = Updater(token="")
dispatcher = updater.dispatcher


def start_command(bot, update):
    """
    /start command
    """

    bot.send_message(chat_id=update.message.chat_id, text="Привіт! Для пошуку вакансій введіть пошуковий запит")


def form_url(text='python львов'):
    """
    Forms url string for request and writes result in global variable
    """

    words = text.split()
    pattern = 'https://jobs.dou.ua/vacancies/?search='
    for i in range(len(words)):
        if re.search(r'[а-яА-ЯёЁ]', words[i]) is not None:
            words[i] = quote(words[i])
    global url
    global searchtext
    searchtext = '+'.join(words)
    url = pattern + searchtext


def get_html():
    """
    Makes scrapping of web-page and returns html-code as text
    return: response (str) - html code of page
    """

    client = requests.session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/68.0.3440.106 Safari/537.36 '
    }

    first_part = client.get(url, headers=headers)  # получаю первый get-запрос
    soup = BeautifulSoup(first_part.text, features="html.parser")  # создаю объект-парсер для проверки

    # наличия кнопки и результатов на странице
    if soup.find('div', {'class': 'l-items'}) is None:  # если на странице нет списка результатов
        response = None

    elif soup.find('div', {'class': 'more-btn'}) is None:  # если на странице нет кнопки "Больше вакансий"
        response = first_part

    else:  # если есть список вакансий и есть кнопка "Больше вакансий"
        result = first_part.text  # сохраняем html первой порции
        pattern = 'https://jobs.dou.ua/vacancies/xhr-load/?search='

        csrf = dict(client.cookies)['csrftoken']  # сохраняем токен
        headers['Referer'] = url  # дополняет хидеры для пост-запроса

        data = dict(csrfmiddlewaretoken=csrf, count=20)  # данные, которые передаём пост-запросом
        while True:
            second_part = client.post(pattern + searchtext, headers=headers, data=data)
            result += second_part.json()['html']
            if second_part.json()['last']:  # когда у полученных данных флаг, что они последние
                break
        response = result

    client.close()
    return response


def write_database(result):
    """
    Parses html-page and writes data to database
    :param result: html page as text
    :return: text message with result of writing
    """

    if result is None:
        return 'Не знайдено жодної вакансії'
    conn = MongoClient()
    db = conn.DouJobsBotDB
    jobs = db.Jobs
    soup = BeautifulSoup(result, features="html.parser")
    items = soup.findAll('li', {'class': 'l-vacancy'})

    count = 0
    jobs.remove()
    for item in items:
        jobs.save(
            {'vacancy': unicodedata.normalize("NFKD", item.find('div', {'class': 'title'}).find('a').text),
             'link': item.find('div', {'class': 'title'}).find('a').get('href'),
             'company': unicodedata.normalize("NFKD", item.find('strong').find('a', {'class': 'company'}).text),
             'cities': item.find('span', {'class': 'cities'}).text})
        count += 1
    conn.close()
    return "Дані завантажено! Знайдено {0} записів".format(count)


def text_message(bot, update):
    """
    Handler for text messages, that user sends to bot.
    Message means query to search vacancies.
    Displays result of self-work as message to user.
    """


    text = update.message.text
    global url
    form_url(text)
    html_page = get_html()
    result = write_database(html_page)
    bot.send_message(chat_id=update.message.chat_id, text=str(result))


def help_command(bot, update):
    """
    /help command
    """
    bot.send_message(chat_id=update.message.chat_id, text="Для пошуку вакансій введіть пошуковий запит")


def get_command(bot, update):
    """
    Shows about vacancies, that already appear in database.

    Future extension: telegraph displaying of info
    """
    conn = MongoClient()
    db = conn.DouJobsBotDB
    jobs = db.Jobs

    if 5 > jobs.find().count() > 0:
        text = ''
        for item in jobs.find():
            text += 'Вакансія <b>' + item['vacancy'] + '</b>\n'
            text += ' в <b>' + item['company'] + '</b>\n'
            text += '(в ' + item['cities'] + ')\n'
            text += '<i>детальніше за посиланням:</i>' + item['link']
            bot.send_message(parse_mode='HTML', chat_id=update.message.chat_id, text=text)
            text = ''
    elif jobs.find().count() >= 5:
        text = 'Знайдено <b> {0} </b> вакансій'.format(jobs.find().count())
        bot.send_message(parse_mode='HTML', chat_id=update.message.chat_id, text=text)
    else:
        text = 'Не знайдено жодної вакансії'
        bot.send_message(chat_id=update.message.chat_id, text=text)

    conn.close()


def check_command(bot, update):
    """
    Compares vacancies from current html-page and from database.
    Displays new vacancies if there are such.
    """

    print('In check command handler')
    conn = MongoClient()
    db = conn.DouJobsBotDB
    jobs = db.Jobs

    form_url()
    html_page = get_html()

    if html_page is None:
        print(html_page)
        bot.send_message(chat_id=update.message.chat_id, text='Немає результатів')
    soup = BeautifulSoup(html_page, features="html.parser")
    items = soup.findAll('li', {'class': 'l-vacancy'})

    new = []

    for item in items:
        current = {'vacancy': unicodedata.normalize("NFKD", item.find('div', {'class': 'title'}).find('a').text),
                   'link': item.find('div', {'class': 'title'}).find('a').get('href'),
                   'company': unicodedata.normalize("NFKD", item.find('strong').find('a', {'class': 'company'}).text),
                   'cities': item.find('span', {'class': 'cities'}).text}
        if jobs.find(current).count() == 0:
            new.append(current)
        else:
            pass
    if len(new) == 0:
        text = '{0}, оновлень не знайдено'.format(update.message.from_user.username)
        bot.send_message(chat_id=update.message.chat_id, text=text)
    else:
        for i in range(len(new)):
            text = u'\U0001F525 {0}. Вакансія <b> {1} </b>\n'.format(i+1, new[i]['vacancy'])
            text += ' в <b>' + new[i]['company'] + '</b>\n'
            text += '(в ' + new[i]['cities'] + ')\n'
            text += '<i>детальніше за посиланням:</i>' + new[i]['link']
            bot.send_message(parse_mode='HTML', chat_id=update.message.chat_id, text=text)

    conn.close()
    write_database(html_page)


get_command_handler = CommandHandler('get', get_command)
start_command_handler = CommandHandler('start', start_command)
help_command_handler = CommandHandler('save', help_command)
text_handler = MessageHandler(Filters.text, text_message)
check_handler = CommandHandler('check', check_command)

dispatcher.add_handler(start_command_handler)
dispatcher.add_handler(help_command_handler)
dispatcher.add_handler(text_handler)
dispatcher.add_handler(check_handler)

updater.start_polling(clean=True)
updater.idle()
