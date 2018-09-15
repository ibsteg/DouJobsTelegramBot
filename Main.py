from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
import unicodedata
from pymongo import *
import re

updater = Updater(token="")
dispatcher = updater.dispatcher
url = ''


def start_command(bot, update):
    """ /start function """

    bot.send_message(chat_id=update.message.chat_id, text="Привіт! Для пошуку вакансій введіть пошуковий запит")


def form_url(text='python львов'):
    l = text.split()
    searchtext = 'https://jobs.dou.ua/vacancies/?search='
    for item in l:
        if re.search(r'[а-яА-ЯёЁ]', item) is None:
            searchtext += '+' + item
        else:
            searchtext += '+' + quote(item)
    return searchtext


def get_html(urltext):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/68.0.3440.106 Safari/537.36 '
    }
    result = requests.get(urltext, headers=headers)
    return result


def write_database(result):
    conn = MongoClient()
    db = conn.DouJobsBotDB
    jobs = db.Jobs
    soup = BeautifulSoup(result.text, features="html.parser")
    vacancies = soup.find('ul', {'class': 'lt'})
    items = vacancies.findAll('li', {'class': 'l-vacancy'})

    jobs.remove()
    for item in items:
        jobs.save(
            {'vacancy': unicodedata.normalize("NFKD", item.find('div', {'class': 'title'}).find('a').text),
             'link': item.find('div', {'class': 'title'}).find('a').get('href'),
             'company': unicodedata.normalize("NFKD", item.find('strong').find('a', {'class': 'company'}).text),
             'cities': item.find('span', {'class': 'cities'}).text})
    conn.close()


def text_message(bot, update):
    text = update.message.text
    global url
    url = form_url(text)
    html_page = get_html(url)
    write_database(html_page)
    bot.send_message(chat_id=update.message.chat_id, text='Дані завантажено з DOU.ua. '
                                                          'Перегляд доступний за командою /get')


def help_command(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="Для пошуку вакансій введіть пошуковий запит")


def get_command(bot, update):
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
    conn = MongoClient()
    db = conn.DouJobsBotDB
    jobs = db.Jobs

    url = form_url()
    html_page = get_html(url)

    soup = BeautifulSoup(html_page.text, features="html.parser")
    vacancies = soup.find('ul', {'class': 'lt'})
    items = vacancies.findAll('li', {'class': 'l-vacancy'})

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


convhandler = ConversationHandler(
    entry_points=[CommandHandler('get', get_command)],
    states={
        "info": [MessageHandler(Filters.text, text_message)]
    },
    fallbacks=[CommandHandler('get', get_command)]
)


dispatcher.add_handler(convhandler)

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
