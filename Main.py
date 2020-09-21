import json
import logging
import math
import os
import time
from itertools import islice
from os import listdir
from os.path import isfile, join

# LOGGING CONFIGURATION
import docker

logging.basicConfig(format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
logging.getLogger().setLevel(logging.INFO)

#  CONST VARIABLES (make sure to Modify them before using this script)
ServerIpAddress = "192.168.1.5"
DockerApiUrlPort = "tcp://192.168.1.5:2375"
WebServersLogsFolderPath = "/home/amir/containerAutoScalingScripts/logs/"
ScaleUpThreshold = 40
ScaleDownThreshold = 10
ScaleUpAverageThreshold = 40
Coefficient_X = 2
Coefficient_Y = 1
Coefficient_Z = 1
HaProxyConfigFilePath = "/etc/haproxy/haproxy.cfg"
HaProxyInitConfigFile = """
global
	log /dev/log	local0
	log /dev/log	local1 notice
	chroot /var/lib/haproxy
	stats socket /run/haproxy/admin.sock mode 660 level admin expose-fd listeners
	stats timeout 30s
	user haproxy
	group haproxy
	daemon

	# Default SSL material locations
	ca-base /etc/ssl/certs
	crt-base /etc/ssl/private

	# Default ciphers to use on SSL-enabled listening sockets.
	# For more information, see ciphers(1SSL). This list is from:
	#  https://hynek.me/articles/hardening-your-web-servers-ssl-ciphers/
	# An alternative list with additional directives can be obtained from
	#  https://mozilla.github.io/server-side-tls/ssl-config-generator/?server=haproxy
	ssl-default-bind-ciphers ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:RSA+AESGCM:RSA+AES:!aNULL:!MD5:!DSS
	ssl-default-bind-options no-sslv3

defaults
	log	global
	mode	http
	option	httplog
	option	dontlognull
        timeout connect 5000
        timeout client  50000
        timeout server  50000
	errorfile 400 /etc/haproxy/errors/400.http
	errorfile 403 /etc/haproxy/errors/403.http
	errorfile 408 /etc/haproxy/errors/408.http
	errorfile 500 /etc/haproxy/errors/500.http
	errorfile 502 /etc/haproxy/errors/502.http
	errorfile 503 /etc/haproxy/errors/503.http
	errorfile 504 /etc/haproxy/errors/504.http

frontend Local_Server
    bind 192.168.1.5:80
    mode http
    default_backend My_Web_Servers

backend My_Web_Servers
    mode http
    balance roundrobin
    option forwardfor
    http-request set-header X-Forwarded-Port %[dst_port]
    http-request add-header X-Forwarded-Proto https if { ssl_fc }
    option httpchk HEAD / HTTP/1.1rnHost:localhost
    #server web1.example.com  192.168.1.101:80
    #server web2.example.com  192.168.1.102:80
"""


class DockerUtil:
    def __init__(self, dockerClient):
        self.dockerClient = dockerClient

    def createContainer(self, image, name, memory, command, ports):
        if not self.ifContainerExist(name):
            try:
                container = self.dockerClient.containers.run(image=image, name=name, mem_limit=memory, ports=ports,
                                                             command=command, detach=True)
                logging.info("Container has successfully created")
                return container
            except Exception as e:
                logging.error(e)

        else:
            logging.error("Container has already existed, duplicated name")

    def removeCountainer(self, containerName):
        if self.ifContainerExist(containerName):
            try:
                container = self.dockerClient.containers.get(containerName)
                container.remove(force=True)
                logging.info("Container has been successfully deleted")
            except Exception as e:
                logging.error(e)
        else:
            logging.error("Container does not exist")

    # Sample Output
    # {'read': '2020-08-28T16:55:21.279921925Z', 'preread': '2020-08-28T16:55:20.280187763Z', 'pids_stats': {'current': 1}, 'blkio_stats': {'io_service_bytes_recursive': [], 'io_serviced_recursive': [], 'io_queue_recursive': [], 'io_service_time_recursive': [], 'io_wait_time_recursive': [], 'io_merged_recursive': [], 'io_time_recursive': [], 'sectors_recursive': []}, 'num_procs': 0, 'storage_stats': {}, 'cpu_stats': {'cpu_usage': {'total_usage': 31387993, 'percpu_usage': [29253741, 2134252], 'usage_in_kernelmode': 10000000, 'usage_in_usermode': 20000000}, 'system_cpu_usage': 17094090000000, 'online_cpus': 2, 'throttling_data': {'periods': 0, 'throttled_periods': 0, 'throttled_time': 0}}, 'precpu_stats': {'cpu_usage': {'total_usage': 31387993, 'percpu_usage': [29253741, 2134252], 'usage_in_kernelmode': 10000000, 'usage_in_usermode': 20000000}, 'system_cpu_usage': 17092100000000, 'online_cpus': 2, 'throttling_data': {'periods': 0, 'throttled_periods': 0, 'throttled_time': 0}}, 'memory_stats': {'usage': 1544192, 'max_usage': 3375104, 'stats': {'active_anon': 98304, 'active_file': 0, 'cache': 0, 'dirty': 0, 'hierarchical_memory_limit': 999997440, 'hierarchical_memsw_limit': 0, 'inactive_anon': 0, 'inactive_file': 0, 'mapped_file': 0, 'pgfault': 698, 'pgmajfault': 0, 'pgpgin': 504, 'pgpgout': 480, 'rss': 98304, 'rss_huge': 0, 'total_active_anon': 98304, 'total_active_file': 0, 'total_cache': 0, 'total_dirty': 0, 'total_inactive_anon': 0, 'total_inactive_file': 0, 'total_mapped_file': 0, 'total_pgfault': 698, 'total_pgmajfault': 0, 'total_pgpgin': 504, 'total_pgpgout': 480, 'total_rss': 98304, 'total_rss_huge': 0, 'total_unevictable': 0, 'total_writeback': 0, 'unevictable': 0, 'writeback': 0}, 'limit': 999997440}, 'name': '/amir', 'id': '3d84761d3455d356c4e681e21cd185c01e2e494b8a04ffa6735245d88be0343a', 'networks': {'eth0': {'rx_bytes': 828, 'rx_packets': 10, 'rx_errors': 0, 'rx_dropped': 0, 'tx_bytes': 0, 'tx_packets': 0, 'tx_errors': 0, 'tx_dropped': 0}}}
    def containerAllStats(self, containerName):
        if self.ifContainerExist(containerName):
            try:
                container = self.dockerClient.containers.get(containerName)
                return container.stats(stream=False)
            except Exception as e:
                logging.error(e)
        else:
            logging.error("Container does not exist")

    def containerCpuUsage(self, containerName):
        if self.ifContainerExist(containerName):
            try:
                jsonData = json.loads(json.dumps(self.containerAllStats(containerName)))
                cpuDelta = jsonData["cpu_stats"]["cpu_usage"]["total_usage"] - jsonData["precpu_stats"]["cpu_usage"][
                    "total_usage"]
                systemDelta = jsonData["cpu_stats"]["system_cpu_usage"] - jsonData["precpu_stats"]["system_cpu_usage"]
                return cpuDelta / systemDelta * 100
            except Exception as e:
                logging.error(e)
        else:
            logging.error("Container does not exist")

    def containerMemoryUsage(self, containerName):
        if self.ifContainerExist(containerName):
            try:
                jsonData = json.loads(json.dumps(self.containerAllStats(containerName)))
                # Return as MB
                return (jsonData["memory_stats"]["usage"] / 1024) / 1024
            except Exception as e:
                logging.error(e)
        else:
            logging.error("Container does not exist")

    def allContainersList(self):
        return self.dockerClient.containers.list()

    def ifContainerExist(self, containerName):
        for container in self.dockerClient.containers.list():
            if containerName == container.name:
                return True
        return False


class FileReader:
    def __init__(self, filePath):
        self.filePath = filePath

    # Output: Array of lines ['Line1', 'Line2', 'Line3', 'Line4', 'Line5']
    def readNumberOfLines(self, numberOfLines):
        if os.path.exists(self.filePath):
            with open(self.filePath) as file:
                head = list(islice(file, numberOfLines))
            # example -> "['Line1\n']"
            # To remove "\n" from the string
            finalArray = []
            for string in head:
                finalArray.append(string.replace('\n', ''))
            return finalArray
        else:
            return []


class HaproxyConfigModifier:
    def __init__(self, filePath):
        self.filePath = filePath

    def addNewDestination(self, destinationString):
        with open(self.filePath, "a") as myfile:
            # Destination string needs to have 4 spaces at the beginning, like below
            #    server web1.example.com  192.168.1.101:80
            myfile.write(destinationString)

    def removeTheNewestDestination(self):
        # Based on the answer from https://stackoverflow.com/questions/1877999/delete-final-line-in-file-with-python
        with open(self.filePath, "r+") as file:
            file.seek(0, os.SEEK_END)
            pos = file.tell() - 1
            while pos > 0 and file.read(1) != "\n":
                pos -= 1
                file.seek(pos, os.SEEK_SET)
            if pos > 0:
                file.seek(pos, os.SEEK_SET)
                file.truncate()

    def reWriteWholeConfigFile(self, configStr):
        # Remove all texts (clean the file)
        with open(self.filePath, 'w'): pass

        with open(self.filePath, 'w+') as fh:
            fh.write(configStr)


class OsCommandRunner:
    def executeCommand(self, command):
        com = os.popen(command)
        logging.info("----------- Executing Command: " + command + " -----------")
        logging.info(com.read())
        logging.info(com.close())
        logging.info("----------------------------------------------------------")


class WebServer:
    def __init__(self, name, mappedPort, weight):
        self.name = name
        self.weight = weight
        self.mappedPort = mappedPort
        self.cpu = -1
        self.memory = -1
        self.memoryUsage = -1
        self.inputTraffic = -1
        self.outPutTraffic = -1
        self.busyThreadsCount = -1
        self.processingReqTime = -1
        self.score = 0
        self.scaleUpFlag = False
        self.scaleDownFlag = False

        # Situations:
        # deathFlag = false  isDead = false --> webServer is alive and active (as a active destination in LB config)
        # deathFlag = true  isDead = false --> webServer is alive but NOT active (removed from LB config)
        # deathFlag = true  isDead = true --> webServer is dead and NOT active (removed physically)
        self.deathFlag = False
        self.isDead = False

    def setStatus(self, cpu, memory, memoryUsage, inputTraffic, outPutTraffic, busyThreadsCount, processingReqTime):
        self.cpu = cpu
        self.memory = memory
        self.memoryUsage = memoryUsage
        self.inputTraffic = inputTraffic
        self.outPutTraffic = outPutTraffic
        self.busyThreadsCount = busyThreadsCount
        self.processingReqTime = processingReqTime

    def isStatusSet(self):
        if (self.cpu > -1 and self.memory > -1 and self.memoryUsage > -1 and self.inputTraffic > -1 and
                self.outPutTraffic > -1 and self.busyThreadsCount > -1 and self.processingReqTime > -1):
            return True
        return False

    def calcucateScoreAndFlags(self, X, Y, Z, maxProcessingTime, scaleUpThr, scaleDownThr):
        self.score = X * ((self.memoryUsage + self.cpu) / 2) + Y * (self.busyThreadsCount / 4) + Z * (
                self.processingReqTime / maxProcessingTime)
        if self.score > scaleUpThr:
            self.scaleUpFlag = True
            self.scaleDownFlag = False
        elif self.score < scaleDownThr:
            self.scaleUpFlag = False
            self.scaleDownFlag = True
        else:
            self.scaleUpFlag = False
            self.scaleDownFlag = False
        return self.score

    def setWeight(self, weight):
        self.weight = weight

    def getWeight(self):
        return self.weight

    def getScaleUpFlag(self):
        return self.scaleUpFlag

    def getScaleDownFlag(self):
        return self.scaleDownFlag

    def setDeathFlag(self, flag):
        self.deathFlag = flag

    def getDeathFlag(self):
        return self.deathFlag

    def setIsDead(self, flag):
        self.isDead = flag

    def getIsDead(self):
        return self.isDead


def createConfigFileBasedOnAliveCountainer(webServerObjArray, haproxyInitConfigFileTxt):
    tempStr = ''
    for webServer in webServerObjArray:
        if not webServer.getDeathFlag():
            tempStr += "    server " + webServer.name + "  " + ServerIpAddress + ':' + str(
                webServer.mappedPort) + " weight " + str(math.ceil(webServer.weight)) + "\n"
    return haproxyInitConfigFileTxt + tempStr


def checkMajority(arrayToCheck, numberofWebServers):
    majority = numberofWebServers / 2
    numberOfHint = 0
    for item in arrayToCheck:
        if item == "1":
            numberOfHint += 1

    if numberOfHint > majority:
        return True
    else:
        return False


if __name__ == "__main__":

    newlyWebServerList = {}
    initialScenarioContainerList = {}
    # numberOfWebServers = 1  # There is already 1 web server for initial scenario
    AllWebServersOBJ = []
    # Objects
    client = docker.DockerClient(base_url=DockerApiUrlPort)
    dockerUtils = DockerUtil(client)
    osCommandRunner = OsCommandRunner()
    haproxyConfigModifier = HaproxyConfigModifier(HaProxyConfigFilePath)
    # ----------------------------------------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------
    # Create Initial Scenario
    # Create Sender Httperf
    # 100000000 -> ~~ 100 Meg (Need to be converted to 1024)
    senderContainer = dockerUtils.createContainer("bvnf6", "sender", 1000000000, command="tail -f /dev/null", ports={
        # Container Port : Host Port
        '80': 8000
    })
    # Create web server
    webServerContainre = dockerUtils.createContainer("httpd_final", "app" + str(1), 1000000000,
                                                     command='', ports={
            # Container Port : Host Port
            '80': 8010 + 1
        })

    AllWebServersOBJ.append(WebServer("app1", 8010 + 1, 1))
    # Edit the haProxy config file and add the destination
    # Destination string needs to have 4 spaces at the beginning, like below
    #    server web1.example.com  192.168.1.101:80 weight 10
    haproxyConfigModifier.reWriteWholeConfigFile(
        createConfigFileBasedOnAliveCountainer(AllWebServersOBJ, HaProxyInitConfigFile))
    time.sleep(2)
    # Restarting the HaProxy service
    osCommandRunner.executeCommand("service haproxy restart")
    time.sleep(1)
    osCommandRunner.executeCommand("service haproxy status | grep Active")

    if senderContainer.id:
        initialScenarioContainerList["sender"] = senderContainer.id
    if webServerContainre.id:
        initialScenarioContainerList["app1"] = webServerContainre.id

    if initialScenarioContainerList.get("sender") and initialScenarioContainerList.get("app1"):
        logging.info("Initial scenario is deployed")
    else:
        logging.error("Could not create initial scenario")
    # ----------------------------------------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------

    forceToCreate = True
    # Main Loop
    logging.info(" ")
    logging.info("**** STARTING THE MAIN LOOP ****")
    logging.info(" ")
    while True:
        sumOfAllInvertedScore = 0
        for webServer in AllWebServersOBJ:
            readAllStats = False
            # ******* SECTION 1 *******
            # Check weather web server is still alive and Loop until all status are available
            # We still check the web server's status even if it has death flag since in order to remove the
            # container we need to check the "busy" Thread = 1 after checking this thread, the script sets
            # the "isDead" flag and removes the container physically at section "#******* SECTION 2 *******#"
            if not webServer.getIsDead():
                while not readAllStats:
                    fileReader = FileReader(WebServersLogsFolderPath + webServer.name)
                    temp = []
                    # {'Cpu': '0.01', 'Memory': '12.58MiB', 'MemoryUsage': '0.21', 'InputTraffic': '1.82kB', 'OutPutTraffic': '9.1kB', 'BusyThreadsCount': '1', 'ProcessingReqTime': '200'}
                    stats = fileReader.readNumberOfLines(7)
                    for data in stats:
                        temp.append(((data.split())[1]).replace("%", ""))
                    if len(temp) == 7:
                        readAllStats = True
                        # cpu, memory, memoryUsage, inputTraffic, outPutTraffic, busyThreadsCount, processingReqTime
                        webServer.setStatus(float(temp[0]), temp[1], float(temp[2]), temp[3], temp[4], int(temp[5]), int(temp[6]))
                        webServer.calcucateScoreAndFlags(Coefficient_X, Coefficient_Y, Coefficient_Z,
                                                         500, ScaleUpThreshold, ScaleDownThreshold)
                        # Sum Up all inverted score for calculation the weight of the web server in the next step
                        sumOfAllInvertedScore += 1 / webServer.score

                        print("--------------------------")
                        print(webServer.name + " score is: " + str(webServer.score))
                        print(webServer.name + " death flag is: " + str(webServer.getDeathFlag()))
                        print(temp)
                        print("sumOfAllInvertedScore  " + str(sumOfAllInvertedScore))
                        print("--------------------------")
                        time.sleep(1)


        # ******* SECTION 2 *******
        # Count the "scaleDown/scaleUp" FLAGs from webServer OBJs & Calculate average of all scores
        # ALSO physical removal of the container happens here ( container death flag = True &
        # busyThread < 3 (meaning all requests have been processed) )
        # At section "#******* SECTION 4 *******#" the container will be marked as a "To Be Removed" and
        # it will be removed from HaProxy config file and score calculation HOWEVER physical removal will happens here
        numberOfScaleDownFlag = 0
        numberOfScaleUpFlag = 0
        numberOfCurrentAliveWebServers = 0
        sumOfAllScores = 0
        allWebServersScoreAvg = 0
        # highestWeight = ((1 / AllWebServersOBJ[0].score) / sumOfAllInvertedScore) * 100
        # lowestScore = AllWebServersOBJ[0].score
        # lowestScoreWebServerName = AllWebServersOBJ[0].name
        highestWeight = -1
        lowestScore = 9999
        lowestScoreWebServerName = ''
        for objServer in AllWebServersOBJ:
            if not objServer.getIsDead():
                if not objServer.getDeathFlag():
                    # Set the weight of web server
                    objServer.setWeight(
                        ((1 / objServer.score) / sumOfAllInvertedScore) * 100
                    )
                    numberOfCurrentAliveWebServers = numberOfCurrentAliveWebServers + 1
                    sumOfAllScores = sumOfAllScores + objServer.score
                    if lowestScore >= objServer.score:
                        lowestScore = objServer.score
                        lowestScoreWebServerName = objServer.name
                    if objServer.getWeight() >= highestWeight:
                        highestWeight = objServer.weight
                    if objServer.scaleUpFlag:
                        numberOfScaleUpFlag = numberOfScaleUpFlag + 1
                    elif objServer.scaleDownFlag:
                        numberOfScaleDownFlag = numberOfScaleDownFlag + 1
                else:
                    # Container physically removal
                    if int(objServer.busyThreadsCount) < 4:
                        objServer.setIsDead(True)
                        dockerUtils.removeCountainer(objServer.name)
                        print("~~~~~~~~~~~~~~~~~~~~~ REMOVAL ~~~~~~~~~~~~~~~~~~~~~")
                        logging.info("Web Server " + objServer.name + " has been removed")
                        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

        print("sumOfAllInvertedScore " + str(sumOfAllInvertedScore))
        print("highestWeight " + str(highestWeight))
        print("lowestScoreWebServerName " + str(lowestScoreWebServerName))
        print("lowestScore " + str(lowestScore))
        print("numberOfScaleDownFlag " + str(numberOfScaleDownFlag))
        print("numberOfScaleUpFlag " + str(numberOfScaleUpFlag))
        print("numberOfCurrentAliveWebServers " + str(numberOfCurrentAliveWebServers))
        print("AllWebServersCount " + str(len(AllWebServersOBJ)))
        print("sumOfAllScores " + str(sumOfAllScores))
        print("sumOfAllScores / numberOfCurrentAliveWebServers: " + str(sumOfAllScores / numberOfCurrentAliveWebServers))

        # ******* SECTION 3 *******
        # Scaling UP
        if numberOfScaleUpFlag > (numberOfCurrentAliveWebServers / 2) or (
                sumOfAllScores / numberOfCurrentAliveWebServers) > ScaleUpAverageThreshold:
            AllWebServersOBJ.append(
                WebServer(("app" + str(len(AllWebServersOBJ) + 1)), 8010 + len(AllWebServersOBJ) + 1, highestWeight))

            webServerContainre = dockerUtils.createContainer("httpd_final", "app" + str(len(AllWebServersOBJ)),
                                                             1000000000,
                                                             command='', ports={
                    # Container Port : Host Port
                    '80': 8010 + len(AllWebServersOBJ)
                })
            logging.info("Web Server " + ("app" + str(len(AllWebServersOBJ))) + " has been added")
            logging.info("Modify and Restart HaProxy")

            # Edit the haProxy config file and add the destination
            # Destination string needs to have 4 spaces at the beginning, like below
            #    server web1.example.com  192.168.1.101:80 weight 10
            haproxyConfigModifier.reWriteWholeConfigFile(
                createConfigFileBasedOnAliveCountainer(AllWebServersOBJ, HaProxyInitConfigFile))

            # Restarting the HaProxy service
            osCommandRunner.executeCommand("service haproxy restart")
            time.sleep(1)
            osCommandRunner.executeCommand("service haproxy status | grep Active")

        # ******* SECTION 4 *******
        # Scaling Down
        if numberOfScaleDownFlag > numberOfCurrentAliveWebServers / 2:
            if numberOfCurrentAliveWebServers > 1:
                if lowestScoreWebServerName != '':
                    for webs in AllWebServersOBJ:
                        if not webs.getIsDead():
                            if webs.name == lowestScoreWebServerName:
                                webs.setDeathFlag(True)
                                # Removing the web server from HaProxy config file by setting "setDeathFlag(True)"
                                haproxyConfigModifier.reWriteWholeConfigFile(
                                    createConfigFileBasedOnAliveCountainer(AllWebServersOBJ, HaProxyInitConfigFile))
                                # Restarting the HaProxy service
                                osCommandRunner.executeCommand("service haproxy restart")
                                time.sleep(1)
                                osCommandRunner.executeCommand("service haproxy status | grep Active")


        print("########################################################################################################################")
        print("########################################################################################################################")
        print("########################################################################################################################")




