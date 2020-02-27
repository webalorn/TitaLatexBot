from PIL import Image, ImageOps, UnidentifiedImageError
from urllib.parse import quote
from urllib.request import urlopen

from threading import current_thread
import os, subprocess
from src.data import *
from src.utility import *

class InvalidLatexErr(Exception):
	pass

def remove_accents(expression):
	return unidecode.unidecode(expression)

def png_post_process(filename, remove_alpha=False, expand=False):
	try:
		image = Image.open(filename).convert("RGBA")
	except UnidentifiedImageError: # In case of invalid expression
		raise InvalidLatexErr

	if expand:
		image = ImageOps.expand(image, CONF.image_border)
	if remove_alpha:
		canvas = Image.new('RGBA', image.size, (255,255,255,255))
		canvas.paste(image, mask=image)
		image = canvas
	image.save(filename, format="PNG")


## Using CodeGogs API

def tex2png_codegogs(filename, expression):
	# Preparing text strings
	expression = remove_accents(expression)
	filename += ".png"
	server = "http://latex.codecogs.com/png.download?"
	size = "%5Cdpi%7B300%7D%20"

	# Quote expression
	expression = quote(expression)
	url = server + size + expression

	# Download file from url and save to output_file:
	with urlopen(url) as response, open(filename, 'wb') as output_file:
		data = response.read()  # A bytes object
		output_file.write(data)
	png_post_process(filename, remove_alpha=True, expand=True)

	return filename

## Using local latex generation

def tex2png_local(filename, expression):
	filename_png = filename + ".png"
	filename_latex = filename + ".tex"
	dest_dir = "/".join(filename.split("/")[:-1])

	latex_code = LATEX_TEMPLATE.replace("<formula>", expression)
	with open(filename_latex, "w") as tmp_latex_file:
		tmp_latex_file.write(latex_code)

	with open(os.devnull, "w") as null_file:
		r = subprocess.call(
			["latex",
			"-src",
			"-interaction=nonstopmode",
			"--output-directory="+dest_dir,
			filename_latex],
			stdout=null_file, stderr=null_file
		)
		if r:
			raise InvalidLatexErr

		subprocess.call([
			"dvipng",
			"-T", "tight",
			"-D", str(CONF.dpi),
			filename + ".dvi",
			"-o", filename_png
		],
		stdout=null_file, stderr=null_file
		)

	png_post_process(filename_png, expand=True)
	return filename_png

## Main latex conversion functions

if CONF.use_local_latex:
	with open("template.tex", "r") as template_f:
		LATEX_TEMPLATE = template_f.read()
	tex2png = tex2png_local
else:
	import unidecode
	tex2png = tex2png_codegogs

def tex2filename(expression):
	"""
	Convert expression to an image called results/hash.png
	"""
	expression = expression.strip()
	expr_encoded = hash_dn(expression)
	filename_result = "results/" + expr_encoded + ".png"

	if os.path.exists(filename_result):
		return filename_result
	else:
		with non_valid_latex_shared as non_valid_latex:
			if expr_encoded in non_valid_latex:
				return None

	filename_tmp = "results/" + current_thread().name + "_tmp"

	try:
		tmp_location = tex2png(filename_tmp, expression)
	except InvalidLatexErr:
		with non_valid_latex_shared as non_valid_latex:
			non_valid_latex.add(expression)
		return None

	os.rename(tmp_location, filename_result)
	return filename_result