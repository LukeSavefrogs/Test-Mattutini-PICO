#!/bin/python
import inspect
from urllib.parse import urlparse

from webdriver_manager.driver import ChromeDriver
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
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException


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
import utility

from MyCache.utils import Cache

from exceptions import BrowserNotInstalledException

from infrastructure import get_active_cell

"""
	DESCRIZIONE:
		Script per i Test mattutini di PICO
	
	AGGIORNAMENTI:
		- 30/10/20: Aggiunto controllo validità stazione 
		- 31/10/20: Aggiunto Context Manager per gestire le eccezioni, aggiunta eccezione di rete, modificato formatting e migliorato logging
		- 01/11/20: Aggiunta misurazione performance, aggiunta eccezione di rete, aggiunto percorso anche quando si usa la versione eseguibile
		- 01/11/20: Aggiunti parametri da CLI, aggiunto controllo raggiungibilità macchina tramite richiesta HTTP (molto più veloce)
		- 17/11/20: Rimosse alcune funzioni di sviluppo, aggiunto controllo se esce la richiesta di acquisto Andata e Ritorno, aggiunto Help per file di configurazione
		- 05/12/20: Fixato bug per cui andava in errore quando un viaggio selezionato non aveva cambi

	APPUNTI DI SVILUPPO:
		- Per la compilazione: pyinstaller --clean --name "Test_acquisto-PICO" --log-level=WARN --onefile --noconfirm --add-data="./conf/;./conf/" .\pico_tests.py
		- Per la copia/upload: Copy-Item .\dist\Test_acquisto-* "\\172.30.62.6\gts\sharedScripts\Test di Acquisto"

		- Entrambi: pyinstaller --clean --name "Test_acquisto-PICO" --log-level=WARN --onefile --noconfirm --add-data="./conf/;./conf/" .\pico_tests.py; if ($?) { Copy-Item .\dist\Test_acquisto-* "\\172.30.62.6\gts\sharedScripts\Test di Acquisto" }
"""


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


def getEntryPoint():
	is_executable = getattr(sys, 'frozen', False)
	
	if is_executable:
		# print("Program is an executable")
		return sys.executable

	# print("Program is a script")
	return inspect.stack()[-1][1]



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



"""
██╗    ██╗ ██████╗   █████╗  ██████╗  ██████╗  ███████╗ ██████╗ 
██║    ██║ ██╔══██╗ ██╔══██╗ ██╔══██╗ ██╔══██╗ ██╔════╝ ██╔══██╗
██║ █╗ ██║ ██████╔╝ ███████║ ██████╔╝ ██████╔╝ █████╗   ██████╔╝
██║███╗██║ ██╔══██╗ ██╔══██║ ██╔═══╝  ██╔═══╝  ██╔══╝   ██╔══██╗
╚███╔███╔╝ ██║  ██║ ██║  ██║ ██║      ██║      ███████╗ ██║  ██║
 ╚══╝╚══╝  ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝      ╚═╝      ╚══════╝ ╚═╝  ╚═╝
"""
@contextmanager
def StartTest(url, visible=False):
	"""
	Wrapper around the tests.
	This ensures the test is ALWAYS ended gracefully, doing some clean-up before exiting (https://book.pythontips.com/en/latest/context_managers.html#implementing-a-context-manager-as-a-generator)

	Args:
		visible (bool): Wether to start the instance as a headless browser (background, no GUI) or not. Defaults to False
	
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
	errorManager = DebugManager(f"PICO_{domain}_{datetime.now().strftime('%Y%m%d-%H%M%S')}")

	try:	
		__driver = webdriver.Chrome( ChromeDriverManager(log_level=0).install(), options=chrome_options )
		__driver.set_window_size(1920, 1080)
		
		if visible: __driver.maximize_window()

		errorManager.setDriver(__driver)
		
		yield __driver

	except WebDriverException as ex:
		print("------------------- WebDriverException -------------------")

		# errorManager.dumpException()

		if "net::ERR_CONNECTION_TIMED_OUT" in ex.msg:
			print("FATAL ERROR - La connessione con il server è andata in Timeout. \nCodice di errore net::ERR_CONNECTION_TIMED_OUT\n")
		
		elif "net::ERR_CONNECTION_REFUSED" in ex.msg:
			print("FATAL ERROR - Impossibile contattare il server. \nCodice di errore net::ERR_CONNECTION_REFUSED\n")

		elif re.match(pattern="unknown error: cannot find .* binary", string=ex.msg):
			browser = re.match(pattern="unknown error: cannot find (.*?) binary", string=ex.msg).group(1)

			raise BrowserNotInstalledException(browser)

		else:
			DebugManager.dump("PICO-UnexpectedExceptionHandler", __driver, with_screenshot=True, with_stacktrace=True, print_stacktrace=True)
			print(f"OTHER ERROR - Message: {ex}")
			# print(f"sys.exc_info(): {sys.exc_info()}")
			# print("Stacktrace:")
			# traceback.print_stack()
			print("Stacktrace 2:")
			print(traceback.format_exc())
			print("\n")
	
	except Exception as exception:
		DebugManager.dump("PICO-UnexpectedExceptionHandler", __driver, with_screenshot=True, with_stacktrace=True, print_stacktrace=True)
		print("------------------- Exception -------------------")
		print(f"Message: {exception}")
		# print(f"sys.exc_info(): {sys.exc_info()}")
		# print("Stacktrace:")
		# errorManager.dumpException()

	finally:
		# input("DEBUG MODE - Premi INVIO per distruggere il driver")
	
		if __driver is not None: 
			print("\n\n+++++++++++++++++++ DESTROYING DRIVER... PLEASE WAIT... +++++++++++++++++++\n")
			__driver.quit()
			print("\n\n+++++++++++++++++++ DRIVER SUCCESSFULLY DESTROYED! +++++++++++++++++++")

		test_end = time()
		print(f"Durata test: {timedelta(seconds=int(test_end - test_start))}")

		print()



"""
████████╗███████╗███████╗████████╗    ██╗      ██████╗  ██████╗ ██╗ ██████╗
╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝    ██║     ██╔═══██╗██╔════╝ ██║██╔════╝
   ██║   █████╗  ███████╗   ██║       ██║     ██║   ██║██║  ███╗██║██║     
   ██║   ██╔══╝  ╚════██║   ██║       ██║     ██║   ██║██║   ██║██║██║     
   ██║   ███████╗███████║   ██║       ███████╗╚██████╔╝╚██████╔╝██║╚██████╗
   ╚═╝   ╚══════╝╚══════╝   ╚═╝       ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝ ╚═════╝
"""
def singleNodeTest (url, visible: bool=False, skip_payment: bool=False) -> bool:
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

	# For debug purposes - Always make the tests successful
	# return True

	# For debug purposes - Return a random Boolean
	# return bool(random.getrandbits(1))

	print("Controllo raggiungibilita' front-end:\t\t", end="", flush=True)

	# front_end_raggiungibile = getStatusCode(url)

	if not uri_exists_stream(url):
		# print(f"ERRORE (Front-End non raggiungibile. Status code: {getStatusCode(url)})")
		print("ERRORE (Front-End non raggiungibile)")

		return False

	print("Ok")

	with StartTest(url, visible) as driver:
		driver.get(url)

		WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#origin[name='departureStation']")))


		# -------------------------------------------------------------------------------------
		# 								Pagina di ricerca
		# -------------------------------------------------------------------------------------
		print("PAGINA - Ricerca soluzione:")
		print("\tImposto stazione di partenza e arrivo: \t", end="", flush=True)
		driver.find_element(By.CSS_SELECTOR, "#origin[name='departureStation']").send_keys(TRAVEL_DETAILS["departure"] + Keys.TAB)
		driver.find_element(By.CSS_SELECTOR, "#destination[name='arrivalStation']").send_keys(TRAVEL_DETAILS["arrival"] + Keys.TAB)
		print("OK")
		


		print("\tImposto data e ora di partenza: \t", end="", flush=True)
		driver.find_element(By.CSS_SELECTOR, "#calenderId1Dropdown > input#calenderId1Text").send_keys(TRAVEL_DETAILS['travel_date'] + Keys.TAB)
		driver.find_element(By.CSS_SELECTOR, "#departureTimeDiv #departureTimeText").send_keys(TRAVEL_DETAILS['travel_time'] + Keys.TAB)
		print("OK")


		sleep(1.5)


		print("\n\tClicco su pulsante 'Cerca': \t\t", end="", flush=True)
		search_start = time()
		driver.find_element(By.ID, "searchButton").click()

		# Controlla se si presenta il dialog per la stazione sbagliata, altrimenti procede
		try:
			WebDriverWait(driver, 3).until(EC.alert_is_present(), 'Timed out waiting for alert')

			alert = driver.switch_to.alert

			print(f"ERRORE (comparso Alert: {alert.text})")
			
			alert.accept()

			DebugManager.dump("PICO_alertAfterSearch", driver, with_screenshot=True)
			return False
		except TimeoutException:
			# No errors
			pass






		# -------------------------------------------------------------------------------------
		# 								Pagina dell'elenco soluzioni
		# -------------------------------------------------------------------------------------
		try:
			WebDriverWait(driver, 120).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#searchRequestForm #refreshButton")))
		except (TimeoutException) as ex:
			if driver.find_elements(By.ID, "errorExc"):
				errore = driver.find_element(By.ID, "errorExc").get_attribute('innerText').strip().replace('\n', ' ').replace('\r', '')

				print(f"ERRORE ({errore})")

				DebugManager.dump("PICO_Timeout-Error_Search_", driver, with_screenshot=True)
				return False

		search_end = time()
		print(f"OK (durata ricerca: {timedelta(seconds=int(search_end - search_start))})")


		print()
		print("PAGINA - Lista soluzioni trovate:")
		print("\tControllo soluzioni > 0: \t\t", end="", flush=True)

		if not driver.find_elements(By.ID, "accordion"):
			print("ERRORE (Nessuna soluzione trovata)")

			return False


		solution_container = driver.find_element(By.CSS_SELECTOR, "form#searchRequestForm > .panel-group#accordion > div.panel")
		solutions = solution_container.find_elements(By.CSS_SELECTOR, "div[id^='travelSolution']")
		
		print (f"OK (trovate {len(solutions)} soluzioni)")


		MAX_ATTEMPTS_SOLUTION_SELECT = 5
		for tentativo in range (0, MAX_ATTEMPTS_SOLUTION_SELECT):
			print(f"\n\tTentativo n. {tentativo+1}: \t\t\t", end="", flush=True)
						
			solution_container = driver.find_element(By.CSS_SELECTOR, "form#searchRequestForm > .panel-group#accordion > div.panel")
			solutions = solution_container.find_elements(By.CSS_SELECTOR, "div[id^='travelSolution']")

			if tentativo >= int(len(solutions)):
				print("ERRORE - Impossibile eseguire altri tentativi. Soluzioni non sufficenti")
				return False

			mid_travelSolution = solution_container.find_element(By.ID, f"travelSolution{tentativo}")
			print(f"OK (provo soluzione n. {tentativo})")

			print("\tControllo biglietto acquistabile: \t", end="", flush=True)
			ora_partenza, ora_arrivo = "N/D", "N/D"
			try:
				ora_partenza = mid_travelSolution.find_element(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(1) > div.split > span.bottom.text-center").get_attribute("innerText").strip()
				ora_arrivo = mid_travelSolution.find_element(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(3) > div.split > span.bottom.text-center").get_attribute("innerText").strip()
				
				SOLUTION = {
					"ORARIO_PARTENZA": mid_travelSolution.find_element(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(1) > div.split > span.bottom.text-center").get_attribute("innerText").strip(),
					"ORARIO_ARRIVO": mid_travelSolution.find_element(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(3) > div.split > span.bottom.text-center").get_attribute("innerText").strip(),
					"DURATA": mid_travelSolution.find_element(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(4) > div.descr.duration.text-center").get_attribute("innerText").strip(),
					"NUMERO_CAMBI": re.search("Cambi: ([0-9]+)", mid_travelSolution.find_element(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(4) div.change").get_attribute("innerText").strip()).group(1) if mid_travelSolution.find_elements(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(4) div.change") else 0,
					"ELENCO_TRENI": " -> ".join([ elem.find_element(By.CSS_SELECTOR, ".train > .descr").get_attribute("innerText").strip() for elem in mid_travelSolution.find_elements(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(5) > .trainOffer") ]),
					"PREZZO_DA": mid_travelSolution.find_element(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(6) > span > div > span.price").get_attribute("innerText").strip(),
				}
			except WebDriverException as ex:
				print(f"ERRORE - Biglietto NON acquistabile (treno {ora_partenza} - {ora_arrivo})")
				continue
				# logging.exception("Impossibile reperire dettagli del viaggio")
			else:
				print(f"OK (soluzione valida)\n")

				print ("\tDettagli soluzione selezionata:")
				print (f"\t\t- Orario di partenza: {SOLUTION['ORARIO_PARTENZA']}")
				print (f"\t\t- Orario di arrivo: {SOLUTION['ORARIO_ARRIVO']}")
				print (f"\t\t- Durata del viaggio: {SOLUTION['DURATA']}")
				print (f"\t\t- Numero di cambi: {SOLUTION['NUMERO_CAMBI']}")
				print (f"\t\t- Elenco scambi: {SOLUTION['ELENCO_TRENI']}")
				print (f"\t\t- Prezzo a partire da: {SOLUTION['PREZZO_DA']}\n")

			print("\tEspando soluzione: \t\t\t", end="", flush=True)
			try: 
				mid_travelSolution.find_element(By.CSS_SELECTOR, "table.table-solution-hover > tbody > tr > td:nth-child(6)").click()
				WebDriverWait(driver, 120).until(EC.visibility_of_element_located((By.CSS_SELECTOR, f"div#priceGrid{tentativo} div.row > div > input.btn.btn-primary.btn-lg.btn-block[type='button']")))
			except (WebDriverException, TimeoutException) as ex:
				print(f"\tClicco su 'Procedi': \t\t\t", end="", flush=True)
				print(f"ERRORE - Impossibile espandere la soluzione '{tentativo}'")
				continue
			else:
				print(f"OK")

			# Utilizzo Javascript per cliccare perchè l'elemento non è interagibile utilizzando Selenium
			mid_priceGrid = solution_container.find_element(By.ID, f"priceGrid{tentativo}")
			pulsante_continua = mid_priceGrid.find_element(By.CSS_SELECTOR, "div.row > div > input.btn.btn-primary.btn-lg.btn-block[type='button']")
			driver.execute_script("arguments[0].click();", pulsante_continua)
			
			print("\tAspetto il caricamento della pagina: \t", end="", flush=True)
			try:
				WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, "firstPanel")))
			except TimeoutException:
				if driver.find_elements(By.ID, "errorExc"):
					errore_text = driver.find_element(By.ID, "errorExc").get_attribute('innerText').strip().replace('\n', ' ').replace('\r', '')

					print(f"ERRORE ({errore_text})")
					DebugManager.dump("PICO-TimeoutPrenotazione", driver, with_screenshot=True)
					if driver.find_elements(By.ID, f"priceGrid{tentativo}"):
						continue
					return False

				elif driver.find_elements(By.ID, "msgErrorCredentials") and driver.find_element(By.ID, "msgErrorCredentials").is_displayed():
					error_text = driver.find_element(By.ID, "msgErrorCredentials").get_attribute('innerText').strip().replace('\n', ' ').replace('\r', '')
					
					if error_text.startswith("!DOCTYPE html>"):
						print(f"ERRORE - Uno dei treni nella tratta NON ESISTE o risulta NON VALIDO")
					else:
						DebugManager.dump("PICO-TimeoutPrenotazioneErrore", driver, with_screenshot=True)
						print(f"ERRORE - Comparso codice di errore. Vedere screenshot salvato")

					return False
				
				elif driver.find_elements(By.ID, "upSellingPopupContent") and driver.find_element(By.ID, "upSellingPopupContent").is_displayed():
					print("OK (Comparsa proposta di cambio a Premium)")
					
					target_button = driver.find_element(By.ID, "upSellingB1")
					print(f"\tClicco su '{target_button.get_attribute('value').strip()}': \t", end="", flush=True)
					target_button.click()

					try:
						WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, "firstPanel")))
						break

					except TimeoutException:
						print("ERRORE - Fallito nuovamente... ")
						DebugManager.dump("PICO-TimeoutPrenotazioneSecondo", driver, with_screenshot=True)
						return False

				elif driver.find_elements(By.ID, "dayAfterModal") and driver.find_element(By.ID, "dayAfterModal").is_displayed():
					print("OK (Comparso avviso di viaggio per il giorno successivo)")
					
					target_button = driver.find_element(By.CSS_SELECTOR, "#dayAfterModal .modal-content > .modal-footer > button.btn-primary")
					print(f"\tClicco su '{target_button.get_attribute('value').strip()}': \t", end="", flush=True)
					target_button.click()

					try:
						WebDriverWait(driver, 60).until(EC.invisibility_of_element((By.ID, "dayAfterModal")))
						break

					except TimeoutException:
						print("ERRORE - Fallito nuovamente... ")
						logging.exception("Fallito durante la conferma del viaggio al giorno dopo")
						# DebugManager.dump("PICO-TimeoutPrenotazioneSecondo", driver, with_screenshot=True)
						return False

				else:
					print("ERRORE - La pagina di prenotazione non ha caricato entro 60 secondi.")
					DebugManager.dump("PICO-TimeoutPrenotazione", driver, with_screenshot=True)
				
					return False
			else:
				print ("OK\n")
				break
		else:
			print("")
			print(f"ERRORE - Raggiunto numero massimo di tentativi falliti ({MAX_ATTEMPTS_SOLUTION_SELECT})")
			return False




		# -------------------------------------------------------------------------------------
		# 								Pagina di prenotazione
		# -------------------------------------------------------------------------------------
		print("PAGINA - Inserimento dati prenotazione:", flush=True)

		pannello_autenticazione = driver.find_element(By.ID, "firstPanel")
		pannello_passeggeri = driver.find_element(By.ID, "startTravelDetails")

		print("\tClicco su 'Procedi senza registrazione': \t", end="", flush=True)
		pannello_autenticazione.find_element(By.ID, "nonSonoRegistrato").click()
		WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.ID, "emailId")))
		print ("OK")



		print("\tInserimento dati Utente: \t\t", end="", flush=True)
		notRegisteredSection = pannello_autenticazione.find_element(By.ID, "notRegisteredSection")
		notRegisteredSection.find_element(By.ID, "nameId").send_keys(USER["firstName"] + Keys.TAB)
		notRegisteredSection.find_element(By.ID, "snameId").send_keys(USER["lastName"] + Keys.TAB)
		notRegisteredSection.find_element(By.ID, "emailId").send_keys(USER["email"] + Keys.TAB)
		notRegisteredSection.find_element(By.ID, "email2Id").send_keys(USER["email"] + Keys.TAB)
		notRegisteredSection.find_element(By.ID, "phId").send_keys(USER["tel_number"] + Keys.TAB)
		print ("OK")



		print("\tInserimento dati Passeggero: \t\t", end="", flush=True)
		pannello_passeggeri.find_element(By.CSS_SELECTOR, "#collapsePassenger div.row fieldset input[id^='firstName']").send_keys(USER["firstName"] + Keys.TAB)
		pannello_passeggeri.find_element(By.CSS_SELECTOR, "#collapsePassenger div.row fieldset input[id^='lastName']").send_keys(USER["lastName"] + Keys.TAB)
		sleep(0.5)
		pannello_passeggeri.find_element(By.CSS_SELECTOR, "#collapsePassenger div.row fieldset input[id^='dob']").click()
		sleep(0.5)
		pannello_passeggeri.find_element(By.CSS_SELECTOR, "#collapsePassenger div.row fieldset input[id^='dob']").send_keys(USER["birth_date"] + Keys.TAB)
		sleep(0.5)
		pannello_passeggeri.find_element(By.CSS_SELECTOR, "#collapsePassenger div.row fieldset input[id^='primaryEmail']").send_keys(USER["email"] + Keys.TAB)
		pannello_passeggeri.find_element(By.CSS_SELECTOR, "#collapsePassenger div.row fieldset input[id^='contactNo']").send_keys(USER["tel_number"] + Keys.TAB)
		print ("OK")


		# Accetto le condizioni di trasporto
		print("\n\tAccetto Termini e Condizioni: \t\t", end="", flush=True)
		driver.find_element(By.ID, "termsCondition").click()
		print ("OK")

		# Fino a 5 tentativi
		print("\n\tClicco su 'Continua': \n", end="", flush=True)
		url_before = driver.current_url
		
		for i in range(5):
			print(f"\t\t- Tentativo {i+1}: \t\t\t", end="", flush=True)

			try: 
				# Clicca su 'Continua'
				driver.find_element(By.ID, "submitMyTrip").click()

				try:
					# Clicco su 'Acquista solo l'andata'
					WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.ID, "modalReturnTrip")))
					driver.find_element(By.ID, "modalReturnTripButton1").click()
				except TimeoutException:
					pass
			


				# Aspetto fino all'entrata nella pagina di NETS
				WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.data[id='data']")))
				print("OK")

				sleep(0.5)
				break

			except (TimeoutException) as ex:
				if driver.find_elements(By.ID, "errorExc"):
					errore_transazione_text = driver.find_element(By.ID, "errorExc").get_attribute('innerText').strip().replace('\n', ' ').replace('\r', '')

					print(f"ERRORE ({errore_transazione_text})")
					continue
			
			except NoSuchElementException:
				DebugManager.dump("PICO-ErroreDopoPrenotazione", driver, with_screenshot=True)
				if driver.find_elements(By.ID, "errorExc"):
					errore_transazione_text = driver.find_element(By.ID, "errorExc").get_attribute('innerText').strip().replace('\n', ' ').replace('\r', '')

					print(f"ERRORE ({errore_transazione_text})")

				url_now = driver.current_url 
				if "search.do" in url_now:
					print("\nATTENZIONE - Il browser e' stato reindirizzato alla pagina di ricerca! Interrompo il test")

				elif url_before != url_now: 
					print(f"\nANOMALIA - L'URL e' cambiato dopo aver cliccato 'Continua': \n\tPrima: {url_before}\n\tDopo: {url_now}")
					print("Mi aspettavo rimanesse lo stesso, ma non sono piu' riuscito a trovare il pulsante 'Continua'")
				
				return False

		if not driver.find_elements(By.CSS_SELECTOR, "div.data[id='data']"):
			print("\nERRORE FATALE - Esauriti tutti i 5 tentativi disponibili. Termine test in errore")

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
		driver.find_element(By.CSS_SELECTOR, "input[name='ACCNTFIRSTNAME']").send_keys(str(CARD["firstName"]) + Keys.TAB)
		driver.find_element(By.CSS_SELECTOR, "input[name='ACCNTLASTNAME']").send_keys(str(CARD["lastName"]) + Keys.TAB)
		driver.find_element(By.CSS_SELECTOR, "input[name='PAN']").send_keys(str(CARD["number"]) + Keys.TAB)

		select_mese = Select(driver.find_element(By.ID, "EXPDT_MM"))
		select_mese.select_by_visible_text((datetime.now()).strftime('%m'))
		
		select_anno = Select(driver.find_element(By.ID, "EXPDT_YY"))
		select_anno.select_by_visible_text((datetime.now() + relativedelta(years=1)).strftime('%Y'))

		driver.find_element(By.CSS_SELECTOR, "input[name='CVV']").send_keys(str(CARD["csc"]) + Keys.TAB)
		print("OK")

		# Clicco su 'Continua'
		print("\tClicco su 'Continua': \t\t\t", end="", flush=True)
		driver.find_element(By.ID, "continue").click()
		print("OK")

		# Aspetto fino alla pagina di conferma dei dati della Carta
		WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "modify")))

		# Clicco su 'Conferma'
		print("\tClicco su 'Conferma': \t\t\t", end="", flush=True)
		driver.find_element(By.ID, "confirm").click()
		print("OK")





		# -------------------------------------------------------------------------------------
		# 							Pagina di conferma prenotazione
		# -------------------------------------------------------------------------------------
		print("\nPAGINA - Pagina 'SECURE CHECKOUT':", flush=True)
		try:
			# Aspetto fino alla pagina di conferma dei dati della Carta
			print("\tCaricamento pagina: \t\t\t", end="", flush=True)
			WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.ID, "challengeDataEntry")))
			print("OK - Trovata richiesta di inserimento OTP")
		except TimeoutException:
			# Se la pagina non si carica
			print("WARNING - Nessuna richiesta di OTP trovata")
		else:
			OTP = "111111"
			print("\tInserimento OTP: \t\t\t", end="", flush=True)
			driver.find_element(By.ID, "challengeDataEntry").send_keys(OTP + Keys.TAB)
			sleep(0.5)
			print(f"OK - Inserito OTP '{OTP}'")

			print("\tClicco su 'Submit': \t\t\t", end="", flush=True)
			driver.find_element(By.ID, "confirm").click()
			print(f"OK")




		# -------------------------------------------------------------------------------------
		# 							Pagina di conferma prenotazione
		# -------------------------------------------------------------------------------------
		print("\nPAGINA - Pagina di conferma prenotazione:", flush=True)
		try:
			# Aspetto fino alla pagina di conferma dei dati della Carta
			print("\tCaricamento pagina: \t\t\t", end="", flush=True)
			WebDriverWait(driver, 60).until(EC.url_contains(url="B2CWeb/createTicket.do"))
			print("OK")

		except TimeoutException:
			# Se la pagina non si carica
			print("ERRORE")

			return False


		print("\tControllo popup: \t\t\t", end="", flush=True)
		
		try:
			popup = WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "popupInfo")))
			popup_text = popup.find_element(By.CSS_SELECTOR, ".modal-dialog > .modal-content > .modal-body > .inner-body").get_attribute("innerText").strip()

			if popup_text in ["Operazione conclusa con successo!"]:
				print(f"OK - Messaggio di conferma RICEVUTO ({popup_text})")

				return True
			else: 
				print(f"ERRORE - Messaggio di conferma NON trovato ({popup_text})")
				
				DebugManager.dump("PICO-ConfermaPrenotazione", driver, with_screenshot=True)
				return False
		except TimeoutException:
			# Se la pagina non si carica
			print("ERRORE - Errore nel caricamento della pagina.")

			# try:
			# 	logger.info(f"Inizio cambio password per l'Hostname: '{host}'")
			# 	ISIM.change_password(driver, host)
			# except Exception:
			# 	logger.exception("Eccezione non gestita durante il cambio password. Segnalare allo sviluppatore")
			# 	screenshot_filename = Path(tempfile.gettempdir(), f"ISIMRootPasswordChange_GenericException_{datetime.datetime.today().strftime('%d-%m-%Y_%H.%M.%S')}.png")
				
			# 	if driver.save_screenshot(str(screenshot_filename.absolute().resolve())):
			# 		logger.error(f"Salvato screenshot: '{screenshot_filename.absolute()}'. Utilizzarlo per identificare il problema...")
			# 		webbrowser.open(screenshot_filename.absolute().as_uri())


			
			DebugManager.dump("PICO-ErrorePrenotazione", driver, with_screenshot=True)
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

	APP_ID = "Test_Mattutini"
	APP_VERSION = "0.7.2"
	APP_DATA = {}

	PROJECT_NAME = "Pico"

	try:
		window_size = get_terminal_size()

		CONSOLE_WIDTH = window_size.columns
		CONSOLE_HEIGTH = window_size.lines
	except:
		CONSOLE_WIDTH = 130



	APP_CONFIG = {
		"CARD": {

		},
		"USER": {
			"firstName": "",
			"lastName": "",
			"email": "",
			"email": "",
			"tel_number": "",
		},
		"TRAVEL": {
			"departure": "Frascati",
			"arrival": "Milano Centrale",
			"travel_date": (datetime.now() + relativedelta(days=5)).strftime('%d-%m-%Y'),
			"travel_time": "12"
		}
	}

	FILE_PATH = os.path.dirname(os.path.realpath(__file__))
	DEBUG = True


	DEFAULT_AMBIENTI = [ 
		"Certificazione",
		"Correttiva",
		"Integrazione",
		"Training"
	]
	
	DEFAULT_STAZIONI = {
		"partenza": "Frascati",
		"arrivo": "Milano Centrale",
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
			"code": f"{SCRIPT_INVOCATION} Training Correttiva",
			"desc": "Effettua i test solo per i nodi di Training e Correttiva."
		},
		{
			"code": f"{SCRIPT_INVOCATION}",
			"desc": "Effettua i test per Correttiva, Certificazione, Integrazione e Training."
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

	EXAMPLE_CONF_FILE = ""
	# with open(utility.getCorrectPath(os.path.join("conf","mock_card.yml")), 'r') as stream:
	# 	line = stream.readline()
	# 	EXAMPLE_CONF_FILE += line

	# 	while line:
	# 		line += stream.readline()

		
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

	stazioni.add_argument("-A", "--stazione-arrivo", help=f"Indica la stazione di arrivo (default=%(default)s)", dest="stazione_arrivo", default=DEFAULT_STAZIONI["arrivo"], metavar="stazione")
							   
	stazioni.add_argument("-P", "--stazione-partenza", help=f"Indica la stazione di partenza (default=%(default)s)", dest="stazione_partenza", default=DEFAULT_STAZIONI["partenza"], metavar="stazione")
	
	# default=(datetime.now() + relativedelta(days=5)).strftime('%d-%m-%Y')
	target_date = datetime.now() + relativedelta(hours=1)
	stazioni.add_argument("-G", "--giorno-partenza", help=f"Indica la data di partenza (default: %(default)s)", dest="data_partenza", default=target_date.strftime('%d-%m-%Y'), metavar="data")
	
	stazioni.add_argument("-O", "--ora-partenza", help=f"Indica l'ora di partenza (default: %(default)s)", dest="ora_partenza", default=target_date.strftime('%H'), metavar="ora")

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
	print("Percorso Cache: " + cache.getCacheFilename())

	if not APP_DATA or CLI_ARGS.force_update or not APP_DATA["data"]:
		print("Avvio aggiornamento del file di configurazione infrastrutturale...")

		if PortalePicoGTS.isReachable():
			try:
				cache.setCache(Trenitalia.getInfrastructure())
				APP_DATA = cache.getCache()

				if not "data" in APP_DATA or not APP_DATA["data"]:
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
	with open(utility.getCorrectPath(os.path.join("conf","mock_card.yml")), 'r') as stream:
		CARD = yaml.safe_load(stream)


	# Utente
	with open(utility.getCorrectPath(os.path.join("conf","mock_user.yml")), 'r') as stream:
		USER = yaml.safe_load(stream)




	TRAVEL_DETAILS = {
		"departure": CLI_ARGS.stazione_partenza,
		"arrival": CLI_ARGS.stazione_arrivo,
		"travel_date": CLI_ARGS.data_partenza,
		"travel_time": CLI_ARGS.ora_partenza
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

	valid_keys = [ "B2C", "B2C_SC" ]
	VALID_ENVIRONMENTS  = [ 
		key for key in nodes[PROJECT_NAME].keys() 
			if 
				(
					"B2C" in nodes[PROJECT_NAME][key] 
					and "APPLICATION_SERVER" in nodes[PROJECT_NAME][key]["B2C"]
				) or
				(
					"B2C_SC" in nodes[PROJECT_NAME][key] 
					and "APPLICATION_SERVER" in nodes[PROJECT_NAME][key]["B2C_SC"]
				)
	]
	
	if CLI_ARGS.show_available_environments: 
		print("Ambienti disponibili per il test:")
		for ambiente in VALID_ENVIRONMENTS: 
			if ambiente.startswith("Corr-Blue"): print("\t- Correttiva (nodo attivo)")
			elif ambiente.startswith("Cert-Blue"): print("\t- Certificazione (nodo attivo)")
			elif ambiente.startswith("Int-Blue"): print("\t- Integrazione (nodo attivo)")
			print(f"\t- {ambiente}")
		
		print("")
		
		sys.exit(0)



	if not CLI_ARGS.ambienti:
		print(repeat_string('-', CONSOLE_WIDTH))
		print("ATTENZIONE".center(CONSOLE_WIDTH))
		print("Nessun ambiente specificato. Aggiungine uno per iniziare i test.".center(CONSOLE_WIDTH))
		print("Per un controllo degli ambienti disponibili vai su http://ngppgtsfe.pico.gts/was/ng-nodes".center(CONSOLE_WIDTH))
		print(repeat_string('-', CONSOLE_WIDTH))
		
		sys.exit(1)







	"""
	███████╗████████╗ █████╗ ██████╗ ████████╗    ████████╗███████╗███████╗████████╗
	██╔════╝╚══██╔══╝██╔══██╗██╔══██╗╚══██╔══╝    ╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝
	███████╗   ██║   ███████║██████╔╝   ██║          ██║   █████╗  ███████╗   ██║   
	╚════██║   ██║   ██╔══██║██╔══██╗   ██║          ██║   ██╔══╝  ╚════██║   ██║   
	███████║   ██║   ██║  ██║██║  ██║   ██║          ██║   ███████╗███████║   ██║   
	╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝          ╚═╝   ╚══════╝╚══════╝   ╚═╝   
	"""
	if not PROJECT_NAME in nodes:
		print(f"Nessuna configurazione presente corrispondente alla voce '{PROJECT_NAME}'")
		sys.exit(2)

	try:
		all_test_start = time()
		risultati_test = {}

		for ambiente in CLI_ARGS.ambienti:
			print(repeat_string('-', CONSOLE_WIDTH))
			print (f"Test di acquisto per {ambiente}")


			# Se si sta puntando il nodo generico, viene puntato quello attivo
			if ambiente == "Correttiva":
				active_cell = get_active_cell(project=PROJECT_NAME, environment=ambiente)
				print (f"INFO - Stai puntando al nodo della Cella Attiva di '{ambiente}' ({active_cell.upper()})\n")
				
				ambiente = "Corr-Green" if active_cell == "green" else "Corr-Blue"

			elif ambiente == "Certificazione":
				active_cell = get_active_cell(project=PROJECT_NAME, environment=ambiente)
				print (f"INFO - Stai puntando al nodo della Cella Attiva di '{ambiente}' ({active_cell.upper()})\n")
				
				ambiente = "Cert-Green" if active_cell == "green" else "Cert-Blue"

			elif ambiente == "Integrazione":
				# active_cell = get_active_cell(project=PROJECT_NAME, environment=ambiente)
				active_cell = "blue"		# Al momento SOLO la blue è attiva
				print (f"INFO - Stai puntando al nodo della Cella Attiva di '{ambiente}' ({active_cell.upper()})\n")
				
				ambiente = "Int-Green" if active_cell == "green" else "Int-Blue"



			if not ambiente in nodes[PROJECT_NAME]:
				print ("")
				print (f"ATTENZIONE - L'ambiente '{ambiente}' non esiste o il file di configurazione potrebbe non essere aggiornato.\n\n")
				continue

			if "B2C" in nodes[PROJECT_NAME][ambiente]:
				ENDPOINT = [ 
					jvm["urls"]["https"] for jvm in nodes[PROJECT_NAME][ambiente]["B2C"]["APPLICATION_SERVER"] 
				]
			else:
				ENDPOINT = [ 
					jvm["urls"]["https"] for jvm in nodes[PROJECT_NAME][ambiente]["B2C_SC"]["APPLICATION_SERVER"] 
				]

			if not ambiente in risultati_test:
				risultati_test[ambiente] = {
					"totale_nodi": len(ENDPOINT),
					"risultati": []
				}
			
			for index, url in enumerate(ENDPOINT):
				print(f"{ambiente} B2C [nodo {index+1} di {len(ENDPOINT)}] - {url}")
				
				test_success = singleNodeTest(url, CLI_ARGS.show_browser, skip_payment=CLI_ARGS.skip_payment)
				

				risultati_test[ambiente]["risultati"].append({
					"nodo": index+1,
					"url": url,
					"result": test_success
				})

				if test_success:
					print(f"************** TEST OK [{ambiente} {index+1}/{len(ENDPOINT)}] **************")
				else:
					print(f"!?!?!?!?!?!? TEST KO [{ambiente} {index+1}/{len(ENDPOINT)}] ?!?!?!?!?!?!")

			print("\n")

	except BrowserNotInstalledException as e:
		print(f"ERRORE CRITICO - Il browser '{e.browser}' non è installato sul sistema. Procedura annullata")

		exit(2)


	program_end = time()




	""" 
	██████╗ ██╗███████╗██████╗ ██╗██╗      ██████╗  ██████╗  ██████╗ 
	██╔══██╗██║██╔════╝██╔══██╗██║██║     ██╔═══██╗██╔════╝ ██╔═══██╗
	██████╔╝██║█████╗  ██████╔╝██║██║     ██║   ██║██║  ███╗██║   ██║
	██╔══██╗██║██╔══╝  ██╔═══╝ ██║██║     ██║   ██║██║   ██║██║   ██║
	██║  ██║██║███████╗██║     ██║███████╗╚██████╔╝╚██████╔╝╚██████╔╝
	╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝╚══════╝ ╚═════╝  ╚═════╝  ╚═════╝ 
    """                                                           
	print("\n\n")
	print(repeat_string('-', CONSOLE_WIDTH))
	print("Riepilogo Generale".center(CONSOLE_WIDTH))
	print(repeat_string('-', CONSOLE_WIDTH))
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
		print(f"{ambiente.title()}:")

		for test in risultati_test[ambiente]["risultati"]:
			ip_add = re.search(r"https?://[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.([0-9]{1,3})", test['url']).group(1)

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


	print(repeat_string('-', CONSOLE_WIDTH))
	print("")
	
	input("\nPremi INVIO per continuare\n")