from textwrap import indent
from portalePICO.main import PortalePicoGTS
import signal
import os
import sys
from sys import exc_info
import yaml

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import IEDriverManager
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException


from time import sleep, time
from pyautogui import press

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re
import textwrap

import logging

import traceback
from contextlib import contextmanager

# For testing purposes only
import random
import json



import requests
from urllib3.exceptions import InsecureRequestWarning
import argparse

from portalePICO.utils import Trenitalia
import utility

from MyCache.utils import Cache

from exceptions import BrowserNotInstalledException


"""
	DESCRIZIONE:
		Script per i Test mattutini di PICO
	
	AGGIORNAMENTI:
		- 30/10/20: Aggiunto controllo validità stazione 
		- 31/10/20: Aggiunto Context Manager per gestire le eccezioni, aggiunta eccezione di rete, modificato formatting e migliorato logging
		- 01/11/20: Aggiunta misurazione performance, aggiunta eccezione di rete, aggiunto percorso anche quando si usa la versione eseguibile
		- 01/11/20: Aggiunti parametri da CLI, aggiunto controllo raggiungibilità macchina tramite richiesta HTTP (molto più veloce)
		- 17/11/20: Rimosse alcune funzioni di sviluppo, aggiunto controllo se esce la richiesta di acquisto Andata e Ritorno, aggiunto Help per file di configurazione

	APPUNTI DI SVILUPPO:
		- Per la compilazione: pyinstaller --clean --name "Test_acquisto-PICO" --log-level=WARN --onefile --noconfirm --add-data="./conf/;./conf/" .\pico_tests.py
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



@contextmanager
def StartTest():
	"""
	Wrapper around the tests.
	This ensures the test is ALWAYS ended gracefully, doing some clean-up before exiting (https://book.pythontips.com/en/latest/context_managers.html#implementing-a-context-manager-as-a-generator)

	Yields:
		selenium.webdriver.Chrome: The selenium webdriver instance used for the test
	"""
	test_start = time()

	chrome_flags = [
		"--disable-extensions",
		"start-maximized",
		"--disable-gpu",
		"--ignore-certificate-errors",
		"--ignore-ssl-errors",
		#"--no-sandbox # linux only,
		"--log-level=3",	# Start from CRITICAL
		"--headless",
	]
	chrome_options = Options()

	for flag in chrome_flags: chrome_options.add_argument(flag)

	# To remove '[WDM]' logs (https://github.com/SergeyPirogov/webdriver_manager#configuration)
	os.environ['WDM_LOG_LEVEL'] = '0'
	os.environ['WDM_PRINT_FIRST_LINE'] = 'False'

	# To remove "DevTools listening on ws:..." message (https://stackoverflow.com/a/56118790/8965861)
	chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
	
	__driver = webdriver.Chrome( ChromeDriverManager(log_level=0).install(), options=chrome_options )
	__driver.set_window_size(1920, 1080)

	try:
		yield __driver

	except WebDriverException as ex:
		print("------------------- WebDriverException -------------------")


		if "net::ERR_CONNECTION_TIMED_OUT" in ex.msg:
			print("FATAL ERROR - La connessione con il server è andata in Timeout. \nCodice di errore net::ERR_CONNECTION_TIMED_OUT\n")
		
		elif "net::ERR_CONNECTION_REFUSED" in ex.msg:
			print("FATAL ERROR - Impossibile contattare il server. \nCodice di errore net::ERR_CONNECTION_REFUSED\n")

		elif re.match(pattern="unknown error: cannot find .* binary", string=ex.msg):
			browser = re.match(pattern="unknown error: cannot find (.*?) binary", string=ex.msg).group(1)
			# print(f"Il browser '{browser}' non risulta installato sulla macchina")

			raise BrowserNotInstalledException(browser)

		else:
			print(f"OTHER ERROR - Message: {ex.msg}")
			# print(f"sys.exc_info(): {sys.exc_info()}")
			print("Stacktrace:")
			traceback.print_stack()
			print("\n")
	
		# input("Premi INVIO per continuare")

	except Exception as exception:
		print("------------------- Exception -------------------")
		print(f"Message: {exception.msg}")
		print(f"sys.exc_info(): {sys.exc_info()}")
	
		# input("Premi INVIO per continuare")


	finally:
		print("\n\n+++++++++++++++++++ DESTROYING DRIVER... PLEASE WAIT... +++++++++++++++++++\n")
		__driver.quit()
		print("\n\n+++++++++++++++++++ DRIVER SUCCESSFULLY DESTROYED! +++++++++++++++++++")

		test_end = time()
		print(f"Durata test: {timedelta(seconds=int(test_end - test_start))}")

		print()




def singleNodeTest (url):
	"""
	Starts the browser
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

	with StartTest() as driver:
		driver.get(url)

		WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#origin[name='departureStation']")))

		# To take screenshot:
		# driver.save_screenshot("screenshot.png")

		print("PAGINA - Ricerca soluzione:")
		print("\tImposto stazione di partenza e arrivo: \t", end="", flush=True)
		driver.find_element_by_css_selector("#origin[name='departureStation']").send_keys(TRAVEL_DETAILS["departure"] + Keys.TAB)
		driver.find_element_by_css_selector("#destination[name='arrivalStation']").send_keys(TRAVEL_DETAILS["arrival"] + Keys.TAB)
		print("OK")
		


		print("\tImposto data e ora di partenza: \t", end="", flush=True)
		driver.find_element_by_css_selector("#calenderId1Dropdown > input#calenderId1Text").send_keys(TRAVEL_DETAILS['travel_date'] + Keys.TAB)
		driver.find_element_by_css_selector("#departureTimeDiv #departureTimeText").send_keys(TRAVEL_DETAILS['travel_time'] + Keys.TAB)
		print("OK")


		sleep(1.5)


		print("\n\tClicco su pulsante 'Cerca': \t\t", end="", flush=True)
		search_start = time()
		driver.find_element_by_id("searchButton").click()

		try:
			WebDriverWait(driver, 3).until(EC.alert_is_present(), 'Timed out waiting for alert')

			alert = driver.switch_to.alert

			print(f"ERRORE (comparso Alert: {alert.text})")
			
			alert.accept()

			return False
		except TimeoutException:
			# No errors
			pass

		WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#searchRequestForm #refreshButton")))

		search_end = time()
		print(f"OK (durata ricerca: {timedelta(seconds=int(search_end - search_start))})")


		print()
		print("PAGINA - Lista soluzioni trovate:")
		print("\tControllo soluzioni > 0: \t\t", end="", flush=True)

		if not driver.find_element_by_id("accordion"):
			print("FAILED")

			print("\nNessuna soluzione trovata per la tratta:")

			result_partenza = driver.find_element_by_css_selector("#collapseViaggio input[name='departureStation']").get_attribute("innerText").strip()
			result_arrivo = driver.find_element_by_css_selector("#collapseViaggio input[name='arrivalStation']").get_attribute("innerText").strip()
			result_data = driver.find_element_by_css_selector("#collapseViaggio input[id='calenderId1Text']").get_attribute("innerText").strip()
			result_orario = driver.find_element_by_css_selector("#collapseViaggio input[id='departureTimeText']").get_attribute("innerText").strip()

			print(f"\tStazione di partenza: {result_partenza}")
			print(f"\tStazione di arrivo: {result_arrivo}\n")

			print(f"\tData di partenza: {result_data}")
			print(f"\tOrario di partenza: {result_orario}\n")


			return False


		solution_container = driver.find_element_by_css_selector("form#searchRequestForm > .panel-group#accordion > div.panel")
		solutions = solution_container.find_elements_by_css_selector("div[id^='travelSolution']")


		print (f"OK (trovate {len(solutions)} soluzioni)")


		print(f"\tSeleziono soluzione intermedia: \t", end="", flush=True)
		# Se c'è un unica solution:
		# 	>>> int(1 / 2)              
		# 	0
		mid_solution_id = int(len(solutions) / 2)

		mid_travelSolution = solution_container.find_element_by_id(f"travelSolution{mid_solution_id}")
		mid_priceGrid = solution_container.find_element_by_id(f"priceGrid{mid_solution_id}")
		print(f"OK (soluzione n. {mid_solution_id})\n")

		SOLUTION = {
			"ORARIO_PARTENZA": mid_travelSolution.find_element_by_css_selector("table.table-solution-hover > tbody > tr > td:nth-child(1) > div.split > span.bottom.text-center").get_attribute("innerText").strip(),
			"ORARIO_ARRIVO": mid_travelSolution.find_element_by_css_selector("table.table-solution-hover > tbody > tr > td:nth-child(3) > div.split > span.bottom.text-center").get_attribute("innerText").strip(),
			"DURATA": mid_travelSolution.find_element_by_css_selector("table.table-solution-hover > tbody > tr > td:nth-child(4) > div.descr.duration.text-center").get_attribute("innerText").strip(),
			"NUMERO_CAMBI": re.search("Cambi: ([0-9]+)", mid_travelSolution.find_element_by_css_selector("table.table-solution-hover > tbody > tr > td:nth-child(4) div.change").get_attribute("innerText").strip()).group(1),
			"ELENCO_TRENI": " -> ".join([ elem.find_element_by_css_selector(".train > .descr").get_attribute("innerText").strip() for elem in mid_travelSolution.find_elements_by_css_selector("table.table-solution-hover > tbody > tr > td:nth-child(5) > .trainOffer") ]),
			"PREZZO_DA": mid_travelSolution.find_element_by_css_selector("table.table-solution-hover > tbody > tr > td:nth-child(6) > span > div > span.price").get_attribute("innerText").strip(),
		}

		print ("\tDettagli soluzione selezionata:")
		print (f"\t\t- Orario di partenza: {SOLUTION['ORARIO_PARTENZA']}")
		print (f"\t\t- Orario di arrivo: {SOLUTION['ORARIO_ARRIVO']}")
		print (f"\t\t- Durata del viaggio: {SOLUTION['DURATA']}")
		print (f"\t\t- Numero di cambi: {SOLUTION['NUMERO_CAMBI']}")
		print (f"\t\t- Elenco scambi: {SOLUTION['ELENCO_TRENI']}")
		print (f"\t\t- Prezzo a partire da: {SOLUTION['PREZZO_DA']}\n")


		print(f"\tClicco su 'Procedi': \t\t\t", end="", flush=True)
		# Utilizzo Javascript per cliccare perchè l'elemento non è interagibile utilizzando Selenium
		pulsante_continua = mid_priceGrid.find_element_by_css_selector("div.row > div > input.btn.btn-primary.btn-lg.btn-block[type='button']")
		driver.execute_script("arguments[0].click();", pulsante_continua)
		print ("OK\n")



		print("PAGINA - Inserimento dati prenotazione:", flush=True)
		print("\tCaricamento pagina: \t\t\t", end="", flush=True)

		print ("OK")

		pannello_autenticazione = driver.find_element_by_id("firstPanel")
		pannello_passeggeri = driver.find_element_by_id("startTravelDetails")

		print("\n\tClicco su 'Procedi senza registrazione': \t", end="", flush=True)
		pannello_autenticazione.find_element_by_id("nonSonoRegistrato").click()
		WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.ID, "emailId")))
		print ("OK")



		print("\tInserimento dati Utente: \t\t", end="", flush=True)
		notRegisteredSection = pannello_autenticazione.find_element_by_id("notRegisteredSection")
		notRegisteredSection.find_element_by_id("nameId").send_keys(USER["firstName"] + Keys.TAB)
		notRegisteredSection.find_element_by_id("snameId").send_keys(USER["lastName"] + Keys.TAB)
		notRegisteredSection.find_element_by_id("emailId").send_keys(USER["email"] + Keys.TAB)
		notRegisteredSection.find_element_by_id("email2Id").send_keys(USER["email"] + Keys.TAB)
		notRegisteredSection.find_element_by_id("phId").send_keys(USER["tel_number"] + Keys.TAB)
		print ("OK")



		print("\tInserimento dati Passeggero: \t\t", end="", flush=True)
		pannello_passeggeri.find_element_by_css_selector("#collapsePassenger div.row fieldset input[id^='firstName']").send_keys(USER["firstName"] + Keys.TAB)
		pannello_passeggeri.find_element_by_css_selector("#collapsePassenger div.row fieldset input[id^='lastName']").send_keys(USER["lastName"] + Keys.TAB)
		sleep(0.5)
		pannello_passeggeri.find_element_by_css_selector("#collapsePassenger div.row fieldset input[id^='dob']").click()
		sleep(0.5)
		pannello_passeggeri.find_element_by_css_selector("#collapsePassenger div.row fieldset input[id^='dob']").send_keys(USER["birth_date"] + Keys.TAB)
		sleep(0.5)
		pannello_passeggeri.find_element_by_css_selector("#collapsePassenger div.row fieldset input[id^='primaryEmail']").send_keys(USER["email"] + Keys.TAB)
		pannello_passeggeri.find_element_by_css_selector("#collapsePassenger div.row fieldset input[id^='contactNo']").send_keys(USER["tel_number"] + Keys.TAB)
		print ("OK")


		# Accetto le condizioni di trasporto
		print("\n\tAccetto Termini e Condizioni: \t\t", end="", flush=True)
		driver.find_element_by_id("termsCondition").click()
		print ("OK")

		# Fino a 5 tentativi
		print("\n\tClicco su 'Continua': \n", end="", flush=True)
		url_before = driver.current_url
		
		for i in range(5):
			print(f"\t\t- Tentativo {i+1}: \t\t\t", end="", flush=True)

			try: 
				# Clicca su 'Continua'
				driver.find_element_by_id("submitMyTrip").click()

				try:
					# Clicco su 'Acquista solo l'andata'
					WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.ID, "modalReturnTrip")))
					driver.find_element_by_id("modalReturnTripButton1").click()
				except TimeoutException:
					pass
			


				# Aspetto fino all'entrata nella pagina di NETS
				WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.data[id='data']")))
				print("OK")

				sleep(0.5)
				break

			except (TimeoutException) as ex:
				if driver.find_elements_by_id("errorExc"):
					errore_transazione_text = driver.find_element_by_id("errorExc").get_attribute('innerText').strip().replace('\n', ' ').replace('\r', '')

					print(f"ERRORE ({errore_transazione_text})")
					continue
			
			except NoSuchElementException:
				if driver.find_elements_by_id("errorExc"):
					errore_transazione_text = driver.find_element_by_id("errorExc").get_attribute('innerText').strip().replace('\n', ' ').replace('\r', '')

					print(f"ERRORE ({errore_transazione_text})")

				url_now = driver.current_url 
				if "search.do" in url_now:
					print("Il browser e' stato reindirizzato alla pagina di ricerca! Interrompo il test")

				elif url_before != url_now: 
					print(f"\nANOMALIA - L'URL e' cambiato dopo aver cliccato 'Continua': \n\tPrima: {url_before}\n\tDopo: {url_now}")
					print("Mi aspettavo rimanesse lo stesso, ma non sono piu' riuscito a trovare il pulsante 'Continua'")
				
				return False

		if not driver.find_elements_by_css_selector("div.data[id='data']"):
			print("\nERRORE FATALE - Esauriti tutti i 5 tentativi disponibili. Termine test in errore")

			return False


		print("\nPAGINA - Pagina di pagamento N&TS:", flush=True)
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


		print("\nPAGINA - Pagina di conferma prenotazione:", flush=True)
		try:
			# Aspetto fino alla pagina di conferma dei dati della Carta
			print("\tCaricamento pagina: \t\t\t", end="", flush=True)
			WebDriverWait(driver, 60).until(EC.url_contains(url="B2CWeb/createTicket.do"))
			print("OK")

			popup = driver.find_element_by_id("popupInfo")
			popup_text = popup.find_element_by_css_selector(".modal-dialog > .modal-content > .modal-body > .inner-body").get_attribute("innerText").strip()

			print("\tControllo popup: \t\t\t", end="", flush=True)

			if popup_text != "Operazione conclusa con successo!":
				print(f"ERRORE - Messaggio di conferma NON trovato ({popup_text})")

				return False
			else: 
				print(f"OK - Messaggio di conferma RICEVUTO ({popup_text})")
				
				return True

		except TimeoutException:
			# Se la pagina non si carica
			print("ERRORE")

			return False
	
	return False


if __name__ == "__main__":
	program_start = time()

	APP_ID = "Test_Mattutini"
	APP_VERSION = "1.4.0"
	APP_DATA = {}

	FILE_PATH = os.path.dirname(os.path.realpath(__file__))
	DEBUG = True



	# DEFAULT_CONFIGURATION = {
	# 	"card":{
	# 		"firstName": 	"PICO",
	# 		"lastName": 	"Trenitalia",
	# 		"number": 		4539999999999993,
	# 		"exp_date": 	"12/2022",
	# 		"csc": 			111
	# 	},
	# 	"passenger":{
	# 		"firstName": 	"Test",
	# 		"lastName": 	"User",
	# 		"email": 		"test.email@test.com",
	# 		"tel_number": 	"0123456789",
	# 		"birth_date": 	"11/09/2001"
	# 	},
	# 	"travel":{
	# 		"departure": 	"Frascati",
	# 		"arrival": 		"Milano Centrale"
	# 	}
	# }


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
		f"Script per il testing automatico degli ambienti NOPROD di PICO - Versione {APP_VERSION}\n"
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


	files = parser.add_argument_group('Opzioni di configurazione')

	files.add_argument("-c", "--config", help=f"Specifica il percorso del file di configurazione (vedi il paragrafo 'Struttura file di configurazione' per meggiori dettagli)", dest="path_custom_config", metavar="percorso_file")

	altre_opzioni = parser.add_argument_group('Altre opzioni')

	altre_opzioni.add_argument("-f", "--force-update", help="Forza l'aggiornamento del file di configurazione dell'infrastruttura",
						action="store_true", dest="force_update")
	
	altre_opzioni.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                   		help='Mostra questo messaggio ed esce')

	altre_opzioni.add_argument("-V", "--version", help="Mostra la versione del programma ed esce",
						action='version', version=f"%(prog)s {APP_VERSION}")


	CLI_ARGS = parser.parse_args()

	signal.signal(signal.SIGINT, signal_handler)


	if DEBUG: 
		print("----------------------------------------------------------------------------------------------------------------------------------\n	")
		print(f"TEST MATTUTINI PICO - VERSIONE DI SVILUPPO v.{APP_VERSION}".center(130))
		print("")
		print("In fase di test si prega di lanciare il programma con 'nomeprogramma.exe | Tee-Object -Append -FilePath \"terminal.log\"'".center(130))
		print("Questo file andra' poi condiviso se vengono trovati degli errori nel programma\n".center(130))
		print("----------------------------------------------------------------------------------------------------------------------------------\n	")


	
	"""
		--------------------------------------------------------------------------------------------
										CONFIGURATION LOADING
		--------------------------------------------------------------------------------------------
	"""
	# Infrastruttura
	cache = Cache("Test_Mattutini_Nodi_Infrastruttura.yaml", apiVersion=APP_VERSION)
	APP_DATA = cache.getCache()
	
	if not APP_DATA or CLI_ARGS.force_update:
		print("Avvio aggiornamento del file di configurazione infrastrutturale...")

		if PortalePicoGTS.isReachable():
			try:
				cache.setCache(Trenitalia.getInfrastructure())
				APP_DATA = cache.getCache()

				if not "data" in APP_DATA:
					print("Nessun dato ricavato dall'analisi del portale")
					exit(1)
			
			except BrowserNotInstalledException as e:
				print(f"ERRORE CRITICO - Il browser '{e.browser}' non è installato sul sistema. Procedura annullata")

				exit(2)

			except Exception as e:
				print(f"CRITICAL ERROR - Fallito update infrastruttura con errore: {e}")

			nodes = APP_DATA["data"]
		else:
			print(f"Impossibile collegarsi al Portale PICO GTS ({PortalePicoGTS.getUrl()}) per l'aggiornamento del file di configurazione.")

			if CLI_ARGS.force_update:
				print("Impossibile forzare l'aggiornamento. \n")

			elif not cache.exists():
				print("FATAL ERROR - Per la prima configurazione e' mandatoria la disponibilita del portale per prendere i nodi infrastrutturali\n")
				
				exit(99)
		
			print("Uso configurazione vecchia... Verra' aggiornata appena sara' raggiungibile il portale..\n")
			APP_DATA = cache.getCache(check_valid=False)


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

			exit(2)
		except yaml.YAMLError as e:
			print("TEST ABORTITO - File di Configurazione Utente non valido")
			print(e)

			exit(2)


		if "card" in USER_CONFIGURATION:
			CARD = merge_dicts(CARD, USER_CONFIGURATION["card"])

		if "passenger" in USER_CONFIGURATION:
			USER = merge_dicts(USER, USER_CONFIGURATION["passenger"])

		if "travel" in USER_CONFIGURATION:
			TRAVEL_DETAILS = merge_dicts(TRAVEL_DETAILS, USER_CONFIGURATION["travel"])

			
		# exit()
		
	
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

	try:
		for ambiente in CLI_ARGS.ambienti:
			print("-------------------------------------------------------------------------------")
			print (f"Test di acquisto per {ambiente}")

			if not ambiente in nodes["Pico"]:
				print (f"\nATTENZIONE - L'ambiente '{ambiente}' non esiste o il file di configurazione potrebbe non essere aggiornato.")
				continue

			ENDPOINT = [ jvm["urls"]["https"] for jvm in nodes["Pico"][ambiente]["B2C"]["APPLICATION_SERVER"] ]
			
			if not ambiente in risultati_test:
				risultati_test[ambiente] = {
					"totale_nodi": len(ENDPOINT),
					"risultati": []
				}
			
			for index, url in enumerate(ENDPOINT):
				print(f"{ambiente} B2C [nodo {index+1} di {len(ENDPOINT)}] - {url}")
				
				test_success = singleNodeTest(url)
				

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
	
	if not CLI_ARGS.ambienti:
		print("---------------------------------------------------------------------------------------------")
		print("                                       ATTENZIONE                                            ")
		print("              Nessun ambiente specificato. Aggiungine uno per iniziare i test.				")
		print("  Per un controllo degli ambienti disponibili vai su http://ngppgtsfe.pico.gts/was/ng-nodes	")
		print("---------------------------------------------------------------------------------------------")



	program_end = time()

	print("\n\n")
	print("----------------------------------------------------------------------------------------------------------------------------------  	")
	print("Riepilogo Generale".center(130))
	print("----------------------------------------------------------------------------------------------------------------------------------  	")
	print("")
	print("---------------------------".center(130))
	print("|  Statistiche generiche  |".center(130))
	print("---------------------------".center(130))
	print("")
	print(f"- Durata complessiva test:     {timedelta(seconds=int(program_end - all_test_start))} -".center(130))
	print(f"- Durata totale programma:     {timedelta(seconds=int(program_end - program_start))} -".center(130))
	print("\n\n")
	print("--------------------".center(130))
	print("|  Risultati Test  |".center(130))
	print("--------------------".center(130))

	for ambiente in risultati_test:
		print(f"{ambiente.title()}:")

		for test in risultati_test[ambiente]["risultati"]:
			ip_add = re.search(r"https?://[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.([0-9]{1,3})", test['url']).group(1)

			print(f"\t{test['nodo']}) Nodo {ip_add}: \t{ 'Ok' if test['result'] else 'Fallito' }\t\t[{test['url']}]")

		print("")

	if not all([ risultato["result"] for ambiente in risultati_test for risultato in risultati_test[ambiente]["risultati"] ]):
		pass
		# print("\n\n")
		# print("Aiuto".center(130))
		# print("- Controlla la log per vedere dove sono FALLITI i test.. -".center(130))
		# print("- Puoi rilanciare i test falliti semplicemnte rilanciando il programma con l'ambiente corrispondente come parametro -".center(130))
	
	print("\n\n")
	print("Suggerimento".center(130))
	print("Per una lista completa delle opzioni disponibili rilancia il programma fornendo il parametro '-h'".center(130))


	print("----------------------------------------------------------------------------------------------------------------------------------\n	")
	
	input("\nPremi INVIO per continuare\n")