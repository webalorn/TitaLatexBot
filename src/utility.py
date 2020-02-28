from threading import Thread
import base64, struct, time, re
from src.data import CONF, save_data

def present_user(user):
	return "{} (@{})".format(" ".join(
		[name for name in [user.first_name, user.last_name] if name]),
		user.username
	)

def filename2url(filename):
	return CONF.expose_url + filename

class BackgroundThread(Thread):
	def __init__(self, *kargs, daemon=True, **kwargs):
		super().__init__(*kargs, daemon=daemon, **kwargs)

	def run(self):
		while True:
			time.sleep(60*5)
			save_data()

log_file = None
def log(*args, sep=" ", end="\n"):
	global log_file
	if CONF.use_stdout:
		print(*args, sep=sep, end=end)
	else:
		if not log_file:
			log_file = open("log/stdout.log", "w")
		message = sep.join(args) + end
		log_file.write(message)
		log_file.flush()

def log_message(message):
	log("GOT message from {} : {}".format(present_user(message.from_user), repr(message.text)))

## Hashing function
# Original code and licence for theses 2 functions at : https://gist.github.com/Cilyan/9424144 (Written by : @Cilyan)
# I have altered them to accept non-ascii characters

def fnv64(data):
	hash_ = 0xcbf29ce484222325
	for b in data:
		hash_ *= 0x100000001b3
		hash_ &= 0xffffffffffffffff
		hash_ ^= b
	return hash_

def hash_dn(dn, salt="42"):
	# Turn dn into bytes with a salt
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

## Extracting from string

REGEX_PASTE = re.compile('^ *h?t?t?p?s?:?/?/?(?:pastebin.com/)?(?:raw/)?([0-9a-zA-Z]{8})/? *$', re.IGNORECASE)

def extract_pastebin(text):
	m = REGEX_PASTE.match(text)
	if m:
		return m.group(1)