import json, os
from collections import defaultdict, deque
from threading import Lock

## Constants

DEFAULT_RECENTS = 5
DEFAULT_DPI = 600
LOST = set(["the game", "THE GAME", "game", "42"])

MESSAGES = {
	"start" : "Hello ! I am Tita-Latex, I am here to help you using latex in telegram. To start, directly type your latex code, or use :\n\n/latex [you code]\nOr if you want more informations : /help\n\n Enjoy !",
	"latex_start" : "Now, write your equation 😈",
	"switch_pm_text" : "Write an equation with me 😇",
	"no_latex_in_cmd" : "It would be nice to send your latex expression with \"/latex [expression]\", or by sending the code directly in the conversation",
	"invalid_latex_code" : "Ho no, my dear friend... Your latex code \"{}\" is invalid !",
	"help" : "While you can directly talk to me in latex, you can also use :\n/latex [expression]\nYou can use me as a good servant in any conversion by typing @{}. You can then select one of latest images you have generated, or directly type you code."
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

		self.expose_url = self.conf.get("expose_url", "")
		if self.expose_url and self.expose_url[-1] != "/":
			self.expose_url += "/"

	def to_stdout(self, hide_token=True):
		if not hide_token:
			print("Token : ", self.token)
		if self.expose_url:
			print("Inline mode : recent item and new expressions generation")
		else:
			print("Inline mode : only recent items")

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
		with non_valid_latex_shared as non_valid_latex, last_images_shared as last_images:
			data_dict = {
				"last_images" : {key:list(val) for key, val in last_images.items()},
				"non_valid_latex" : list(non_valid_latex),
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

	except FileNotFoundError:
		pass

## Manupulation of global objects

def add_recent_image_user(username, expression, photo_id):
	with last_images_shared as last_images:
		last_images[username].append((expression, photo_id))
		while len(last_images[username]) > CONF.nb_recent_items:
			last_images[username].popleft()

## Global objects

CONF = Config("conf.json")

non_valid_latex_shared = SharedGlobal(set())
last_images_shared = SharedGlobal(defaultdict(deque))
data_json_shared = SharedGlobal("")