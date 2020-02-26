#!/usr/bin/env python3

from threading import current_thread
from collections import defaultdict, deque
import os, sys
import base64
import struct

import telebot
from telebot import logging
from telebot import types

from urllib.parse import quote
from urllib.request import urlopen
import PIL
from PIL import Image, ImageOps

## Utility functions

NON_VALID_LATEX = set()
LAST_IMAGES = defaultdict(deque, {'webalorn': deque([('4', 'AgACAgQAAxkDAANYXlYkvhUH810L16zmbHQ3t5HLGVYAAhmxMRtUQLFSCsGyfZfpP1lIX6gbAAQBAAMCAANtAANWbwgAARgE'), ('5', 'AgACAgQAAxkDAANaXlYkxXYmks1CS42IkGjMbnwsEKMAAoCxMRveYbhSTV_Wh-kJmGzPkaAbAAQBAAMCAANtAAPR9AcAARgE')])})
MAX_SAVED_USER = 10

try:
	EXPOSE_URL = open("expose_url.txt").read().strip()
	print("Inline mode : recent item and new expressions generation")
except FileNotFoundError:
	EXPOSE_URL = None
	print("Inline mode : only recent items")

def present_user(user):
	return "{} (@{})".format(" ".join(
		[name for name in [user.first_name, user.last_name] if name]),
		user.username
	)

def filename2url(filename):
	return EXPOSE_URL + filename

# Original code and licence for theses 2 functions at : https://gist.github.com/Cilyan/9424144 (Written by : @Cilyan)

def fnv64(data):
	hash_ = 0xcbf29ce484222325
	for b in data:
		hash_ *= 0x100000001b3
		hash_ &= 0xffffffffffffffff
		hash_ ^= b
	return hash_

def hash_dn(dn, salt="42"):
	# Turn dn into bytes with a salt, dn is expected to be ascii data
	dn = "".join(chr(ord(c)%128) for c in dn)
	data = salt.encode("ascii") + dn.encode("ascii")
	# Hash data
	hash_ = fnv64(data)
	# Pack hash (int) into bytes
	bhash = struct.pack("<Q", hash_)
	return base64.urlsafe_b64encode(bhash)[:-1].decode("ascii")

def mark_user_image(username, expression, photo_id):
	LAST_IMAGES[username].append((expression, photo_id))
	while len(LAST_IMAGES[username]) > MAX_SAVED_USER:
		LAST_IMAGES[username].popleft()

## Latex conversion

def latex2img(expression):
	"""
	Convert expression to an image called filename.webp
	"""
	expression = expression.strip()
	expr_encoded = hash_dn(expression)
	filename = "results/" + expr_encoded + ".webp"
	os.makedirs("results", exist_ok=True)

	if os.path.exists(filename):
		return filename
	elif expr_encoded in NON_VALID_LATEX:
		return None

	# Preparing text strings
	server = "http://latex.codecogs.com/png.download?"
	fullname_png = "results/" + current_thread().name + "_tmp.png"
	size = "%5Cdpi%7B300%7D%20"

	# Quote expression
	expression = quote(expression)
	url = server + size + expression

	# Download file from url and save to output_file:
	with urlopen(url) as response, open(fullname_png, 'wb') as output_file:
		data = response.read()  # A bytes object
		output_file.write(data)

	try:
		image = Image.open(fullname_png).convert("RGBA")
		image = ImageOps.expand(image, 75)
	except PIL.UnidentifiedImageError: # In case of invalid expression
		NON_VALID_LATEX.add(expression)
		return None

	canvas = Image.new('RGBA', image.size, (255,255,255,255))
	canvas.paste(image, mask=image)
	canvas.save(filename, format="WEBP")

	os.remove(fullname_png)

	return filename

## Bot creation

with open("token.txt", "r") as file:
	TOKEN = file.readline().strip()

bot = telebot.TeleBot(TOKEN)
bot_user_infos = bot.get_me()

## Bot functions

def send_equation(chat_id, text, user):
	bot.send_chat_action(chat_id, 'upload_document')

	filename = latex2img(text)
	if not filename:
		return False

	with open(filename, 'rb') as equation:
		msg = bot.send_photo(chat_id, equation)
		mark_user_image(user.username, text.strip(), msg.photo[0].file_id)
	return True

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	if message.text != "latex":
		bot.reply_to(message, "You can convert LaTeX expression using\n\n/latex expression")

@bot.message_handler(commands=['latex'])
def send_expression(message):
	print("GOT message from {} : {}".format(present_user(message.from_user), repr(message.text)))
	chat_id = message.chat.id
	text = message.text[7:]

	if text and text != "LaTeX2IMGbot":
		if not send_equation(chat_id, text, message.from_user):
			new_msg = bot.reply_to(message, "Invalid latex expression")
	else:
		new_msg = bot.reply_to(message, "Please send your expression with \"/latex [expression]\"")

## Inline mode

def get_inline_query_results_generated(inline_query):
	image_path = latex2img(inline_query.query)
	if image_path:
		return [
			telebot.types.InlineQueryResultArticle(
				id=0,
				title="Convert LaTeX to image",
				input_message_content=telebot.types.InputTextMessageContent(
					filename2url(image_path),
					parse_mode='HTML'
				),
				description="Press to send the image url",
				thumb_height=1
			)
		]
	return [
		telebot.types.InlineQueryResultArticle(
			id=0,
			title="Convert LaTeX to image",
			input_message_content=telebot.types.InputTextMessageContent(
				"The latex code \"{}\" is invalid".format(inline_query.query)
			),
			description="invalid LaTeX code",
			thumb_height=1
		)
	]

def get_inline_query_results_lasts(inline_query):
	results = []
	for latex_expr, photo_id in LAST_IMAGES[inline_query.from_user.username]:
		results.append(
			telebot.types.InlineQueryResultCachedPhoto(
				id=len(results)+10,
				title=latex_expr,
				photo_file_id=photo_id,
				description="Use previous expression :",
				caption=latex_expr
			)
		)
	return results

@bot.inline_handler(func=lambda query: True)
def query_text(inline_query):
	if inline_query.query.strip() and EXPOSE_URL:
		bot.answer_inline_query(
			inline_query.id,
			get_inline_query_results_generated(inline_query),
		)
	else:
		bot.answer_inline_query(
			inline_query.id,
			get_inline_query_results_lasts(inline_query),
			cache_time=0,
			is_personal=True,
			switch_pm_text="Write an equation with me",
			switch_pm_parameter="latex",
		)

## Init bot

logger = telebot.logger
formatter = logging.Formatter('[%(asctime)s] %(thread)d {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
								  '%m-%d %H:%M:%S')
ch = logging.FileHandler("log.txt")
logger.addHandler(ch)
logger.setLevel(logging.INFO)
ch.setFormatter(formatter)


print("Hello ! I am {}".format(present_user(bot_user_infos) or ""))
bot.polling()