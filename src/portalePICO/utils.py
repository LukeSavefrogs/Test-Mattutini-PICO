import traceback
from portalePICO.core import PortalePicoGTS

class Trenitalia(object):
	@staticmethod
	def getInfrastructure():
		nodi = {}
		
		# --------------------------------------------------------------------------
		#							Scrape data
		# --------------------------------------------------------------------------
		print ("<PortalePicoGTS-PyScraper>")
		try:
			gts = PortalePicoGTS()
			gts.login("ictsmoperator", "Pico.GTS")

			nodi = gts.getNodes()
			gts.close()
			
		except Exception as e:
			print("ERRORE - " + str(e))
			print("Stacktrace:")
			traceback.print_stack()

		finally:
			print()
			print("</PortalePicoGTS-PyScraper>")

		return nodi
