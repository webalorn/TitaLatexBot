import telebot
from telebot import logging, types
import os, sys, json
from src.latex2img import *
from src.data import *
from src.utility import *

## Bot creation

bot = telebot.TeleBot(CONF.token)

## Bot functions for math latex

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
		add_recent_image_user(user.username, text.strip(), msg.photo[0].file_id)
	return True

def handle_expression(text, message):
	if text and text[0] != "/":
		if not send_equation(message.chat.id, text, message.from_user):
			bot.reply_to(message, "Invalid latex expression")
	else:
		bot.reply_to(message, MESSAGES["no_latex_in_cmd"])

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
	log_message(message)
	text = message.text.strip().split(" ", 1)
	text = text[1] if len(text) >= 2 else ""
	handle_expression(text, message)

@bot.message_handler(commands=['code'])
def send_code(message):
	log_message(message)
	params = message.text.split()
	if len(params) != 2 and len(params) != 3:
		bot.send_message(message.chat.id, MESSAGES["code_cmd_explanation"])
	paste_id = params[1][-8:]
	lang = "" if len(params) == 2 else params[2]
	url = "http://pastebin.com/raw/{}".format(paste_id)

	filename = None
	try:
		filename = code2filename(url, lang)
	except InvalidRessouce:
		bot.send_message(message.chat.id, "This pastebin code/id is not valid 😡")

	if filename:
		with open(filename, 'rb') as img:
			msg = bot.send_photo(message.chat.id, img, caption=url)
	else:
		bot.send_message(message.chat.id, MESSAGES["code_error"])

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
			description="Invalid LaTeX code",
			thumb_height=1
		)
	]

def get_inline_query_results_lasts(inline_query):
	results = []
	with last_images_shared as last_images:
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
	if inline_query.query.strip() and CONF.expose_url:
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

## Unhandled input

@bot.message_handler(func=lambda message:message.chat.type == "private")
def text_handler(message):
	log_message(message)
	text = message.text.strip()
	if text in LOST:
		bot.send_message(message.chat.id, "How dare you !!??...\nI lost the game 👿")
	else:
		handle_expression(text, message)

## Init bot

back_thread, logger = None, None

def init_bot():
	global back_thread, logger

	for d in ["results", "log"]:
		os.makedirs(d, exist_ok=True)

	load_data()
	back_thread = BackgroundThread()

	logger = telebot.logger
	formatter = logging.Formatter('[%(asctime)s] %(thread)d {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
									  '%m-%d %H:%M:%S')
	ch = logging.FileHandler("log/logging_bot.log")
	logger.addHandler(ch)
	logger.setLevel(logging.INFO)
	ch.setFormatter(formatter)

def bot_main_loop():

	init_bot()
	bot_user_infos = bot.get_me()
	back_thread.start()

	CONF.to_stdout()
	print("Hello ! I am {}".format(present_user(bot_user_infos) or ""))

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
		print("Relaunching bot in 10s...")
		time.sleep(10)