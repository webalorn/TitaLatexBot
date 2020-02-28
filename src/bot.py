import telebot
from telebot import logging, types
import os, sys, json
from src.latex2img import *
from src.data import *
from src.utility import *

## Bot creation

bot = telebot.TeleBot(CONF.token)
bot_user_infos = bot.get_me()

## Bot functions for math latex

def send_equation(chat_id, text, user, is_text=False):
	bot.send_chat_action(chat_id, 'upload_document')

	expression = LatexExpression(text)
	if is_text:
		expression.template = "text"
	filename = tex2filename(expression)
	if not filename:
		return False

	with open(filename, 'rb') as equation:
		msg = bot.send_photo(chat_id, equation)
		add_recent_image_user(user.username, text.strip(), msg.photo[0].file_id)

		inline_query = " ".join(["send", str(msg.photo[0].file_id), text.strip()])
		markup = types.InlineKeyboardMarkup(row_width=2)
		markup.row(
			types.InlineKeyboardButton("Image", url=filename2url(filename)),
			types.InlineKeyboardButton("Send", switch_inline_query=inline_query)
		)
		bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg.message_id, reply_markup=markup)
	return True

def handle_expression(text, message, is_text=False):
	if text and text[0] != "/":
		if not send_equation(message.chat.id, text, message.from_user, is_text=is_text):
			bot.reply_to(message, "Invalid latex expression")
	else:
		bot.reply_to(message, MESSAGES["no_latex_in_cmd"])

@bot.message_handler(commands=['start'])
def send_welcome(message):
	log("/start with {}".format(present_user(message.from_user)))
	start_content = " ".join(message.text.strip().split()[1:])
	if start_content == "latex":
		bot.send_message(message.chat.id, MESSAGES["latex_start"])
	else:
		markup = types.InlineKeyboardMarkup(row_width=2)
		markup.row(
			types.InlineKeyboardButton("Show commands list", callback_data="show_help"),
			types.InlineKeyboardButton("I don't care", callback_data="dont_care"),
		)
		bot.send_message(message.chat.id, MESSAGES["start"], reply_markup=markup)

def send_help_action(chat_id):
	bot.send_message(chat_id, MESSAGES["help"].format(bot_user_infos.username), parse_mode="HTML")

@bot.message_handler(commands=['help'])
def send_help(message):
	send_help_action(message.chat.id)

@bot.message_handler(commands=['latex', 'text'])
def send_expression(message):
	log_message(message)
	text_parts = message.text.strip().split(" ", 1)
	text = text_parts[1] if len(text_parts) >= 2 else ""
	handle_expression(text, message, text_parts[0] == "/text")

@bot.message_handler(commands=['code'])
def send_code(message):
	log_message(message)
	params = message.text.split()
	if len(params) != 2 and len(params) != 3:
		bot.send_message(message.chat.id, MESSAGES["code_cmd_explanation"])
		return
	paste_id = params[1][-8:]
	lang = "" if len(params) == 2 else params[2]
	url = "http://pastebin.com/raw/{}".format(paste_id)
	url_paste = "http://pastebin.com/{}".format(paste_id)

	filename = None
	try:
		filename = code2filename(url, lang)
	except InvalidRessouce:
		bot.send_message(message.chat.id, "This pastebin code/id is not valid 😡")

	if filename:
		with open(filename, 'rb') as img:
			msg = bot.send_photo(message.chat.id, img, caption=url)
		with last_code_shared as last_code:
			last_code[message.from_user.username] = (paste_id, lang, msg.photo[0].file_id)

		inline_query = " ".join(["send_code", str(msg.photo[0].file_id), url_paste])
		markup = types.InlineKeyboardMarkup(row_width=2)
		markup.row(
			types.InlineKeyboardButton("Image", url=filename2url(filename)),
			types.InlineKeyboardButton("Send", switch_inline_query=inline_query)
		)
		bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=msg.message_id, reply_markup=markup)
	else:
		bot.send_message(message.chat.id, MESSAGES["code_error"], parse_mode="HTML")

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
	username = inline_query.from_user.username
	with last_images_shared as last_images: # Last math images
		n = len(last_images[username])
		for latex_expr, photo_id in last_images[username]:
			results.append(
				(["math", str(n)], telebot.types.InlineQueryResultCachedPhoto(
					id=len(results)+10,
					title=latex_expr,
					photo_file_id=photo_id,
					description="Use previous expression :",
					caption=latex_expr
				))
			)
			n -= 1
	with last_code_shared as last_code: # Last sended code
		paste_id, lang, photo_id = last_code.get(username, (None, None, None))
		if paste_id:
			url = "http://pastebin.com/{}".format(paste_id)
			results.append(
				(["code", "paste"], telebot.types.InlineQueryResultCachedPhoto(
					id=len(results)+10,
					title=url,
					photo_file_id=photo_id,
					description="⌨️ Send pastebin {}".format(paste_id),
					caption=url
				))
			)
	return results

def filter_recent_items(query, results):
	return [b for l, b in results if [x for x in l if x.startswith(query)]]

@bot.inline_handler(func=lambda query: True)
def query_text(inline_query):
	query = inline_query.query.strip()
	log("GOT inline query from {} : {}".format(present_user(inline_query.from_user), repr(inline_query.query)))

	items = query.split(" ", 2)

	if query.startswith("send ") and len(items) == 3:
			bot.answer_inline_query(
				inline_query.id,
				[telebot.types.InlineQueryResultCachedPhoto(
					id=0,
					title=items[2],
					photo_file_id=items[1],
					description=items[2],
					caption=items[2]
				)],
			)
			return
	if query.startswith("send_code ") and len(items) == 3:
			bot.answer_inline_query(
				inline_query.id,
				[telebot.types.InlineQueryResultCachedPhoto(
					id=0,
					title=items[2],
					photo_file_id=items[1],
					description=items[2],
					caption=items[2]
				)],
			)
			return

	recent_items = filter_recent_items(query, get_inline_query_results_lasts(inline_query))
	if not recent_items and CONF.expose_url:
	# if query and CONF.expose_url:
		bot.answer_inline_query(
			inline_query.id,
			get_inline_query_results_generated(inline_query),
		)
	else:
		bot.answer_inline_query(
			inline_query.id,
			recent_items,
			cache_time=0,
			is_personal=True,
			switch_pm_text=MESSAGES["switch_pm_text"],
			switch_pm_parameter="latex",
		)

## Unhandled input, callbacks

@bot.callback_query_handler(func=lambda call: True)
def  test_callback(call):
    if call.data == "show_help":
    	send_help_action(call.message.chat.id)
    elif call.data == "dont_care":
    	bot.edit_message_text(
    		chat_id=call.message.chat.id, message_id=call.message.message_id,
    		text=call.message.text
    	)

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
	back_thread.start()

	CONF.to_stdout()
	log("Hello ! I am {}".format(present_user(bot_user_infos) or ""))

	while True:
		try:
			bot.polling(none_stop=True)
		except KeyboardInterrupt as e:
			log("KeyboardInterrupt", e)
			raise e
		except Exception as ex:
			log("ERROR", ex)
			logger.error(ex)
		else:
			break
		finally:
			save_data()
		log("Relaunching bot in 10s...")
		time.sleep(10)