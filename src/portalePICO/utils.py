import logging
from portalePICO.core import PortalePicoGTS

class Trenitalia(object):
	@staticmethod
	def getInfrastructure(headless=True):
		nodi = {}
		
		# --------------------------------------------------------------------------
		#							Scrape data
		# --------------------------------------------------------------------------
		print ("<PortalePicoGTS-PyScraper>")
		try:
			gts = PortalePicoGTS(headless=headless)
			gts.login("ictsmoperator", "Pico.GTS")

			nodi = gts.getNodes()
			gts.close()
			
		except Exception as e:
			print("ERRORE - " + str(e))
			logging.exception("Stacktrace:")

		finally:
			print()
			print("</PortalePicoGTS-PyScraper>")

		return nodi