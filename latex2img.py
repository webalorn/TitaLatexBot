from urllib.parse import quote
from urllib.request import urlopen
import PIL
from PIL import Image, ImageOps

import os, sys, unidecode

class InvalidLatexErr(Exception):
	pass

def remove_accents(expression):
	return unidecode.unidecode(expression)

def png_post_process(filename, remove_alpha=False, expand=0):
	try:
		image = Image.open(filename).convert("RGBA")
	except PIL.UnidentifiedImageError: # In case of invalid expression
		raise InvalidLatexErr

	if expand:
		image = ImageOps.expand(image, expand)
	if remove_alpha:
		canvas = Image.new('RGBA', image.size, (255,255,255,255))
		canvas.paste(image, mask=image)
		image = canvas
	image.save(filename, format="PNG")

def tex2png_codegogs(filename, expression):
	# Preparing text strings
	expression = remove_accents(expression)
	server = "http://latex.codecogs.com/png.download?"
	filename_alpha = filename + ".png"
	size = "%5Cdpi%7B300%7D%20"

	# Quote expression
	expression = quote(expression)
	url = server + size + expression

	# Download file from url and save to output_file:
	with urlopen(url) as response, open(filename_alpha, 'wb') as output_file:
		data = response.read()  # A bytes object
		output_file.write(data)
	png_post_process(filename_alpha, remove_alpha=True, expand=40)

	return filename_alpha