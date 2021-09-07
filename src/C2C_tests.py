#!/bin/python
# from json.decoder import JSONDecodeError
# from textwrap import indent

from portalePICO.core import PortalePicoGTS

import signal
import os
import sys
import yaml

from os import get_terminal_size


from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.driver import ChromeDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.remote.webelement import WebElement


from time import sleep, time

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re
import textwrap

import logging

import traceback
from contextlib import contextmanager


import requests
from urllib3.exceptions import InsecureRequestWarning
import argparse

from portalePICO.utils import Trenitalia

import inspect

from MyCache.utils import Cache

from exceptions import BrowserNotInstalledException

from urllib.parse import urlparse

import logging

from infrastructure import EnvironmentParser, EnvironmentParsingException


from utility import executable_run_directly, getCorrectPath


def wait_user_if_launched_gui (text="Press ENTER to continue..."):
	"""If the compiled executable was launched by double-clicking on the file, ask for input with the specified text

	Args:
		text (str, optional): Text to show while waiting for input. Defaults to "Press ENTER to continue...".
	"""
	try:
		if executable_run_directly():
			print("You called the file by double-clicking")
			input(text)
		else:
			print("You called the file in the CLI. No need to wait for user input...")
	except:
		print("Random Exception was thrown")
		input(text)


EXIT_SUCCESS = 0
EXIT_FAILURE = 1

logger = logging.getLogger(__name__)

"""
	DESCRIZIONE:
		Script per i Test mattutini di PICO
	
	AGGIORNAMENTI:
		- 30/10/20: Aggiunto controllo validità stazione 
		- 31/10/20: Aggiunto Context Manager per gestire le eccezioni, aggiunta eccezione di rete, modificato formatting e migliorato logging
		- 01/11/20: Aggiunta misurazione performance, aggiunta eccezione di rete, aggiunto percorso anche quando si usa la versione eseguibile
		- 01/11/20: Aggiunti parametri da CLI, aggiunto controllo raggiungibilità macchina tramite richiesta HTTP (molto più veloce)
		- 17/11/20: Rimosse alcune funzioni di sviluppo, aggiunto controllo se esce la richiesta di acquisto Andata e Ritorno, aggiunto Help per file di configurazione
		- 24/11/20: Aggiunti più tentativi di ricerca, dato che la mattina ci mette troppo e va in timeout. Creazione di file con stacktrace e screenshot in caso di Eccezione non gestita

	APPUNTI DI SVILUPPO:
		- Per la compilazione: pyinstaller --clean --name "Test_acquisto-C2C" --log-level=WARN --onefile --noconfirm --add-data="./conf/;./conf/" .\C2C_tests.py
"""

# From: https://stackoverflow.com/a/242531/8965861
# def info(type, value, tb):
#     if hasattr(sys, 'ps1') or not sys.stderr.isatty():
#     # we are in interactive mode or we don't have a tty-like
#     # device, so we call the default hook
#         sys.__excepthook__(type, value, tb)
#     else:
#         import traceback, pdb
#         # we are NOT in interactive mode, print the exception...
#         traceback.print_exception(type, value, tb)
#         print
#         # ...then start the debugger in post-mortem mode.
#         # pdb.pm() # deprecated
#         pdb.post_mortem(tb) # more "modern"

# sys.excepthook = info

def getEntryPoint():
	is_executable = getattr(sys, 'frozen', False)
	
	if is_executable:
		# print("Program is an executable")
		return sys.executable

	# print("Program is a script")
	return inspect.stack()[-1][1]


def uri_exists_stream(uri: str) -> bool:
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    try:
        with requests.head(uri, stream=True, allow_redirects=True, headers=headers, verify=False) as response:
            try:
                response.raise_for_status()
                return True
            except requests.exceptions.HTTPError:
                return False
    except requests.exceptions.ConnectionError:
        return False



def merge_dicts(*dict_args):
	"""
	Given any number of dictionaries, shallow copy and merge into a new dict,
	precedence goes to key value pairs in latter dictionaries.
	"""
	result = {}
	for dictionary in dict_args:
		result.update(dictionary)
	return result



# Returns the Status code of the uri requested. Find more at httpstatusrappers.com :)
#
# https://stackoverflow.com/a/13641613
def getStatusCode(uri: str) -> int:
	"""Returns the Status code of the uri requested. Find more at httpstatusrappers.com :)
	
	https://stackoverflow.com/a/13641613

	Args:
		uri (str): [description]

	Returns:
		int: Returns the Status Code, or False if the url was not found
	"""
	headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
	requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

	# prints the int of the status code. 
	try:
		r = requests.head(uri, allow_redirects=True, headers=headers, verify=False)
		return r.status_code
	except requests.ConnectionError:
		return False



def signal_handler(sig, frame):
	"""Executed when the user types CTRL+C

	Args:
		sig ([type]): [description]
		frame ([type]): [description]
	"""
	print("\n")
	print("==================================================")
	print("Test interrotto dall'utente".center(50))
	print("==================================================")
	
	sys.exit(0)


class C2C_Interface(object):
	"""Utility methods for C2C (Pico4UK)"""
	browser = None

	def __init__(self, driver: webdriver.Chrome) -> None:
		self.browser = driver

	@staticmethod		
	def isProgressBarActive (d):
		return len(d.find_elements_by_id("nprogress")) == 0

	@staticmethod		
	def waitUntilPageLoaded (browser: webdriver.Chrome, timeout: int = 30):
		"""Waits until the page has finished loading (by watching the progress bar)

		Args:
			browser (webdriver.Chrome): The Webdriver instance
			timeout (int, optional): Timeout of the operation in seconds. Defaults to 30.
		"""
		sleep(1)
		WebDriverWait(browser, timeout).until(C2C_Interface.isProgressBarActive)


	@staticmethod		
	def getAllModals(browser: webdriver.Chrome):
		"""Returns a list of all VISIBLE modals present in the page

		Args:
			browser (webdriver): The webdriver instance

		Returns:
			list: The C2C modals
		"""
		modals_in_page = browser.find_elements_by_css_selector('[role=dialog] > .modal-dialog')
		modals_visible = [ modal for modal in modals_in_page if modal.is_displayed() ]

		if not modals_in_page or not modals_visible:
			return None

		parsed_modal = []
		for curr_modal in modals_visible:
			modal_details = {
				"__html": curr_modal,
				"title": curr_modal.find_element_by_class_name("modal-title").get_attribute("innerText").strip(),
				"body": curr_modal.find_element_by_class_name("modal-body").get_attribute("innerText").strip(),
				"buttons": { button.get_attribute("innerText").strip(): button for button in curr_modal.find_elements_by_css_selector(".modal-footer button")}
			}

			parsed_modal.append(modal_details)

		return parsed_modal

	@staticmethod		
	def getForegroundModal(browser: webdriver.Chrome):
		"""Returns a dictionary describing a C2C modal or None if not present.
			Known titles:
				- Your c2c session has timed out.
				- Error [text: "Oops, something went wrong."]
				- Please note [text: "Some of your journey results continue into another day"]


		Args:
			browser (webdriver): The webdriver instance

		Returns:
			dict: The C2C modal
		"""
		modals_in_page = C2C_Interface.getAllModals(browser)

		if not modals_in_page:
			return None

		modal = modals_in_page.pop(-1)

		return modal

	@staticmethod
	def isModalPresent(browser: webdriver.Chrome, title=None):
		fg_modal = C2C_Interface.getForegroundModal(browser)

		if title:
			return bool(fg_modal and fg_modal["title"] == title)
		
		return bool(fg_modal)

	@staticmethod		
	def waitForModalPresent(browser: webdriver.Chrome, title=None, timeout=30):
		"""Waits until a modal is shown

		Args:
			browser (webdriver.Chrome): The Webdriver instance
			title (str, optional): The title of the modal to search. Defaults to None.
			timeout (int, optional): Timeout. Defaults to 30.

		Returns:
			dict: Dictionary containing the modal data
		"""
		WebDriverWait(browser, timeout).until(lambda s: C2C_Interface.isModalPresent(s, title))

		return C2C_Interface.getForegroundModal(browser)
	
	@staticmethod		
	def waitForModalNotPresent(browser: webdriver.Chrome, title=None, timeout=30):
		"""Waits until a modal is shown

		Args:
			browser (webdriver.Chrome): The Webdriver instance
			title (str, optional): The title of the modal to search. Defaults to None.
			timeout (int, optional): Timeout. Defaults to 30.
		"""
		WebDriverWait(browser, timeout).until(lambda s: not C2C_Interface.isModalPresent(s, title))

	
	@staticmethod
	def getSection(browser: webdriver.Chrome):
		if not browser.find_elements_by_tag_name("router-view"):
			raise Exception("Main 'router-view' element not found")

		PAGE_TO_DICT = {
			"html": browser.find_element_by_tag_name("router-view"),
			"header": browser.find_element_by_css_selector("router-view > div.header-container"),
			"body": {
				"title": "",
				"html": browser.find_element_by_css_selector("router-view > div.container"),
				"main_content": {
					"html": None,
					"buttons": {}
				},
				"sidebar": None
			}
		}


		# Se non è vuoto il contenuto (ad esempio nella pagina di Ricerca)
		html_main_content = PAGE_TO_DICT["body"]["html"].find_element_by_css_selector("div[slot='main-content']")
		
		# Se sono presenti elementi (qualsiasi sezione tranne pagina di ricerca)
		if len(html_main_content.find_elements_by_css_selector("*")) > 0:
			
			PAGE_TO_DICT["body"]["title"] = browser.execute_script("""
				return Array.from(document.querySelectorAll("div[slot='main-content'] h2.au-target, div[slot='main-content'] .h2.au-target")).map(e => e.innerText.trim()).join(" / ")
			""")

			PAGE_TO_DICT["body"].update({
				"main_content": {
					"html": html_main_content,
					"buttons": { button.get_attribute("innerText").strip(): button for button in html_main_content.find_elements_by_css_selector("div.row > div > .btn.btn-primary.btn-block") },
				}
			})

		else:
			PAGE_TO_DICT["body"]["title"] = "Search page"
		
		# Se è presente la Sidebar (Es. carrello)
		if PAGE_TO_DICT["body"]["html"].find_elements_by_css_selector("div[slot='sidebar']"):
			PAGE_TO_DICT["body"]["sidebar"] = PAGE_TO_DICT["body"]["html"].find_element_by_css_selector("div[slot='sidebar']"),

		return PAGE_TO_DICT

	@staticmethod
	def set_value(input_elem: WebElement, new_value: str, interval_seconds: float = 1.5):
		input_elem.click()
		input_elem.clear()
		input_elem.send_keys(Keys.CONTROL, 'a' + Keys.BACK_SPACE)
		input_elem.send_keys(new_value)

		# WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//span[@id='spnStatusConexao' and contains(text(),'online')]")))

		sleep (interval_seconds)

		return str(input_elem.get_attribute("value")).strip() == str(new_value).strip()


class DebugManager(object):
	__driver = None

	exception_log_filename = ""
	exception_png_filename = ""

	def __init__(self, instance_identifier) -> None:
		FILE_PATH = os.path.dirname(os.path.realpath(__file__))
		self.exception_log_filename = os.path.join(FILE_PATH, f"DebugC2C-beforeExceptionExit-{instance_identifier}.log")
		self.exception_png_filename = os.path.join(FILE_PATH, f"DebugC2C-beforeExceptionExit-{instance_identifier}.png")

	def setDriver(self, driver):
		self.__driver = driver

	def dumpException(self):
		print("Stacktrace:")
		traceback.print_stack()

		with open(self.exception_log_filename, "w") as stacktrace_file:
			traceback.print_stack(file=stacktrace_file)

		if self.__driver:
			self.__driver.save_screenshot(self.exception_png_filename)

	@staticmethod
	def dump(instance_identifier, driver: ChromeDriver = None, with_screenshot = False, with_stacktrace=False, print_stacktrace=False):
		"""Dumps to the filesystem a file containing the tacktrace and/or a screenshot of the current page

		Args:
			instance_identifier (str): Unique identifier
			driver (ChromeDriver, optional): WebDriver instance to use for the screenshot. Defaults to None.
			with_screenshot (bool, optional): Whether to print a screenshot of the current webpage to file. Defaults to False.
			with_stacktrace (bool, optional): Whether to save the stacktrace to file. Defaults to False.
			print_stacktrace (bool, optional): Whether to print the stacktrace to screen. Defaults to False.
		"""
		if print_stacktrace:
			print("Stacktrace:")
			traceback.print_stack()

		CREATED_FILES = []
		
		FILE_PATH = os.path.dirname(os.path.realpath(getEntryPoint()))
		dump_time = datetime.now().strftime('%Y%m%d_%H%M%S')

		exception_log_filename = os.path.join(FILE_PATH, f"Debug-{dump_time}-{instance_identifier}.log")
		exception_png_filename = os.path.join(FILE_PATH, f"Debug-{dump_time}-{instance_identifier}.png")

		if with_stacktrace:
			with open(exception_log_filename, "w") as stacktrace_file:
				traceback.print_stack(file=stacktrace_file)
				CREATED_FILES.append(exception_log_filename)

		if driver and with_screenshot:
			driver.save_screenshot(exception_png_filename)
			CREATED_FILES.append(exception_png_filename)
		
		return CREATED_FILES



			

@contextmanager
def StartTest(url, visible=False):
	"""
	Wrapper around the tests.
	This ensures the test is ALWAYS ended gracefully, doing some clean-up before exiting (https://book.pythontips.com/en/latest/context_managers.html#implementing-a-context-manager-as-a-generator)

	Args:
		headless (bool): Wether to start the instance as a headless browser (background, no GUI) or not. Defaults to True
	
	Yields:
		selenium.webdriver.Chrome: The selenium webdriver instance used for the test
	"""
	test_start = time()

	# Default Browser flags
	chrome_flags = [
		"--disable-extensions",
		"start-maximized",
		"--disable-gpu",
		"--ignore-certificate-errors",
		"--ignore-ssl-errors",
		#"--no-sandbox # linux only,
		"--log-level=3",	# Start from CRITICAL
	]
	
	if not visible: chrome_flags.append("--headless")

	# Instantiate the Options object
	chrome_options = Options()
	for flag in chrome_flags: chrome_options.add_argument(flag)

	# To remove '[WDM]' logs (https://github.com/SergeyPirogov/webdriver_manager#configuration)
	os.environ['WDM_LOG_LEVEL'] = '0'
	os.environ['WDM_PRINT_FIRST_LINE'] = 'False'

	# To remove "DevTools listening on ws:..." message (https://stackoverflow.com/a/56118790/8965861)
	chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

	__driver = None

	domain = urlparse(url).netloc.split(":")[0]
	errorManager = DebugManager(f"C2C_{domain}_{datetime.now().strftime('%Y%m%d-%H%M%S')}")

	try:	
		__driver = webdriver.Chrome( ChromeDriverManager(log_level=0).install(), options=chrome_options )
		__driver.set_window_size(1920, 1080)

		errorManager.setDriver(__driver)
		
		yield __driver

	except WebDriverException as ex:
		print("------------------- WebDriverException -------------------")

		# errorManager.dumpException()
		FILE_PATH = os.path.dirname(os.path.realpath(getEntryPoint()))
		dump_time = datetime.now().strftime('%Y%m%d_%H%M%S')

		exception_log_filename = os.path.join(FILE_PATH, f"Debug-{domain}-{dump_time}.log")
		exception_png_filename = os.path.join(FILE_PATH, f"Debug-{domain}-{dump_time}.png")
		__driver.save_screenshot(exception_png_filename)


		if "net::ERR_CONNECTION_TIMED_OUT" in ex.msg:
			print("FATAL ERROR - La connessione con il server è andata in Timeout. \nCodice di errore net::ERR_CONNECTION_TIMED_OUT\n")
		
		elif "net::ERR_CONNECTION_REFUSED" in ex.msg:
			print("FATAL ERROR - Impossibile contattare il server. \nCodice di errore net::ERR_CONNECTION_REFUSED\n")

		elif re.match(pattern="unknown error: cannot find .* binary", string=ex.msg):
			browser = re.match(pattern="unknown error: cannot find (.*?) binary", string=ex.msg).group(1)

			raise BrowserNotInstalledException(browser)

		else:
			print(f"OTHER ERROR - Message: {ex}")
			# print(f"sys.exc_info(): {sys.exc_info()}")
			# print("Stacktrace:")
			# traceback.print_stack()
			print("Stacktrace 2:")
			print(traceback.format_exc())
			print("\n")
	

	except Exception as exception:
		print("------------------- Exception -------------------")
		print(f"Message: {exception}")
		# print(f"sys.exc_info(): {sys.exc_info()}")
		# print("Stacktrace:")
		logger.exception(f"Exception: {exception}")
		# errorManager.dumpException()


	finally:
		if visible: 
			# pdb.post_mortem()
			input("DEBUG MODE - Premi INVIO per continuare")
	
		if __driver is not None: 
			print("\n\n+++++++++++++++++++ DESTROYING DRIVER... PLEASE WAIT... +++++++++++++++++++\n")
			# __driver.close()
			__driver.quit()
			print("\n\n+++++++++++++++++++ DRIVER SUCCESSFULLY DESTROYED! +++++++++++++++++++")

		test_end = time()
		print(f"Durata test: {timedelta(seconds=int(test_end - test_start))}")

		print()

	# Propagate the Exception
	return True



def singleNodeTest_C2C (url, visible: bool=False, skip_payment: bool=False) -> bool:
	"""
	Starts the browser
	

	Args:
		url (str): The URL of the node to test
		visible (bool, optional): Wether to show the UI while executing the test. Can potentially alter the test results, so use with caution. Defaults to False.
		skip_payment (bool, optional): Wether to stop at the payment phase. Defaults to False.

	Raises:
		Exception: DOM Exceptions, all exceptions are caught by the 'StartTest' ContextManager

	Returns:
		bool: True if test succeeded, False otherwise
	"""
	print("")
	print("PRECONDIZIONI - Operazioni preliminari:")

	print("\tControllo raggiungibilita' front-end: \t", end="", flush=True)

	if not uri_exists_stream(url):
		print("ERRORE (Front-End non raggiungibile)")
		return False

	print("OK")


	with StartTest(url=url, visible=visible) as driver:
		print("\tAttendo il caricamento della pagina: \t", end="", flush=True)
		driver.get(url)
		
		try:
			# Start condition: indica che la pagina di arrivo ha caricato
			WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#tickets")))

			C2C_Interface.waitUntilPageLoaded(driver, 60)
		except TimeoutException:
			print("ERRORE")
			return False

		print("OK")






		# -------------------------------------------------------------------------------------
		# 								Chiusura Banner fastidiosi
		# -------------------------------------------------------------------------------------
		# Per Produzione (chiude tutti i banner della PUBBLICITA che si presentano)
		print("\tControllo la presenza di banner: \t", end="", flush=True)
		
		sleep(5)
		n_banner = 0
		try:
			close_buttons = WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[id^=yie-overlay] button[id^=yie-close-button]")))
			for close_btn in close_buttons: 
				try:
					close_btn.click()
				except Exception as e:
					pass
				else: 
					n_banner += 1
		except TimeoutException:
			pass
		
		if n_banner > 0: 
			print(f"OK (Chiusi {n_banner} banner)")
		else: 
			print("OK (Nessun banner trovato)")


		# Per Produzione (chiude tutti i banner dei COOKIE che si presentano)
		print("\tControllo la presenza di Cookie: \t", end="", flush=True)
		try:
			ACCEPT_COOKIES = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "CybotCookiebotDialogBodyButtonAccept")))
			ACCEPT_COOKIES.click()
			
			print(f"OK (Accettata Policy sui Cookie)")
		except TimeoutException:
			print("OK (Banner con la Policy sui Cookie assente)")
			pass
		




		# -------------------------------------------------------------------------------------
		# 								Ricerca della soluzione
		# -------------------------------------------------------------------------------------
		MAX_ATTEMPTS_SEARCH = 3
		
		retry_start = time()
		for retryIndex in range(1, MAX_ATTEMPTS_SEARCH):
			try:
				print("")
				print("PAGINA - Ricerca soluzione:")
				print(f"PAGINA - {C2C_Interface.getSection(driver)['body']['title']}: ")
				SEARCH_FORM = driver.find_element_by_css_selector("div#tickets[role='tabpanel'] > search-ticket > form[role='form']")


				# 1) 	Stazione di PARTENZA
				print("\tImposto stazione di partenza: \t\t", end="", flush=True)
				stazione_partenza = SEARCH_FORM.find_element_by_css_selector("div.bro-tickets-origin w-locations input.tt-input")
				for i in range(5):
					if C2C_Interface.set_value(stazione_partenza, TRAVEL_DETAILS["departure"]):
						break


				# 1.2) 	Controlla se la stazione esiste
				stazioni_trovate = SEARCH_FORM.find_elements_by_css_selector("div.bro-tickets-origin w-locations div.tt-menu > .tt-dataset > div.tt-suggestion")
				if len(stazioni_trovate) <= 0:
					print(f"ERRORE (Nessuna stazione trovata corrispondente al nome: '{TRAVEL_DETAILS['departure']}')")
					return False

				# 1.3) 	Seleziona la stazione
				stazioni_trovate[0].click()
				print(f"OK - Selezionata '{stazioni_trovate[0].get_attribute('innerText').strip()}' (Stazioni trovate: {', '.join([ div.get_attribute('innerText').strip() for div in stazioni_trovate ])})")





				# 2)	Stazione di ARRIVO
				print("\tImposto stazione di arrivo: \t\t", end="", flush=True)
				stazione_arrivo = SEARCH_FORM.find_element_by_css_selector("div.bro-tickets-destination w-locations input.tt-input")
				for i in range(5):
					if C2C_Interface.set_value(stazione_arrivo, TRAVEL_DETAILS["arrival"]):
						break

				# 2.2) 	Controlla se la stazione esiste
				stazioni_trovate = SEARCH_FORM.find_elements_by_css_selector("div.bro-tickets-destination w-locations div.tt-menu > .tt-dataset > div.tt-suggestion")
				if len(stazioni_trovate) <= 0:
					print(f"ERRORE (Nessuna stazione trovata corrispondente al nome: '{TRAVEL_DETAILS['arrival']}')")
					return False


				# 2.3) 	Seleziona la stazione
				stazioni_trovate[0].click()
				print(f"OK - Selezionata '{stazioni_trovate[0].get_attribute('innerText').strip()}' (Stazioni trovate: {', '.join([ div.get_attribute('innerText').strip() for div in stazioni_trovate ])})")





				# 3)	Imposto SOLO ANDATA
				print("\tSeleziono checkbox 'One way': \t\t", end="", flush=True)
				SEARCH_FORM.find_element_by_id("oneway").click()
				print("OK")


				# 4)	Metto la DATA di partenza
				print("\tImposto data e ora di partenza: \t", end="", flush=True)
				elem_date = SEARCH_FORM.find_element_by_css_selector("div.bro-tickets-outward > .bro-tickets-outward-date > w-datetime > .date-picker-container > input.form-control.au-target")
				# elem_date.click()

				# Il metodo clear() non funziona. Mi tocca usare il buon vecchio CTRL + A + Del :)
				# elem_date.send_keys(Keys.CONTROL, 'a' + Keys.BACK_SPACE)
				# elem_date.send_keys(TRAVEL_DETAILS['travel_date'])
				# sleep(0.5)
				C2C_Interface.set_value(elem_date, TRAVEL_DETAILS["travel_date"], interval_seconds=0.5)
				elem_date.send_keys(Keys.TAB)
				


				# ORA di partenza
				elem_time = SEARCH_FORM.find_element_by_css_selector("div.bro-tickets-outward > .bro-tickets-outward-time > w-datetime > .date-picker-container > input.form-control.au-target")
				C2C_Interface.set_value(elem_time, TRAVEL_DETAILS["travel_time"], interval_seconds=0.5)
				elem_time.send_keys(Keys.TAB)

				sleep(1)


				# Controllo che la data sia rimasta consistente e che non ci siano stati errori nella trascrizione
				if (elem_date.get_attribute("value").strip().replace("/", "-") != TRAVEL_DETAILS['travel_date']):
					print("WARNING - Data inserita differente da quella indicato")
				else:
					print("OK")


				print("\n\tCerco soluzioni di viaggio: \t\t", end="", flush=True)
				search_start = time()

				SEARCH_FORM.submit()






				# Aspetta il caricamento della pagina fino a 5 minuti
				try:
					C2C_Interface.waitUntilPageLoaded(driver, 300)
					search_end = time()
				except TimeoutException:
					search_end = time()
					print(f"ERRORE (Durata ricerca eccessiva: {timedelta(seconds=int(search_end - search_start))})")

					return False
				

				if C2C_Interface.isModalPresent(driver):
					modal = C2C_Interface.getForegroundModal(driver)

					if modal["title"] == "Gateway Time-out":
						print(f"ERRORE - Tento un'altra ricerca ('{ modal['title'] }')")
						modal["buttons"]["Close"].click()
						continue
					
					elif modal["title"] == "Please note" and modal["body"] == "Some of your journey results continue into another day":
						# print(f"INFO - Una parte del viaggio verra' fatta in un altro giorno ('{ modal['body'] }')")
						modal["buttons"]["Close"].click()

					else:
						DebugManager.dump("C2C-SearchUnexpectedDialog", driver, with_screenshot=True)
						
						print(f"ERRORE - Trovato dialog: {modal['title']}")
						print(f"Maggiori dettagli: {modal}")
						
						return False

				
				

				print(f"OK (Durata ricerca: {timedelta(seconds=int(search_end - search_start))})")
				break

			except TimeoutException as e:
				retry_end = time()

				print(f"ERRORE - Ricerca andata in Timeout (durata procedura: {timedelta(seconds=int(retry_end - retry_start))}]). Tentativo {retryIndex} di {MAX_ATTEMPTS_SEARCH} in corso...\n\n")
				
				# Controlla se è presente un modal (Es. Generic error)
				modal = C2C_Interface.getForegroundModal(driver)
				if modal:
					print(f"\n\nTrovato modal: {modal['title']}\n")
					print(f"Dettagli: {modal}")
					DebugManager.dump("C2C-SearchGenericTimeout", driver, with_screenshot=True)
			





		# -------------------------------------------------------------------------------------
		# 									Outward journey
		# -------------------------------------------------------------------------------------
		MAX_ATTEMPTS_BOOKING = 5

		print("")
		print("PAGINA - Lista soluzioni trovate:")
		print(f"PAGINA - {C2C_Interface.getSection(driver)['body']['title']}: ")
		print("\tControllo soluzioni > 0: \t\t", end="", flush=True)

		solutions = driver.find_elements_by_css_selector("#solutions-A-singles > fieldset#solutions-fieldset-A-singles .au-target.panel")
		if len(solutions) <= 0:
			error_text = driver.find_element_by_id("singles-A").get_attribute("innerText").strip()
			
			print(f"ERRORE - Nessuna soluzione trovata ({error_text})")
			return False

		print (f"OK (trovate {len(solutions)} soluzioni)")


		for tentativo in range(1, MAX_ATTEMPTS_BOOKING):
			selected_solution = driver.find_element_by_css_selector('#solutions-A-singles > fieldset#solutions-fieldset-A-singles .au-target.panel.panel-primary')

			print(f"\tSeleziono soluzione intermedia: \t", end="", flush=True)


			mid_solution_id = int(len(solutions) / 2)
			solutions[mid_solution_id].find_element_by_name("radio-offers-A-best").click()

			selected_solution = driver.find_element_by_css_selector('#solutions-A-singles > fieldset#solutions-fieldset-A-singles .au-target.panel.panel-primary')

			if solutions[mid_solution_id] == selected_solution: 
				print(f"OK (soluzione n. {mid_solution_id})\n")
			else:
				print(f"WARNING (non sono riuscito a selezionare la soluzione intermedia)\n")

			print(f"\tClicco su 'Continue' e aspetto: \t", end="", flush=True)

			wait_start = time()

			continue_button = driver.find_element_by_css_selector("#basket-panel > .panel-body button.btn.btn-primary")
			continue_button.click()


			try:
				# Aspetta fino a 2 minuti
				C2C_Interface.waitUntilPageLoaded(driver, 120)
				wait_end = time()

				# Controllo se c'è un dialog
				try:
					modal = C2C_Interface.waitForModalPresent(driver, timeout=3)

					# Sui sistemi NO-PROD la prima volta che si effettua la ricerca viene resituito QUASI SEMPRE errore 500, quindi va rieseguita
					if modal["title"] == "Oops, something's not right.":
						print("ERRORE - Trovato dialog di errore 'Oops, something's not right.'")
						modal["buttons"]["Close"].click()
						
						# Aspetto che il dialog sia chiuso
						try:
							C2C_Interface.waitForModalNotPresent(driver, title=modal["title"])
							
							print(f"Chiuso. Tento un'altra volta (Tentativo n.{tentativo+1} su 5)...\n")
							continue
						except TimeoutException:
							print(f"Tempo di chiusura superato (30s). Salvato nuovo screenshot\n")
							DebugManager.dump("C2C-DialogClosingTimeout", driver, with_screenshot=True)
							continue
					else:
						# Se si tratta di un dialog inatteso esci
						print(f"WARNING - Trovato dialog non previsto '{modal['title']}' (Durata attesa: {timedelta(seconds=int(wait_end - wait_start))})")
						DebugManager.dump("C2C-BookingUnexpectedDialog", driver, with_screenshot=True)
						return False

				except TimeoutException:
					# Nessun dialog presente
					pass
				
				print(f"OK (Durata attesa: {timedelta(seconds=int(wait_end - wait_start))})")
				break
			except TimeoutException:
				wait_end = time()
				print(f"ERRORE (Durata attesa eccessiva: {timedelta(seconds=int(wait_end - wait_start))})")

				return False
		else:
			print(f"ERRORE (Superato limite MASSIMO di tentativi per la prenotazione: {MAX_ATTEMPTS_BOOKING})")

			return False
		



		# -------------------------------------------------------------------------------------
		# 							Select options and add extras
		# -------------------------------------------------------------------------------------
		print("")
		print(f"PAGINA - Select options and add extras: ")
		print(f"PAGINA - {C2C_Interface.getSection(driver)['body']['title']}: ")

		
		print(f"\tClicco su pulsante 'Continue': \t\t", end="", flush=True)
		continue_button = driver.find_element_by_css_selector("#basket-panel > .panel-body button.btn.btn-primary")
		continue_button.click()

		# Wait until it asks for the Login Credentials
		try:
			modal = C2C_Interface.waitForModalPresent(driver, title="Login please")["__html"]
		except TimeoutException:
			print("ERRORE (Non ho trovato il dialog 'Login please')")

			return False

		# Sometimes there could be a warning dialog. Close it. 
		#Sorry, it has not been possible to book some legs, for which reservation was optional. You can buy this ticket without reservations. Contact the train operating company for assistance in after-sale booking.
		try:
			warning_dialog = C2C_Interface.waitForModalPresent(driver, title="Warning", timeout=3)
			
			if "Close" in warning_dialog["buttons"]:
				warning_dialog["buttons"]["Close"].click()
				C2C_Interface.waitForModalNotPresent(driver, title=warning_dialog["title"])
			
			print(f"OK - Incontrato dialog 'WARNING': {warning_dialog}")
		except TimeoutException:
			print("OK")


		# Switching to the 'Continue as a guest' section of the 'Login please' dialog
		print(f"\tCompilo sezione 'Continue as a guest': \t", end="", flush=True)
		modal.find_element_by_id("guest").click()

		# Insert required email address
		modal.find_element_by_id("loginEmail").send_keys(USER["email"] + Keys.TAB)
		modal.find_element_by_id("repeatEmail").send_keys(USER["email"] + Keys.TAB)
		print("OK")


		# Submit the form
		print(f"\tProcedo ai metodi di consegna: \t", end="", flush=True)
		modal.find_element_by_id("loginEmail").submit()

		
	


		# -------------------------------------------------------------------------------------
		# 								Select a delivery option
		# -------------------------------------------------------------------------------------
		try:
			C2C_Interface.waitUntilPageLoaded(driver, 60)
			
			WebDriverWait(driver, 90).until(EC.visibility_of_element_located((By.TAG_NAME, "delivery-method")))
			print("OK")
		except TimeoutException:
			print("ERRORE (Non sono arrivato alla sezione 'Select a delivery option')")

			return False


		print("")
		print(f"PAGINA - Select a delivery option: ")
		print(f"PAGINA - {C2C_Interface.getSection(driver)['body']['title']}: ")

		print("\tEspando `Collect at the station`: \t", end="", flush=True)

		# Expanding `Collect at the station` section
		driver.find_element_by_id("delivery-station").click()

		# Wait until content is visible
		WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#collapse-station input#name")))
		print("OK")

		
		# Setting the First and Last Name
		print("\tCompilo con i dati richiesti: \t\t", end="", flush=True)
		driver.find_element_by_css_selector("#collapse-station input#name").send_keys(USER["firstName"] + Keys.TAB)
		driver.find_element_by_css_selector("#collapse-station input#surname").send_keys(USER["lastName"] + Keys.TAB)
		
		# Checking "I am a non-UK resident" checkbox
		driver.find_element_by_css_selector("#collapse-station #ukresident").click()
		print("OK")

		# Click on the 'Continue' button
		C2C_Interface.getSection(driver)["body"]["main_content"]["buttons"]["Continue"].click()

		# Wait until progress bar has finished loading
		C2C_Interface.waitUntilPageLoaded(driver, 60)

		# Click on the 'Accept the Terms and Conditions'
		print("\tClicco su 'Accept Terms/Conditions': \t", end="", flush=True)
		try:
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "acceptConditions")))
			driver.find_element_by_id("acceptConditions").click()
			print("OK - Ho spuntato la checkbox 'Accept the Terms and Conditions'")
		except TimeoutException:
			print("OK - Nessuna checkbox 'Accept the Terms and Conditions' trovata")

		# Click on the 'Continue' button
		print("\tClicco su 'Continue': \t\t\t", end="", flush=True)
		C2C_Interface.getSection(driver)["body"]["main_content"]["buttons"]["Continue"].click()
		print("OK")

		C2C_Interface.waitUntilPageLoaded(driver, 30)
		


		# -------------------------------------------------------------------------------------
		# 									Pay by Card
		# -------------------------------------------------------------------------------------
		print("")
		print(f"PAGINA - Pay by card: ")
		print(f"PAGINA - {C2C_Interface.getSection(driver)['body']['title']}: ")

		# Address, City and Postal Code
		print("\tCompilo con i dati postali: \t\t", end="", flush=True)
		driver.find_element_by_id("postalCodeInput").send_keys("TEST" + Keys.TAB)
		driver.find_element_by_id("firstLine").send_keys("TEST" + Keys.TAB)
		driver.find_element_by_id("cityTown").send_keys("TEST" + Keys.TAB)
		print("OK")


		# Click on the 'Continue' button
		print("\tClicco su 'Continue': \t\t\t", end="", flush=True)
		C2C_Interface.getSection(driver)["body"]["main_content"]["buttons"]["Continue"].click()
		print("OK")

		
		# Wait until N&TS page
		print("\tAspetto il caricamento di N&TS: \t", end="", flush=True)
		try: 
			# Aspetto fino all'entrata nella pagina di NETS
			WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.data[id='data']")))
			print("OK")

			sleep(0.5)

		except (TimeoutException) as ex:
			# If there was an error during the loading
			if driver.find_elements_by_id("errorExc"):
				errore_transazione_text = driver.find_element_by_id("errorExc").get_attribute('innerText').strip().replace('\n', ' ').replace('\r', '')

				print(f"ERRORE ({errore_transazione_text})")
				
			return False
		
		except:
			print(f"ERRORE GENERICO")
			return False





		# -------------------------------------------------------------------------------------
		# 								Pagina di pagamento N&TS
		# -------------------------------------------------------------------------------------
		print("\nPAGINA - Pagina di pagamento N&TS:", flush=True)

		# If we don't need to test the payment (ex. Production environment) skip to the end.
		if skip_payment:
			print("\tOK - E' stato specificato di saltare la fase di pagamento. Tutte le altre funzionalita' sono valide.")
			return True

		print("\tInserisco dati carta: \t\t\t", end="", flush=True)
		driver.find_element_by_css_selector("input[name='ACCNTFIRSTNAME']").send_keys(str(CARD["firstName"]) + Keys.TAB)
		driver.find_element_by_css_selector("input[name='ACCNTLASTNAME']").send_keys(str(CARD["lastName"]) + Keys.TAB)
		driver.find_element_by_css_selector("input[name='PAN']").send_keys(str(CARD["number"]) + Keys.TAB)

		select_mese = Select(driver.find_element_by_id("EXPDT_MM"))
		select_mese.select_by_visible_text((datetime.now()).strftime('%m'))
		
		select_anno = Select(driver.find_element_by_id("EXPDT_YY"))
		select_anno.select_by_visible_text((datetime.now() + relativedelta(years=1)).strftime('%Y'))

		driver.find_element_by_css_selector("input[name='CVV']").send_keys(str(CARD["csc"]) + Keys.TAB)
		print("OK")

		# Clicco su 'Continua'
		print("\tClicco su 'Continua': \t\t\t", end="", flush=True)
		driver.find_element_by_id("continue").click()
		print("OK")

		# Aspetto fino alla pagina di conferma dei dati della Carta
		WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "modify")))

		# Clicco su 'Conferma'
		print("\tClicco su 'Conferma': \t\t\t", end="", flush=True)
		driver.find_element_by_id("confirm").click()
		print("OK")



		# -------------------------------------------------------------------------------------
		# 							Pagina di conferma prenotazione (OTP)
		# -------------------------------------------------------------------------------------
		print("\nPAGINA - Pagina 'SECURE CHECKOUT':", flush=True)
		try:
			# Aspetto fino alla pagina di conferma dei dati della Carta
			print("\tCaricamento pagina: \t\t\t", end="", flush=True)
			WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.ID, "challengeDataEntry")))
			print("OK - Trovata richiesta di inserimento OTP")
		except TimeoutException:
			# Se la pagina non si carica
			print("ERRORE - Nessuna richiesta di OTP trovata")
		else:
			OTP = "111111"
			print("\tInserimento OTP: \t\t\t", end="", flush=True)
			driver.find_element_by_id("challengeDataEntry").send_keys(OTP + Keys.TAB)
			sleep(0.5)
			print(f"OK - Inserito OTP '{OTP}'")

			print("\tClicco su 'Submit': \t\t\t", end="", flush=True)
			driver.find_element_by_id("confirm").click()
			print(f"OK")




		print("")
		print("\tEmail di conferma: \t\t\t", end="", flush=True)

		try:
			modal = C2C_Interface.waitForModalPresent(driver)

			if modal["title"] == "Email confirmation":
				print("OK - Trovato dialog di conferma email")
				return True

			print("ERRORE - Trovato dialog: " + str(modal["title"]))
			return False

		except TimeoutException:
			content = C2C_Interface.getSection(driver)["body"]["main_content"]["html"]
			
			if content.find_elements_by_css_selector("confirmationp > div > h2.au-target"):				
				booking_is_confirmed = content.find_element_by_css_selector("confirmationp > div > h2.au-target").get_attribute("innerText").strip() == "Your booking is confirmed"
				
				if booking_is_confirmed:
					print("OK (Warning: non è stato trovato il dialog con la conferma email)")
					return True


			print("ERRORE")
			return False


		return False


def repeat_string(string: str, length: int):
	"""Repeat a string N times

	Args:
		string (str): String/character to be repeated
		length (int): Number of times to repeat the string

	Returns:
		[type]: [description]
	"""
	return (string * length)[0:length]


if __name__ == "__main__":
	program_start = time()

	APP_ID = "Test_Mattutini_C2C"
	APP_VERSION = "0.7.0"
	APP_DATA = {}

	try:
		window_size = get_terminal_size()

		CONSOLE_WIDTH = window_size.columns
		CONSOLE_HEIGTH = window_size.lines
	except:
		CONSOLE_WIDTH = 130
		
			
	PROJECT_NAME = "C2C"

	FILE_PATH = os.path.dirname(os.path.realpath(__file__))
	DEBUG = True

	DEFAULT_AMBIENTI = [ 
		"Certificazione", 
		# "Corr-Blue", 
		# "Corr-Green",
		"Correttiva",
		# "Prod-Blue", 
		# "Prod-Green",
	]
	
	DEFAULT_STAZIONI = {
		"partenza": "London Terminals",
		"arrivo": "Grays",
	}

	"""
		--------------------------------------------------------------------------------------------
										ARGUMENT PARSING
		--------------------------------------------------------------------------------------------
	"""
	SCRIPT_INVOCATION = f"python {os.path.split(sys.argv[0])[1]}" if str(sys.argv[0]).endswith(".py") else os.path.split(sys.argv[0])[1]

	# Esempi da mostrare nell'Help
	esempi = [
		{
			"code": f"{SCRIPT_INVOCATION} Correttiva",
			"desc": "Effettua i test solo per i nodi della cella attiva di Correttiva."
		},
		{
			"code": f"{SCRIPT_INVOCATION}",
			"desc": "Effettua i test per le celle attive di Correttiva e Certificazione"
		},
		{
			"code": f"{SCRIPT_INVOCATION} -P 'Milano Centrale' -A 'Roma Termini'",
			"desc": "Effettua i test utilizzando come stazione di partenza 'Milano Centrale' e stazione di arrivo 'Roma Termini'"
		},
		{
			"code": f"{SCRIPT_INVOCATION} -c conf/my_config.yml",
			"desc": "Effettua i test utilizzando la configurazione definita nel file (path relativo)"
		},
		{
			"code": f"{SCRIPT_INVOCATION} --config 'C:\\Users\\Luca Salvarani\\Desktop\\Script\\Test_Mattutini_PICO\\conf\\my_config.yml'",
			"desc": "Effettua i test utilizzando la configurazione definita nel file (path assoluto)"
		},
	]
	esempi_text = ''.join([ f"\t{ex['code']}\n\t\t{ex['desc']}\n\n" for ex in esempi ])


	# Firma da mostrare nell'Help
	FIRMA = "Luca Salvarani - luca.salvarani@ibm.com"
	
	# Descrizione del programma
	DESCRIPTION = (
		f"Script per il testing automatico degli ambienti NOPROD di {PROJECT_NAME} - Versione {APP_VERSION}\n"
	)

	# Costruisco il footer
	FOOTER = textwrap.dedent(f'''\
		------------

		Informazioni aggiuntive:
			Di default il test verra' effettuato sugli ambienti di Certificazione, Formazione, Integrazione e Training (in quest'ordine).
			Questo comportamento puo' essere sovrascritto specificando dalla linea di comando gli ambienti desiderati (vedi esempi). 
			
			Cio' potrebbe tornare utile per eseguire un test di acquisto mirato ad uno specifico ambiente dopo un deploy.

        
		Struttura file di configurazione:
			Il file di configurazione deve essere in formato yaml. I parametri non riconosciuti verranno ignorati e 
			sostituiti da quelli di default. Nell'esempio sottostante sono presenti TUTTI i parametri configurabili

			Esempio di file di configurazione:
			---     # Questa riga fa parte del contenuto del file e ne indica l'inizio
			# Configurazione carta (per pagamento sulla pagina di N&TS)
			card:
				firstName:  Bruce
				lastName:   Lee
				number:     4539999999999993
				exp_date:   12/2022
				csc:        111


			# Configurazione dati passeggero da inserire in fase di prenotazione
			passenger:
				firstName:  Bruce
				lastName:   Qui
				email:      test.email@test.com
				tel_number: 0123456789
				birth_date: 29/02/2000


			# Per personalizzare la tratta del viaggio senza dover sempre specificarla tramite i 
			#  parametri `-P` e `-A`
			travel:
				departure:  Mantova              # Stazione di partenza
				arrival:    Torino               # Stazione di arrivo
			

		Aggiornamento configurazione infrastrutturale:
			Al primo avvio il programma si connettera' al Portale Pico GTS per scaricarsi le configurazioni dei nodi (PICO, NUGO, C2C e BT) e salvarle nella home dell'utente.
			Questo file di configurazione verra' aggiornato automaticamente ogni settimana. 

			Se al primo avvio il Portale non fosse raggiungibile il programma si blocchera' e dira' di ritentare una volta tornato raggiungibile. 
			Se invece cio' dovesse accadere ad un aggiornamento successivo, verra' automaticamente usata la configurazione vecchia, e l'aggiornamento sara' rimandato all'avvio successivo.

		Esempi:
         ''')

	FOOTER += (
		f"{esempi_text}\n \n"
		f"{FIRMA}"
	)

	parser = argparse.ArgumentParser(
		description=DESCRIPTION,
		epilog=FOOTER,
		formatter_class=argparse.RawDescriptionHelpFormatter,
		allow_abbrev=True,
		add_help=False
	)
	parser.add_argument('ambienti', nargs='*', default=DEFAULT_AMBIENTI, metavar="ambiente",
	 	help="Uno o piu' nomi degli ambienti su cui effettuare i test (es. Certificazione) separati da spazi. Il nome deve essere scritto ESATTAMENTE come nel PortalePicoGTS. Ciò perchè viene effettuata una corrispondenza Case-Sensitive. Per un controllo degli ambienti disponibili vai su http://ngppgtsfe.pico.gts/was/ng-nodes."
	)

	stazioni = parser.add_argument_group('Opzioni di ricerca')

	stazioni.add_argument("-A", "--stazione-arrivo", help=f"Indica la stazione di arrivo (default={DEFAULT_STAZIONI['arrivo']})", dest="stazione_arrivo", default=DEFAULT_STAZIONI["arrivo"], metavar="stazione")
							   
	stazioni.add_argument("-P", "--stazione-partenza", help=f"Indica la stazione di partenza (default={DEFAULT_STAZIONI['partenza']})", dest="stazione_partenza", default=DEFAULT_STAZIONI["partenza"], metavar="stazione")
							   

	
	special = parser.add_argument_group('Opzioni speciali')
	special.add_argument("-S", "--salta-pagamento", 
					help=f"Se questo flag e' attivo il test si fermera' prima di arrivare alla pagina di pagamento N&TS. Utile per fare i test di acquisto su Produzione, dove non e' valida la carta di test.", 
					dest="skip_payment", default=False, action="store_true")
	
	
	files = parser.add_argument_group('Opzioni di configurazione')

	files.add_argument("-c", "--config", help=f"Specifica il percorso del file di configurazione (vedi il paragrafo 'Struttura file di configurazione' per meggiori dettagli)", dest="path_custom_config", metavar="percorso_file")

	altre_opzioni = parser.add_argument_group('Altre opzioni')

	altre_opzioni.add_argument("-f", "--force-update", help="Forza l'aggiornamento del file di configurazione dell'infrastruttura",
						action="store_true", dest="force_update")

	altre_opzioni.add_argument("-l", "--list-options", help="Mostra tutti gli ambienti disponibili con la configurazione corrente",
						action="store_true", dest="show_available_environments")
	
	altre_opzioni.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                   		help='Mostra questo messaggio ed esce')

	altre_opzioni.add_argument("-V", "--version", help="Mostra la versione del programma ed esce",
						action='version', version=f"%(prog)s {APP_VERSION}")

	altre_opzioni.add_argument("-X", "--show-browser", help="Rende visibile il browser durante i test. Utilizzare unicamente per debug, non utilizzare se non si sa esplicitamente cosa si sta facendo! Non si assicura la veridicita' dei test ne' il funzionamento dello script dopo aver abilitato tale opzione!",
						action='store_true', dest="show_browser")


	CLI_ARGS = parser.parse_args()

	signal.signal(signal.SIGINT, signal_handler)


	if DEBUG: 
		print(f"{repeat_string('-', CONSOLE_WIDTH)}\n	")
		print(f"TEST MATTUTINI {PROJECT_NAME} - VERSIONE DI SVILUPPO v.{APP_VERSION}".center(CONSOLE_WIDTH))
		print("")
		print("In fase di test si prega di lanciare il programma con 'nomeprogramma.exe | Tee-Object -Append -FilePath \"terminal.log\"'".center(CONSOLE_WIDTH))
		print("Questo file andra' poi condiviso se vengono trovati degli errori nel programma\n".center(CONSOLE_WIDTH))
		print(f"{repeat_string('-', CONSOLE_WIDTH)}\n	")



	
	"""
		--------------------------------------------------------------------------------------------
										CONFIGURATION LOADING
		--------------------------------------------------------------------------------------------
	"""
	# Infrastruttura
	cache = Cache("Test_Mattutini_Nodi_Infrastruttura.yaml", apiVersion=APP_VERSION, maximumTime=604800)
	APP_DATA = cache.getCache()
	
	if not APP_DATA or CLI_ARGS.force_update:
		print("Avvio aggiornamento del file di configurazione infrastrutturale...")

		if PortalePicoGTS.isReachable():
			try:
				cache.setCache(Trenitalia.getInfrastructure())
				APP_DATA = cache.getCache()

				if not "data" in APP_DATA:
					print("Nessun dato ricavato dall'analisi del portale")
					sys.exit(1)
			
			except BrowserNotInstalledException as e:
				print(f"ERRORE CRITICO - Il browser '{e.browser}' non è installato sul sistema. Procedura annullata")

				sys.exit(2)

			except Exception as e:
				print(f"CRITICAL ERROR - Fallito update infrastruttura con errore: {e}")

			nodes = APP_DATA["data"]
		else:
			print(f"Impossibile collegarsi al Portale PICO GTS ({PortalePicoGTS.getUrl()}) per l'aggiornamento del file di configurazione.")

			if CLI_ARGS.force_update:
				print("Impossibile forzare l'aggiornamento. \n")

			elif not cache.exists():
				print("FATAL ERROR - Per la prima configurazione e' mandatoria la disponibilita del portale per prendere i nodi infrastrutturali\n")
				
				sys.exit(99)
		
			print("Uso configurazione vecchia... Verra' aggiornata appena sara' raggiungibile il portale..\n")
			APP_DATA = cache.getCache(check_expired=False)


	nodes = APP_DATA["data"]

	
	# Carta
	with open(getCorrectPath(os.path.join("conf","mock_card.yml")), 'r') as stream:
		CARD = yaml.safe_load(stream)


	# Utente
	with open(getCorrectPath(os.path.join("conf","mock_user.yml")), 'r') as stream:
		USER = yaml.safe_load(stream)




	TRAVEL_DETAILS = {
		"departure": CLI_ARGS.stazione_partenza,
		"arrival": CLI_ARGS.stazione_arrivo,
		"travel_date": (datetime.now() + relativedelta(days=5)).strftime('%d-%m-%Y'),
		"travel_time": "12"
	}	


	USER_CONFIGURATION = {}
	if CLI_ARGS.path_custom_config is not None:
		try:
			with open(os.path.realpath(CLI_ARGS.path_custom_config), 'r') as stream:
				USER_CONFIGURATION =  yaml.safe_load(stream)
				
		except FileNotFoundError as e:
			print("TEST ABORTITO - File di Configurazione Utente non trovato")
			print(e)

			sys.exit(2)
		except yaml.YAMLError as e:
			print("TEST ABORTITO - File di Configurazione Utente non valido")
			print(e)

			sys.exit(2)


		if "card" in USER_CONFIGURATION:
			CARD = merge_dicts(CARD, USER_CONFIGURATION["card"])

		if "passenger" in USER_CONFIGURATION:
			USER = merge_dicts(USER, USER_CONFIGURATION["passenger"])

		if "travel" in USER_CONFIGURATION:
			TRAVEL_DETAILS = merge_dicts(TRAVEL_DETAILS, USER_CONFIGURATION["travel"])

			
		# sys.exit()
	

	if not PROJECT_NAME in nodes:
		print (f"Progetto '{PROJECT_NAME}' non esistente")
	
	VALID_ENVIRONMENTS  = [ key for key in nodes[PROJECT_NAME].keys() if "VIP_EXT" in nodes[PROJECT_NAME][key] ]
	

	# Se è stato richiesto il solo display degli ambienti disponibili
	if CLI_ARGS.show_available_environments: 
		print("Ambienti disponibili per il test:")
		for ambiente in VALID_ENVIRONMENTS: 
			if ambiente.startswith("Corr-Blue"): print("\t- Correttiva (nodo attivo)")
			if ambiente.startswith("Prod-Blue"): print("\t- Produzione (nodo attivo)")
			print(f"\t- {ambiente}")
		
		print("")
		
		sys.exit(0)


	"""
		--------------------------------------------------------------------------------------------
										CONFIGURATION PROCESSING
		--------------------------------------------------------------------------------------------
	"""


	print("Dettagli dati da inserire:")
	print(f"\tStazione di partenza: \t{TRAVEL_DETAILS['departure']}")
	print(f"\tStazione di arrivo: \t{TRAVEL_DETAILS['arrival']}\n")

	print(f"\tData di partenza: \t{TRAVEL_DETAILS['travel_date']}")
	print(f"\tOrario di partenza: \t{TRAVEL_DETAILS['travel_time']}\n")



	"""
		--------------------------------------------------------------------------------------------
												TEST START
		--------------------------------------------------------------------------------------------
	"""
	all_test_start = time()

	risultati_test = {}

	if not PROJECT_NAME in nodes:
		print(f"Nessuna configurazione presente corrispondente alla voce '{PROJECT_NAME}'")
		sys.exit(2)

	try:
		for ambiente in CLI_ARGS.ambienti:
			print(repeat_string('-', CONSOLE_WIDTH))
			print (f"Test di acquisto per {ambiente.title()}")

			try:
				parsed_env = EnvironmentParser(project=PROJECT_NAME, environment=ambiente)
				# print(vars(parsed_env))
			except EnvironmentParsingException as e:
				print("Errore: " + str(e))
				# logger.exception("ERRORE")


			# Se l'ambiente non esiste nella configurazione dell'infrastruttura
			if not parsed_env.name_short in nodes[PROJECT_NAME]:
				print (f"\nATTENZIONE - L'ambiente '{parsed_env.name_short}' non esiste o il file di configurazione potrebbe non essere aggiornato.")
				continue


			# Ricava tutti i nodi appartenenti al binomio ambiente-cella richiesti
			if parsed_env.has_multi_cell:
				if parsed_env.is_active_cell: 
					ENDPOINT = [ jvm["urls"]["https"] for jvm in nodes[PROJECT_NAME][parsed_env.name_short]["VIP_EXT"]["VIP_EXT"] if jvm["jvm_name"].lower() == "active" ]
				else:
					ENDPOINT = [ jvm["urls"]["https"] for jvm in nodes[PROJECT_NAME][parsed_env.name_short]["VIP_EXT"]["VIP_EXT"] if jvm["jvm_name"].lower() == "not active" ]
			else:
				ENDPOINT = [ jvm["urls"]["https"] for jvm in nodes[PROJECT_NAME][parsed_env.name_short]["VIP_EXT"]["VIP_EXT"] ]


			# Se è la prima volta che viene testato questo ambiente, inizializza il Dictionary dei risultati con i valori di default
			if not parsed_env.name_short in risultati_test:
				risultati_test[parsed_env.name_short] = {
					"totale_nodi": len(ENDPOINT),
					"risultati": [],
					"cella_attiva": ("Attiva" if parsed_env.is_active_cell else "Passiva") if parsed_env.has_multi_cell else None,
					"nome_completo": parsed_env.name_full
				}
			

			for index, url in enumerate(ENDPOINT):
				print(f"{parsed_env.name_short} B2C [nodo {index+1} di {len(ENDPOINT)}] - {url}")
				
				test_success = singleNodeTest_C2C(url, visible=CLI_ARGS.show_browser, skip_payment=CLI_ARGS.skip_payment)
				

				risultati_test[parsed_env.name_short]["risultati"].append({
					"nodo": index+1,
					"url": url,
					"result": test_success
				})

				if test_success:
					print(f"************** TEST OK [{parsed_env.name_full} {index+1}/{len(ENDPOINT)}] **************")
				else:
					print(f"!?!?!?!?!?!? TEST KO [{parsed_env.name_full} {index+1}/{len(ENDPOINT)}] ?!?!?!?!?!?!")

			print("\n")

	except BrowserNotInstalledException as e:
		print(f"ERRORE CRITICO - Il browser '{e.browser}' non è installato sul sistema. Procedura annullata")

		exit(2)
	
	if not CLI_ARGS.ambienti:
		print(repeat_string('-', CONSOLE_WIDTH))
		print("                                       ATTENZIONE                                            ")
		print("              Nessun ambiente specificato. Aggiungine uno per iniziare i test.				")
		print("  Per un controllo degli ambienti disponibili vai su http://ngppgtsfe.pico.gts/was/ng-nodes	")
		print(repeat_string('-', CONSOLE_WIDTH))



	program_end = time()

	SEPARATOR = repeat_string("-", CONSOLE_WIDTH)

	print("\n\n")
	print(SEPARATOR)
	print("Riepilogo Generale".center(CONSOLE_WIDTH))
	print(SEPARATOR)
	print("")
	print("---------------------------".center(CONSOLE_WIDTH))
	print("|  Statistiche generiche  |".center(CONSOLE_WIDTH))
	print("---------------------------".center(CONSOLE_WIDTH))
	print("")
	print(f"- Durata complessiva test:     {timedelta(seconds=int(program_end - all_test_start))} -".center(CONSOLE_WIDTH))
	print(f"- Durata totale programma:     {timedelta(seconds=int(program_end - program_start))} -".center(CONSOLE_WIDTH))
	print("\n\n")
	print("--------------------".center(CONSOLE_WIDTH))
	print("|  Risultati Test  |".center(CONSOLE_WIDTH))
	print("--------------------".center(CONSOLE_WIDTH))

	for ambiente in risultati_test:
		titolo_ambiente = risultati_test[ambiente]["nome_completo"]
		if risultati_test[ambiente]["cella_attiva"]:
			print(f"{titolo_ambiente.title()} ({risultati_test[ambiente]['cella_attiva'].title()}):")
		else:
			print(f"{titolo_ambiente.title()}:")

		for test in risultati_test[ambiente]["risultati"]:
			ip_add = "not active" if "test" in test['url'] else "active"

			print(f"\t{test['nodo']}) Nodo {ip_add}: \t{ 'Ok' if test['result'] else 'Fallito' }\t\t[{test['url']}]")

		print("")

	if not all([ risultato["result"] for ambiente in risultati_test for risultato in risultati_test[ambiente]["risultati"] ]):
		pass
		# print("\n\n")
		# print("Aiuto".center(CONSOLE_WIDTH))
		# print("- Controlla la log per vedere dove sono FALLITI i test.. -".center(CONSOLE_WIDTH))
		# print("- Puoi rilanciare i test falliti semplicemnte rilanciando il programma con l'ambiente corrispondente come parametro -".center(CONSOLE_WIDTH))
	
	print("\n\n")
	print("Suggerimento".center(CONSOLE_WIDTH))
	print("Per una lista completa delle opzioni disponibili rilancia il programma fornendo il parametro '-h'".center(CONSOLE_WIDTH))


	print(SEPARATOR + "\n")
	
	wait_user_if_launched_gui("Premi INVIO per continuare...")

	ALL_TESTS_OK = all([ risultato["result"] for ambiente in risultati_test for risultato in risultati_test[ambiente]["risultati"] ])
	
	# Exit with useful RC
	sys.exit(EXIT_SUCCESS if ALL_TESTS_OK else EXIT_FAILURE)