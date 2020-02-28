import json, os
from collections import defaultdict, deque
from threading import Lock

## Constants

MAX_CODE_LINE_SIZE = 105
MAX_CODE_LINES = 50
DEFAULT_RECENTS = 5
DEFAULT_DPI = 600
LOST = set(["the game", "THE GAME", "game", "42"])

MESSAGES = {
	"start" : "Hello ! I am TitaLatex, I am here to help you using latex in telegram. To start, just type your latex code, or use :\n\n/latex [you code]\nBut I have other wonderful commands ! If you want more information : /help\n\n Enjoy ! ❤️",
	"latex_start" : "Now, write your equation 😈",
	"help" : ("So you want to learn how to use me ! ☺️🔧\n\n"
		"I have some commands you can use in private chat or in groups :\n"
		"❓ <b>/help </b> will show this message\n"
		" ∑ <b>/latex [LaTeX expression]</b> Use this command to generate an image from a math LaTeX code. This will be executed in a <em>math</em> environment. You can then forward the message, or send it in any chat by typing @{0}\n"
		"🔡 <b>/text [LaTeX expression]</b> Use this command to generate an image from a LaTeX code. In contrast to /latex, it will NOT be executed in a math environment. You can add math parts with $math_code$. You can then forward the message, or send it in any chat by typing @{0}\n"
		"⌨️ <b>/code [pastebin id] [language(optional)]</b> To use this command, you must create a paste on <a href='https://pastebin.com/'>pastebin</a>. Then, you must give me the id or the url of the paste. You can specify the language as a second and optional parameter, but <a href='https://www.overleaf.com/learn/latex/Code_listing#Supported_languages'>the list is very limited.</a>\n"
		"⌨️ <b>/about</b> About me, the wonderful Tita. I may be a bit narcissistic.\n"
		"\n"
		"You can also just send some text in our private conversation, and I will try to interpret it as math LaTeX or as a code if it's a pastebin URL.\n"
		"In any conversation, you can also call me using <b>inline mode</b> : start by typing <b>@{0}</b> in the message field, it will allow you to :\n"\
		"- Send the last code generated with /code : select the image, or type 'code'\n" \
		"- Send some of the last LaTeX images you created : select the image, or type 'math', or 1, 2, 3, etc.. for the last images.\n" \
		"- Generate a new LaTeX image by typing <b>@{0} [your LaTeX code]</b>\n"
		"\n"
		"I hope this can help you ! 😃"),
	"about" : ("I am tita, a bot 🤖🦾 built to help people with LaTeX when using Telegram.\n"
		"I was created by <a href='https://t.me/webalorn'>@webalorn</a> (the one you should complain to if I don't work well) using the beautiful <a href='https://www.python.org/'>python</a> language, the <a href='https://github.com/eternnoir/pyTelegramBotAPI'>pyTelegramBotAPI</a> library and <a href='https://www.tug.org/texlive/'>TeX Live</a>\n"
		"My source code is available on my <a href='https://github.com/webalorn/TitaLatexBot'>github repository</a>."
		),
	"switch_pm_text" : "➕ Write an equation with me ! 😇",
	"no_latex_in_cmd" : "It would be nice to send your latex expression with \"/latex [expression]\", or by sending the code directly in the conversation",
	"invalid_latex_code" : "Ho no, my dear friend... Your latex code \"{}\" is invalid !",
	"code_cmd_explanation" : "To use this command, you must send exaclty one or two parameters :\n-> The first must be the id of a document on pastebin.com (8 characters). Pastebin url is also valid.\n-> The second, optional, is the language of the code, or 'text' if this is plain text.",
	"code_error" : "I had an error... 😢\nThe language you have selected must be invalid.\n(Or maybe there is latex in the pastebin, which can cause the error)\nYou can check all the supported languages <a href='https://www.overleaf.com/learn/latex/Code_listing#Supported_languages'>here</a>",
	"invalid_pastebin_id" : "This pastebin code/id is not valid 😡",
}

## Bot configuration

class Config:
	def __init__(self, filename):
		self.filename = filename
		self.load()

	def load(self):
		with open(self.filename, "r") as json_conf_file:
			self.conf = json.load(json_conf_file)

		self.token = self.conf["token"] # Required
		self.use_local_latex = self.conf["use_local_latex"] # Required
		self.nb_recent_items = self.conf.get("nb_recent_items", DEFAULT_RECENTS)
		self.dpi = self.conf.get("latex_dpi", DEFAULT_DPI)
		self.image_border = self.conf.get("image_border", 0)
		self.use_stdout = self.conf.get("use_stdout", True)

		self.expose_url = self.conf.get("expose_url", "")
		if self.expose_url and self.expose_url[-1] != "/":
			self.expose_url += "/"

	def to_stdout(self, hide_token=True):
		from src.utility import log
		if not hide_token:
			log("Token : ", self.token)
		if self.expose_url:
			log("Inline mode : recent item and new expressions generation")
		else:
			log("Inline mode : only recent items")

## Global variables

class SharedGlobal:
	def __init__(self, val):
		self.val = val
		self.lock = Lock()

	def update(self, val, aquired=False):
		if aquired:
			self.val = val
		else:
			with self.lock:
				self.val = val

	def __enter__(self):
		self.lock.acquire()
		return self.val

	def __exit__(self, *args):
		self.lock.release()

## Saving and loading data

def save_data():
	with data_json_shared as old_json:
		with non_valid_latex_shared as non_valid_latex, \
			last_images_shared as last_images, \
			last_code_shared as last_code:
			data_dict = {
				"last_images" : {key:list(val) for key, val in last_images.items()},
				"non_valid_latex" : list(non_valid_latex),
				"last_code" : last_code
			}
		json_val = json.dumps(data_dict)

		if json_val != old_json:
			data_json_shared.update(json_val, aquired=True)
			with open("data_tmp.json", "w") as f:
				f.write(json_val)
				f.flush()
				os.fsync(f.fileno())
			os.rename("data_tmp.json", "data.json") # Atomic operation, ensures the data is not corrupted if the daemon thread is closed.

def load_data():
	try:
		with open("data.json", "r") as f:
			data = json.load(f)

		if "non_valid_latex" in data:
			non_valid_latex_shared.update(set(data["non_valid_latex"]))

		if "last_images" in data:
			with last_images_shared as last_images:
				for key, val in data["last_images"].items():
					last_images[key] = deque(val)
		last_code_shared.update(data.get("last_code", {}))

	except FileNotFoundError:
		pass

## Manipulation of global objects

def add_recent_image_user(username, expression, photo_id):
	with last_images_shared as last_images:
		last_images[username].append((expression, photo_id))
		while len(last_images[username]) > CONF.nb_recent_items:
			last_images[username].popleft()

## Global objects

CONF = Config("conf.json")

non_valid_latex_shared = SharedGlobal(set())
last_images_shared = SharedGlobal(defaultdict(deque))
last_code_shared = SharedGlobal({})
data_json_shared = SharedGlobal("")