#!/usr/bin/env python3

from threading import current_thread, Lock, Thread
from collections import defaultdict, deque
import os, sys, time, json
import base64, struct

import telebot
from telebot import logging
from telebot import types

from latex2img import *

## Messages

MESSAGES = {
	"start" : "Hello ! I am Tita-Latex, I am here to help you using latex in telegram. To start, directly type your latex code, or use :\n\n/latex [you code]\nOr if you want more informations : /help\n\n Enjoy !",
	"latex_start" : "Now, write your equation 😈",
	"switch_pm_text" : "Write an equation with me 😇",
	"no_latex_in_cmd" : "It would be nice to send your latex expression with \"/latex [expression]\", or by sending the code directly in the conversation",
	"invalid_latex_code" : "Ho no, my dear friend... Your latex code \"{}\" is invalid !",
	"help" : "While you can directly talk to me in latex, you can also use :\n/latex [expression]\nYou can use me as a good servant in any conversion by typing @{}. You can then select one of latest images you have generated, or directly type you code."
}

## Global variables and constants

non_valid_latex = set()
non_valid_latex_lock = Lock()

last_images = defaultdict(deque)
last_images_lock = Lock()

old_data_json = ""
data_files_lock = Lock()

MAX_SAVED_USER = 5
LOST = set(["the game", "THE GAME", "game", "42"])


with open("token.txt", "r") as file:
	TOKEN = file.readline().strip()

try:
	EXPOSE_URL = open("expose_url.txt").read().strip()
	if EXPOSE_URL[-1] != "/":
		EXPOSE_URL = EXPOSE_URL + "/"
	print("Inline mode : recent item and new expressions generation")
except FileNotFoundError:
	EXPOSE_URL = None
	print("Inline mode : only recent items")

## Bot creation

bot = telebot.TeleBot(TOKEN)
bot_user_infos = bot.get_me()

## Utility functions

def present_user(user):
	return "{} (@{})".format(" ".join(
		[name for name in [user.first_name, user.last_name] if name]),
		user.username
	)

def filename2url(filename):
	return EXPOSE_URL + filename

def save_data():
	global old_data_json
	with data_files_lock:
		with non_valid_latex_lock, last_images_lock:
			data_dict = {
				"last_images" : {key:list(val) for key, val in last_images.items()},
				"non_valid_latex" : list(non_valid_latex),
			}
		json_val = json.dumps(data_dict)

		if json_val != old_data_json:
			old_data_json = json_val
			with open("data_tmp.json", "w") as f:
				f.write(json_val)
				f.flush()
				os.fsync(f.fileno())
			os.rename("data_tmp.json", "data.json") # Atomic operation, ensures the data is not corrupted if the darmon thread is closed.

def load_data():
	global non_valid_latex, last_images
	try:
		with open("data.json", "r") as f:
			data = json.load(f)

		with non_valid_latex_lock, last_images_lock:
			if "non_valid_latex" in data:
				non_valid_latex = set(data["non_valid_latex"])
			if "last_images" in data:
				for key, val in data["last_images"].items():
					last_images[key] = deque(val)

	except FileNotFoundError:
		pass

class BackgroundThread(Thread):
	def __init__(self, *kargs, daemon=True, **kwargs):
		super().__init__(*kargs, daemon=daemon, **kwargs)

	def run(self):
		while True:
			time.sleep(60*5)
			save_data()

# Original code and licence for theses 2 functions at : https://gist.github.com/Cilyan/9424144 (Written by : @Cilyan)

def fnv64(data):
	hash_ = 0xcbf29ce484222325
	for b in data:
		hash_ *= 0x100000001b3
		hash_ &= 0xffffffffffffffff
		hash_ ^= b
	return hash_

def hash_dn(dn, salt="42"):
	# Turn dn into bytes with a salt
	# dn = "".join(chr(ord(c)%128) for c in dn)
	tab = [[ord(c)] for c in dn]
	for l in tab:
		while l[-1] >= 128:
			l.append(l[-1]//128)
			l[-2] = l[-1] % 128
	dn = "".join(["".join([chr(c) for c in l]) for l in tab])

	data = salt.encode("ascii") + dn.encode("ascii")
	# Hash data
	hash_ = fnv64(data)
	# Pack hash (int) into bytes
	bhash = struct.pack("<Q", hash_)
	return base64.urlsafe_b64encode(bhash)[:-1].decode("ascii")

def mark_user_image(username, expression, photo_id):
	with last_images_lock:
		last_images[username].append((expression, photo_id))
		while len(last_images[username]) > MAX_SAVED_USER:
			last_images[username].popleft()

## Latex conversion

def tex2filename(expression):
	"""
	Convert expression to an image called results/hash.png
	"""
	expression = expression.strip()
	expr_encoded = hash_dn(expression)
	filename_result = "results/" + expr_encoded + ".png"
	os.makedirs("results", exist_ok=True)

	if os.path.exists(filename_result):
		return filename_result
	else:
		with non_valid_latex_lock:
			if expr_encoded in non_valid_latex:
				return None

	filename_tmp = "results/" + current_thread().name + "_tmp"

	try:
		tmp_location = tex2png_codegogs(filename_tmp, expression)
	except InvalidLatexErr:
		with non_valid_latex_lock:
			non_valid_latex.add(expression)
		return None

	os.rename(tmp_location, filename_result)
	return filename_result

## Bot functions

def send_equation(chat_id, text, user):
	bot.send_chat_action(chat_id, 'upload_document')

	filename = tex2filename(text)
	if not filename:
		return False

	with open(filename, 'rb') as equation:
		markup = types.InlineKeyboardMarkup(row_width=2)
		markup.row(
			types.InlineKeyboardButton("Image", url=filename2url(filename)),
			types.InlineKeyboardButton("Send", switch_inline_query="")
		)
		msg = bot.send_photo(chat_id, equation, reply_markup=markup)
		mark_user_image(user.username, text.strip(), msg.photo[0].file_id)
	return True

def handle_expression(text, message):
	if text and text[0] != "/":
		if not send_equation(message.chat.id, text, message.from_user):
			new_msg = bot.reply_to(message, "Invalid latex expression")
	else:
		new_msg = bot.reply_to(message, MESSAGES["no_latex_in_cmd"])

@bot.message_handler(commands=['start'])
def send_welcome(message):
	print("/start with {}".format(present_user(message.from_user)))
	if message.text == "/start latex":
		bot.send_message(message.chat.id, MESSAGES["latex_start"])
	else:
		bot.send_message(message.chat.id, MESSAGES["start"])

@bot.message_handler(commands=['help'])
def send_help(message):
	bot.send_message(message.chat.id, MESSAGES["help"].format(bot_user_infos.username))

@bot.message_handler(commands=['latex'])
def send_expression(message):
	print("GOT message from {} : {}".format(present_user(message.from_user), repr(message.text)))
	text = message.text.strip().split(" ", 1)
	text = text[1] if len(text) >= 2 else ""
	handle_expression(text, message)

@bot.message_handler(func=lambda message:message.chat.type == "private")
def text_handler(message):
	print("GOT message from {} : {}".format(present_user(message.from_user), repr(message.text)))
	text = message.text.strip()
	if text in LOST:
		bot.send_message(message.chat.id, "How dare you !!??...\nI lost the game 👿")
	else:
		handle_expression(text, message)

## Inline mode

def get_inline_query_results_generated(inline_query):
	image_path = tex2filename(inline_query.query)
	if image_path:
		return [
			telebot.types.InlineQueryResultArticle(
				id=0,
				title="Convert LaTeX to image",
				input_message_content=telebot.types.InputTextMessageContent(
					filename2url(image_path),
					parse_mode='HTML'
				),
				description="Press to send the latex image",
				thumb_height=1
			)
		]
	return [
		telebot.types.InlineQueryResultArticle(
			id=0,
			title="Convert LaTeX to image",
			input_message_content=telebot.types.InputTextMessageContent(
				MESSAGES["invalid_latex_code"].format(inline_query.query)
			),
			description="invalid LaTeX code",
			thumb_height=1
		)
	]

def get_inline_query_results_lasts(inline_query):
	results = []
	with last_images_lock:
		for latex_expr, photo_id in last_images[inline_query.from_user.username]:
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
	print("GOT inline query from {} : {}".format(present_user(inline_query.from_user), repr(inline_query.query)))
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
			switch_pm_text=MESSAGES["switch_pm_text"],
			switch_pm_parameter="latex",
		)

## Init bot

load_data()
back_thread = BackgroundThread()

logger = telebot.logger
formatter = logging.Formatter('[%(asctime)s] %(thread)d {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
								  '%m-%d %H:%M:%S')
ch = logging.FileHandler("logging_bot.log")
logger.addHandler(ch)
logger.setLevel(logging.INFO)
ch.setFormatter(formatter)

def main():
	print("Hello ! I am {}".format(present_user(bot_user_infos) or ""))
	back_thread.start()

	while True:
		try:
			bot.polling(none_stop=True)
		except KeyboardInterrupt as e:
			print("KeyboardInterrupt", e)
			raise e
		except Exception as ex:
			print("ERROR", ex)
			logger.error(ex)
		else:
			break
		finally:
			save_data()
		time.sleep(5)

if __name__ == '__main__':
	main()