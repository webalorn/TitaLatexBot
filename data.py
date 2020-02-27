import json
from collections import defaultdict

class Config:
	def __init__(self, filename):
		self.filename = filename
		self.load()

	def load(self):
		with open(self.filename, "r") as json_conf_file:
			self.conf = json.load(json_conf_file)

		self.token = self.conf["token"] # Required
		self.nb_recent_items = self.conf.get("nb_recent_items", 5)
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

CONF = Config("conf.json")