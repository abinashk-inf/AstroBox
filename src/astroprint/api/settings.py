# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import os
import time

from flask import request, abort, jsonify, make_response

from octoprint.settings import settings
from astroprint.printer.manager import printerManager
from astroprint.network.manager import networkManager

from octoprint.server import restricted_access, admin_permission, softwareManager, UI_API_KEY
from octoprint.server.api import api

# Import Babel
from flask.ext.babel import Babel, gettext
from babel import Locale
# end Babel

@api.route("/settings/printer", methods=["GET", "POST"])
def handlePrinterSettings():
	s = settings()
	pm = printerManager()
	connectionOptions = pm.getConnectionOptions()

	if request.method == "POST":
		if "application/json" in request.headers["Content-Type"]:
			data = request.json

			if "serial" in data.keys():
				if "port" in data["serial"].keys(): s.set(["serial", "port"], data["serial"]["port"])
				if "baudrate" in data["serial"].keys(): s.setInt(["serial", "baudrate"], data["serial"]["baudrate"])

			s.save()

	return jsonify({
		"driver": pm.driverName,
		"serial": {
			"port": connectionOptions["portPreference"],
			"baudrate": connectionOptions["baudratePreference"],
			"portOptions": connectionOptions["ports"].items(),
			"baudrateOptions": connectionOptions["baudrates"]
		}
	})

@api.route("/settings/network/name", methods=["GET", "POST"])
@restricted_access
def handleNetworkName():
	nm = networkManager()

	if request.method == "POST":
		if "application/json" in request.headers["Content-Type"]:
			data = request.json

			nm.setHostname(data['name'])

		else:
			return ("Invalid Request", 400)

	return jsonify(name=nm.getHostname())

@api.route("/settings/network/wifi-networks", methods=["GET"])
@restricted_access
def getWifiNetworks():
	networks = networkManager().getWifiNetworks()

	if networks:
		return jsonify(networks = networks)
	else:
		return jsonify({'message': gettext('unableToGetWifi')})

@api.route("/settings/network", methods=["GET"])
@restricted_access
def getNetworkSettings():
	nm = networkManager()

	return jsonify({
		'networks': nm.getActiveConnections(),
		'hasWifi': bool(nm.getWifiDevice())
	})

@api.route("/settings/network/active", methods=["POST"])
@restricted_access
def setWifiNetwork():
	if "application/json" in request.headers["Content-Type"]:
		data = request.json
		result = networkManager().setWifiNetwork(data['id'], data['password'])

		if result:
			return jsonify(result)
		else:
			return (gettext('netSNotFound') % data['id'], 404)

	return ("Invalid Request", 400)

@api.route("/settings/network/hotspot", methods=["GET", "POST", "PUT", "DELETE"])
@restricted_access
def handleWifiHotspot():
	nm = networkManager()

	if request.method == "GET":
		return jsonify({
			'hotspot': {
				'active': nm.isHotspotActive(),
				'name': nm.getHostname(),
				'hotspotOnlyOffline': settings().getBoolean(['wifi', 'hotspotOnlyOffline'])
			} if nm.isHotspotable() else False
		})

	elif request.method == "PUT":
		if "application/json" in request.headers["Content-Type"]:
			data = request.json

			if "hotspotOnlyOffline" in data:
				s = settings()
				s.setBoolean(['wifi', 'hotspotOnlyOffline'], data["hotspotOnlyOffline"])
				s.save()
				return jsonify()

		return ("Invalid Request", 400)

	elif request.method == "DELETE":
		result = networkManager().stopHotspot()

		if result is True:
			return jsonify()
		else:
			return (result, 500)

	else: #POST
		result = nm.startHotspot()

		if result is True:
			return jsonify()
		else:
			return (result, 500)

@api.route("/settings/software/general", methods=["GET"])
def getGeneralSoftwareSettings():
	s = settings()
	return jsonify(
		language= s.get(['language'])
	)
@api.route("/settings/software/advanced", methods=["GET"])
@restricted_access
def getAdvancedSoftwareSettings():
	s = settings()
	logsDir = s.getBaseFolder("logs")

	return jsonify(
		apiKey= UI_API_KEY,
		serialActivated= s.getBoolean(['serial', 'log']),
		sizeLogs= sum([os.path.getsize(os.path.join(logsDir, f)) for f in os.listdir(logsDir)]),
		language= s.get(['language'])
	)

@api.route("/settings/software/settings", methods=["DELETE"])
@restricted_access
def resetFactorySettings():
	from astroprint.cloud import astroprintCloud

	logger = logging.getLogger(__name__)
	logger.warning("Executing a Restore Factory Settings operation")

	#We log out first
	astroprintCloud().signout()

	s = settings()

	#empty all folders
	def emptyFolder(folder):
		if folder and os.path.exists(folder):
			for f in os.listdir(folder):
				p = os.path.join(folder, f)
				try:
					if os.path.isfile(p):
						os.unlink(p)
				except Exception, e:
					pass

	emptyFolder(s.get(['folder', 'uploads']) or s.getBaseFolder('uploads'))
	emptyFolder(s.get(['folder', 'timelapse']) or s.getBaseFolder('timelapse'))
	emptyFolder(s.get(['folder', 'timelapse_tmp']) or s.getBaseFolder('timelapse_tmp'))
	emptyFolder(s.get(['folder', 'virtualSd']) or s.getBaseFolder('virtualSd'))

	#replace config.yaml with config.factory
	config_file = s._configfile
	os.unlink(config_file)

	#remove info about users
	user_file  = settings().get(["accessControl", "userfile"]) or os.path.join( os.path.dirname(config_file), "users.yaml")
	if user_file and os.path.exists(user_file):
		os.unlink(user_file)

	s._config = {}
	s.load(migrate=False)

	networkManager().forgetWifiNetworks()

	#We should reboot the whole device
	softwareManager.restartServer()

	return jsonify()

@api.route("/settings/software/check", methods=['GET'])
@restricted_access
def checkSoftwareVersion():
	softwareInfo = softwareManager.checkSoftwareVersion()

	if softwareInfo:
		s = settings()
		s.set(["software", "lastCheck"], time.time())
		s.save()
		return jsonify(softwareInfo);
	else:
		return (gettext('errorCheckingSoft'), 400)

@api.route("/settings/software/update", methods=['POST'])
@restricted_access
def updateSoftwareVersion():
	if softwareManager.updateSoftwareVersion(request.get_json()):
		return jsonify();
	else:
		return (gettext('errorIniUpdate'), 400)

@api.route("/settings/software/restart", methods=['POST'])
@restricted_access
def restartServer():
	if softwareManager.restartServer():
		return jsonify();
	else:
		return (gettext('errorRestartServer'), 400)

@api.route("/settings/software/logs", methods=['POST'])
@restricted_access
def sendLogs():
	if softwareManager.sendLogs(request.values.get('ticket', None), request.values.get('message', None)):
		return jsonify();
	else:
		return (gettext('errorSendLogs'), 500)

@api.route("/settings/software/language", methods=['PUT'])
def changeLanguage():
	data = request.json

	if data and 'lang' in data:
		s = settings()
		s.set(['language'], data['lang'])
		s.save()
		return jsonify();
	else:
		return ("Wrong data sent in.", 400)

@api.route("/settings/software/logs/serial", methods=['PUT'])
@restricted_access
def changeSerialLogs():
	data = request.json

	if data and 'active' in data:
		s = settings()
		s.setBoolean(['serial', 'log'], data['active'])
		s.save()

		printerManager().setSerialDebugLogging(data['active'])

		return jsonify();

	else:
		return ("Wrong data sent in.", 400)

@api.route("/settings/software/logs", methods=['DELETE'])
@restricted_access
def clearLogs():
	if softwareManager.clearLogs():
		return jsonify();
	else:
		return (gettext('errorClearLogs'), 500)
