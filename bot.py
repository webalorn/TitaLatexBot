#!/usr/bin/env python
import telebot
import time
import LaTeX2IMG
from time import sleep

TOKEN = '115128154:AAHySW69KRHCJ4v-OPpeJHQTXaDA4K58b4U'


def listener(*messages):
    """
    When new messages arrive TeleBot will call this function.
    """
    for m in messages:
        chatid = m.chat.id
        if m.content_type == 'text':
            text = m.text
            LaTeX2IMG.main(['LaTeX2IMG',text,'resultado','png'])
            photo = open('resultado.png','rb')
            tb.send_photo(chatid,photo)
            # tb.send_message(chatid, text)


tb = telebot.TeleBot(TOKEN)
tb.set_update_listener(listener) #register listener
tb.polling()

while True: # Don't let the main Thread end.
    sleep(5)