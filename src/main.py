#!/bin/python
from os import get_terminal_size

if __name__ == "__main__":
	window_size = get_terminal_size()

	CONSOLE_WIDTH = window_size.columns
	CONSOLE_HEIGTH = window_size.lines
	
	APP_ID = "Test_Mattutini-General"
	APP_VERSION = "0.0.1"
	APP_DATA = {}


	print(F"{CONSOLE_WIDTH}, {CONSOLE_HEIGTH}")
