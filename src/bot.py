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
			types.InlineKeyboardButton("🖼️ Image", url=filename2url(filename)),
			types.InlineKeyboardButton("✉️ Send", switch_inline_query=inline_query)
		)
		bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg.message_id, reply_markup=markup)
	return True

def handle_expression(text, message, is_text=False):
	if text and text[0] != "/":
		if not send_equation(message.chat.id, text, message.from_user, is_text=is_text):
			bot.reply_to(message, "Invalid latex expression")
	else:
		bot.reply_to(message, MESSAGES["no_latex_in_cmd"])

def try_command_code(message, fail_silent=False, has_cmd_text=True, command_text=None):
	if not command_text:
		command_text = message.text
	params = command_text.split()
	if not has_cmd_text:
		params = ["/code"] + params
	if len(params) != 2 and len(params) != 3:
		if not fail_silent:
			bot.send_message(message.chat.id, MESSAGES["code_cmd_explanation"])
		return False
	paste_id = extract_pastebin(params[1])
	if not paste_id:
		if not fail_silent:
			bot.send_message(message.chat.id, MESSAGES["invalid_pastebin_id"])
		return False

	lang = "" if len(params) == 2 else params[2]
	url = "http://pastebin.com/raw/{}".format(paste_id)
	url_paste = "http://pastebin.com/{}".format(paste_id)

	filename = None
	try:
		filename = code2filename(url, lang)
	except InvalidRessouce:
		if not fail_silent:
			bot.send_message(message.chat.id, MESSAGES["invalid_pastebin_id"])
		return False

	if filename:
		with open(filename, 'rb') as img:
			msg = bot.send_photo(message.chat.id, img, caption=url_paste)
		with last_code_shared as last_code:
			last_code[message.from_user.username] = (paste_id, lang, msg.photo[0].file_id)

		inline_query = " ".join(["send_code", str(msg.photo[0].file_id), url_paste])
		markup = types.InlineKeyboardMarkup(row_width=2)
		markup.row(
			types.InlineKeyboardButton("🖥 Image", url=filename2url(filename)),
			types.InlineKeyboardButton("✉️ Send", switch_inline_query=inline_query)
		)
		bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=msg.message_id, reply_markup=markup)
	else:
		bot.send_message(message.chat.id, MESSAGES["code_error"], parse_mode="HTML")
	return True

@bot.message_handler(commands=['start'])
def send_welcome(message):
	log_message(message)
	start_content = " ".join(message.text.strip().split()[1:])
	if start_content == "latex":
		bot.send_message(message.chat.id, MESSAGES["latex_start"])
	else:
		markup = types.InlineKeyboardMarkup(row_width=2)
		markup.row(
			types.InlineKeyboardButton("📜 Show commands list", callback_data="show_help"),
			types.InlineKeyboardButton("❌ I don't care", callback_data="dont_care"),
		)
		bot.send_message(message.chat.id, MESSAGES["start"], reply_markup=markup)

def send_help_action(chat_id):
	bot.send_message(chat_id, MESSAGES["help"].format(bot_user_infos.username), parse_mode="HTML", disable_web_page_preview=True)

@bot.message_handler(commands=['help'])
def send_help(message):
	log_message(message)
	send_help_action(message.chat.id)

def send_about_action(chat_id):
	bot.send_message(chat_id, MESSAGES["about"].format(bot_user_infos.username), parse_mode="HTML", disable_web_page_preview=True)

@bot.message_handler(commands=['about'])
def send_help(message):
	log_message(message)
	send_about_action(message.chat.id)

@bot.message_handler(commands=['latex', 'text'])
def send_expression(message):
	log_message(message)
	text_parts = message.text.strip().split(" ", 1)
	text = text_parts[1] if len(text_parts) >= 2 else ""
	handle_expression(text, message, text_parts[0] == "/text")

## Code and pastes

@bot.message_handler(commands=['code'])
def send_code(message):
	log_message(message)
	try_command_code(message)

def try_paste_to_code(message, paste_id):
	if not try_command_code(message, has_cmd_text=False, fail_silent=True, command_text=paste_id):
		markup = types.InlineKeyboardMarkup(row_width=2)
		markup.row(
			types.InlineKeyboardButton("🖼 Try again", callback_data="try_again_paste " + paste_id),
			types.InlineKeyboardButton("❌ Hide", callback_data="dont_care"),
		)
		bot.send_message(message.chat.id, MESSAGES["paste_spam"].format(paste_id), reply_markup=markup)

@bot.message_handler(commands=['paste'])
def send_code(message):
	parts = message.text.strip().split(' ', 1)
	if len(parts) < 2:
		bot.send_message(message.chat.id, MESSAGES['paste_no_node'])
		return
	code = parts[1]
	success, results = create_paste(code, message.from_user)
	if success:
		try_paste_to_code(message, results)
	else:
		bot.send_message(message.chat.id, "An error occured when trying to upload your code : {}".format(results))

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
def callback_handler(call):
	items = call.data.split(' ', 1)
	call_cmd = items[0]
	call_content = items[1] if len(items) > 1 else ""

	if call_cmd == "show_help":
		send_help_action(call.message.chat.id)
	elif call_cmd == "dont_care":
		bot.edit_message_text(
			chat_id=call.message.chat.id, message_id=call.message.message_id,
			text=call.message.text
		)
	elif call_cmd == "try_again_paste":
		bot.delete_message(call.message.chat.id, call.message.message_id)
		try_paste_to_code(call.message, call_content)

@bot.message_handler(func=lambda message:message.chat.type == "private")
def text_handler(message):
	log_message(message)
	text = message.text.strip()
	if text in LOST:
		bot.send_message(message.chat.id, "How dare you !!??...\nI lost the game 👿")
	elif text.startswith("/"):
		cmd = text.split()[0]
		bot.send_message(message.chat.id, MESSAGES["invalid_command"].format(cmd))
	elif try_command_code(message, fail_silent=True, has_cmd_text=False):
		pass
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