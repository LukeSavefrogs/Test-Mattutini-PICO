import requests
from json.decoder import JSONDecodeError

import re

import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def _fetchActiveCell (url: str):
		"""
			Restituisce la cella attiva
		"""
		data = {}
		active_cell = ""
		try:
			data = requests.get(url).json()["active"]
		except (ValueError, JSONDecodeError):
			# no JSON returned
			raise ValueError(f"L'URL '{url}' non contiene un JSON!")
		except (IndexError, KeyError, TypeError):
			# data does not have the inner structure you expect
			raise ValueError(f"L'URL '{url}' non contiene la cella attiva (campo 'active')!")
		except requests.exceptions.ConnectionError:
			# data does not have the inner structure you expect
			raise ValueError(f"Errore di connessione all'URL '{url}'")
		
		return str(data).lower()



def get_active_cell(project: str, environment: str, useVip: bool = True):
	"""Returns the active cell for the provided Project and Environment

	Args:
		project (str): Project (C2C/PICO)
		environment (str): Environment (Produzione/Correttiva)
		useVip (bool, optional): Wether to pass through the VIP. Defaults to True.

	Raises:
		ex: Exception occurred during data fetching from the URL

	Returns:
		str: Name of the active cell in lowercase (green/blue) or None if not found
	"""
	if project.upper() == "PICO":
		if environment.lower() == "produzione":
			url = "http://lefrecce.it/active/" if useVip else "http://172.24.129.248/active/"
		elif environment.lower() == "certificazione":
			url = "http://cert.web.pico.trn/active/" if useVip else "http://172.24.122.248/active/"
		elif environment.lower() == "correttiva":
			url = "http://correttiva.web.pico.trn/active/"
		else:
			logger.error(f"Environment '{environment}' not valid")
			# raise EnvironmentParsingException(f"Environment '{environment}' not valid")
			return None
		
	elif project.upper() == "C2C":
		if environment.lower() == "produzione":
			url = "http://tickets.c2c-online.co.uk/active/"
		elif environment.lower() == "correttiva":
			url = "http://ticketsstaging.c2c-online.co.uk/active/"
		else:
			logger.error(f"Environment '{environment}' not valid")
			# raise EnvironmentParsingException(f"Environment '{environment}' not valid")
			return None

	else:
		logger.error(f"Project '{project.upper()}' not valid")
		# raise EnvironmentParsingException(f"Project '{project.upper()}' not valid")
		return None
	
	try:
		return _fetchActiveCell(url=url)
	except Exception as ex:
		logger.exception("Exception while fetching the current active cell")
		raise ex






_ENVS_ABBREV = {
	"correttiva": "corr",
	"certificazione": "cert",
	"integrazione": "int",
	"sviluppo": "svil",
	"produzione": "prod",
	"training": "train",
	"ams": "ams"
}

class EnvironmentParser (object):
	def __init__(self, project: str, environment: str):
		self.project = project.upper()
		self.environment = environment.lower()
	
		is_multicell_environment = re.match("^([a-zA-Z]+)-(Green|Blue)$", environment, flags=re.IGNORECASE)

		# Se è stato passato un ambiente del tipo 'Corr-Blue'
		if is_multicell_environment:
			self.environment = dict((v,k) for k,v in _ENVS_ABBREV.items()).get(is_multicell_environment.group(1).lower())
			self.cell_color = is_multicell_environment.group(2).lower()

			# Controlla se esiste la cella
			active_cell = get_active_cell(self.project, self.environment)
			if active_cell is None:
				# La cella deve esistere per forza se si punta direttamente
				raise EnvironmentParsingException (f"No requested Blue/Green cell found for project '{project}' and environment '{environment}'")
			self.has_multi_cell = True

			self.is_active_cell = active_cell == self.cell_color

			self.name_short = f"{_ENVS_ABBREV[self.environment].title()}-{self.cell_color.title()}" if self.environment in _ENVS_ABBREV else environment

		else:	# 'Correttiva'
			active_cell = get_active_cell(self.project, self.environment)
			self.has_multi_cell = active_cell is not None
			self.cell_color = active_cell if self.has_multi_cell else ""

			self.is_active_cell = True

			if self.has_multi_cell:
				self.name_short = f"{_ENVS_ABBREV[self.environment].title()}-{self.cell_color.title()}"
			else:
				self.name_short = self.environment.title()

		self.name_full = f"{self.environment.title()} {self.cell_color.title()}".strip()




	def is_active(self):
		active_cell = get_active_cell(self.project, self.environment)
		return active_cell.lower() == self.cell_color.lower()

	def is_full_name(self):
		_ENVS_ABBREV
	


class EnvironmentParsingException(Exception):
    """Exception raised for errors in the EnvironmentParser class.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Error while parsing the Environment"):
        self.message = message
        super().__init__(self.message)



def get_color_from_env (environment: str):
	pass


if __name__ == '__main__':
	print("Test Start:")

	# print (vars(EnvironmentParser(project="PICO", environment="produzione")))
	# print (vars(EnvironmentParser(project="PICO", environment="prod-green")))
	# print (vars(EnvironmentParser(project="PICO", environment="prod-blue")))
	# print (vars(EnvironmentParser(project="PICO", environment="certificazione")))
	# print (vars(EnvironmentParser(project="PICO", environment="cert")))
	# print (vars(EnvironmentParser(project="PICO", environment="asdfhgklzf")))
	# print (vars(EnvironmentParser(project="PICO", environment="asdfhgklzfa-asgjfghf")))
	print (vars(EnvironmentParser(project="PICO", environment="Cert-GREEN")))
	print (vars(EnvironmentParser(project="PICO", environment="corr-blue")))
	print (vars(EnvironmentParser(project="PICO", environment="integrazione")))
	print (vars(EnvironmentParser(project="c2c", environment="Certificazione")))
	print (vars(EnvironmentParser(project="c2c", environment="Cert-Green")))
	print (vars(EnvironmentParser(project="c2c", environment="Corr-Green")))