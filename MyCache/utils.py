from portalePICO.main import PortalePicoGTS
import os
from datetime import datetime
import time

import json
import yaml

from packaging.version import Version, LegacyVersion, InvalidVersion

HOME = os.path.expanduser("~")

class Cache(object):
	__FILE_BASENAME = ""
	__MIN_SECONDS_BEFORE_UPDATE = 604800
	__API_VERSION = ""

	def __init__(self, fileName, apiVersion = "0.0.0") -> None:
		self.__FILE_BASENAME = fileName
		self.__API_VERSION = apiVersion



	def getCacheFilename(self):
		return os.path.join(HOME, self.__FILE_BASENAME)


	def getCache(self, check_valid = True):
		"""
		Restituisce i nodi salvati su disco
		"""
		if check_valid and self.hasExpired(): 
			return None
		
		config = {}

		# Leggo dal file
		with open(self.getCacheFilename(), 'r') as stream:
			config = yaml.safe_load(stream)

		return config
		

	def setCache(self, data: dict):
		"""Writes the configuration to file, so that it can easily be retrieved

		Args:
			data (dict): The data to be saved
		"""

		payload = {
			"metadata": {
				"timestamp": int(datetime.now().timestamp()),
				"version": self.__API_VERSION
			},
			"data": data
		}

		with open(self.getCacheFilename(), 'w') as outfile:
			yaml.dump(payload, outfile, default_flow_style=False, explicit_start=True, explicit_end=True, indent=4)
		
		return payload

	
	def hasExpired(self):
		"""
		docstring
		"""
		# Controlla se esiste già il file usato come "Cache"
		if not os.path.exists(self.getCacheFilename()):
			return True


		# Leggo dal file
		with open(self.getCacheFilename(), 'r') as stream:
			config = yaml.safe_load(stream)

		try:
			# Se i dati sono troppo vecchi...
			last_updated_ts = config['metadata']['timestamp']

			DATE_TOO_OLD = (int(datetime.now().timestamp()) - last_updated_ts) >= self.__MIN_SECONDS_BEFORE_UPDATE
			IS_OLD_VERSION = Version(self.__API_VERSION) > Version(config['metadata']['version'])
			
			return DATE_TOO_OLD or IS_OLD_VERSION
		except (KeyError, InvalidVersion):
			return True


	def exists(self):
		"""
		docstring
		"""
		# Controlla se esiste già il file usato come "Cache"
		if os.path.exists(self.getCacheFilename()):
			with open(self.getCacheFilename(), 'r') as stream:
				config = yaml.safe_load(stream)
			
			return "data" in config

		return False