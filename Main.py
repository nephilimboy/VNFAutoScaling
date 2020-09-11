import json
import logging
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
HaProxyConfigFilePath = "/etc/haproxy/haproxy.cfg"


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


class OsCommandRunner:
    def executeCommand(self, command):
        com = os.popen(command)
        logging.info("----------- Executing Command: " + command + " -----------")
        logging.info(com.read())
        logging.info(com.close())
        logging.info("----------------------------------------------------------")


class WebServer:
    def __init__(self, cpu, memory, memoryUsage, inputTraffic, outPutTraffic, busyThreadsCount):
        self.cpu = cpu
        self.memory = memory
        self.memoryUsage = memoryUsage
        self.inputTraffic = inputTraffic
        self.outPutTraffic = outPutTraffic
        self.busyThreadsCount = busyThreadsCount


# Output :  sorted list of ['app2', 'app5', 'app3', 'app1', 'app4'] -> ['app1', 'app2', 'app3', 'app4', 'app5']
def getLogsFilesName(logFilesPath):
    files = [f for f in listdir(logFilesPath) if isfile(join(logFilesPath, f))]
    time.sleep(1)
    temp = []
    for name in files:
        if name.startswith('app'):
            temp.append(name)
    return sorted(temp)


def getCpuTriggerCondition():
    # CPU% TriggerCondition for [WebServer1, WebServer2, WebServer3, WebServer4, ... , WebServerN]
    # If the number of WebServers list is grater than the TriggerCondition list, the last TriggerCondition will be applied to extra WebServers
    # If the number of WebServers list is less than the TriggerCondition list, Nothing would happens :D
    return [50, 50, 20]


def getMemoryUsageTriggerCondition():
    # MemoryUsage% TriggerCondition for [WebServer1, WebServer2, WebServer3, WebServer4, ... , WebServerN]
    # If the number of WebServers list is grater than the TriggerCondition list, the last TriggerCondition will be applied to extra WebServers
    # If the number of WebServers list is less than the TriggerCondition list, Nothing would happens :D
    return [10, 70, 20]


def getInputTrafficTriggerCondition():
    # InputTraffic KB TriggerCondition for [WebServer1, WebServer2, WebServer3, WebServer4, ... , WebServerN]
    # If the number of WebServers list is grater than the TriggerCondition list, the last TriggerCondition will be applied to extra WebServers
    # If the number of WebServers list is less than the TriggerCondition list, Nothing would happens :D
    return [30, 40, 20]


def getOutPutTrafficTriggerCondition():
    # OutPutTraffic KB TriggerCondition for [WebServer1, WebServer2, WebServer3, WebServer4, ... , WebServerN]
    # If the number of WebServers list is grater than the TriggerCondition list, the last TriggerCondition will be applied to extra WebServers
    # If the number of WebServers list is less than the TriggerCondition list, Nothing would happens :D
    return [10, 10, 20]


def getBusyThreadsCountTriggerCondition():
    # BusyThreadsCount TriggerCondition for [WebServer1, WebServer2, WebServer3, WebServer4, ... , WebServerN]
    # If the number of WebServers list is grater than the TriggerCondition list, the last TriggerCondition will be applied to extra WebServers
    # If the number of WebServers list is less than the TriggerCondition list, Nothing would happens :D
    return [10, 10, 10]


def chekTriggerConditionToReadStatus(numberOfWebServers, triggerConditionArray, readStatus):
    pass

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
    numberOfWebServers = 1  # There is already 1 web server for initial scenario

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
    webServerContainre = dockerUtils.createContainer("httpd_final", "app" + str(numberOfWebServers), 1000000000,
                                                     command='', ports={
            # Container Port : Host Port
            '80': 8010 + numberOfWebServers
        })

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
        # Trigger condition checker for scale condition, OutPut: [y, n, n, y, n ...] for WebServers
        cpuTriggerConditionChecker = []
        memoryUSageTriggerConditionChecker = []
        inputTrafficTriggerConditionChecker = []
        outPutTrafficTriggerConditionChecker = []
        busyThreadsCountTriggerConditionChecker = []

        # Array of running web servers object
        webServers = []
        # shouldScale = False

        # Read the log files and create the  webServer object
        # for logFile in getLogsFilesName(WebServersLogsFolderPath):
        time.sleep(1)
        readAllContainerStats = False
        while not readAllContainerStats:
            arrayOfAllContainerThresholdHintStats = []
            for logFile in range(numberOfWebServers):
                fileReader = FileReader(WebServersLogsFolderPath + "app" + str(logFile + 1))
                temp = []
                # {'Cpu': '0.01', 'Memory': '12.58MiB', 'MemoryUsage': '0.21', 'InputTraffic': '1.82kB', 'OutPutTraffic': '9.1kB', 'BusyThreadsCount': '1'}
                stats = fileReader.readNumberOfLines(6)
                for data in stats:
                    temp.append(((data.split())[1]).replace("%", ""))
                # compare the read status with trigger condition array
                if len(temp) > 4:
                    if float(temp[0]) > 20:
                        arrayOfAllContainerThresholdHintStats.append("1")
                    elif float(temp[0]) < 15:
                        arrayOfAllContainerThresholdHintStats.append("0")
                if len(arrayOfAllContainerThresholdHintStats) == numberOfWebServers:
                    readAllContainerStats = True
                else:
                    readAllContainerStats = False


        if not checkMajority(arrayOfAllContainerThresholdHintStats, numberOfWebServers) and numberOfWebServers > 1:
            print(
                "########################################################################################################################")
            print(
                "########################################################################################################################")
            dockerUtils.removeCountainer("app" + str(numberOfWebServers))
            logging.info("Web Server " + ("app" + str(numberOfWebServers)) + " has been removed")
            numberOfWebServers = numberOfWebServers - 1
            logging.info("Modify and Restart HaProxy")
            # Edit the haProxy config file and remove the destination
            haproxyConfigModifier.removeTheNewestDestination()
            # Prevent the removal of "\n" at the end of the config file
            haproxyConfigModifier.addNewDestination("\n")
            # Restarting the HaProxy service
            osCommandRunner.executeCommand("service haproxy restart")
            time.sleep(2)
            osCommandRunner.executeCommand("service haproxy status | grep Active")


        elif checkMajority(arrayOfAllContainerThresholdHintStats, numberOfWebServers):
            numberOfWebServers = numberOfWebServers + 1
            webServerContainre = dockerUtils.createContainer("httpd_final", "app" + str(numberOfWebServers), 1000000000,
                                                             command='', ports={
                    # Container Port : Host Port
                    '80': 8010 + numberOfWebServers
                })
            logging.info("Web Server " + ("app" + str(numberOfWebServers)) + " has been added")
            logging.info("Modify and Restart HaProxy")
            # Edit the haProxy config file and add the destination
            # Destination string needs to have 4 spaces at the beginning, like below
            #    server web1.example.com  192.168.1.101:80
            haproxyConfigModifier.addNewDestination(
                "    server " + ("app" + str(numberOfWebServers)) + "  " + ServerIpAddress + ':' + str(
                    8010 + numberOfWebServers) + "\n")
            # Restarting the HaProxy service
            osCommandRunner.executeCommand("service haproxy restart")
            time.sleep(2)
            osCommandRunner.executeCommand("service haproxy status | grep Active")


    # mainWebServerLogReader = FileReader("/Users/amir/Desktop/baka")
    # temp = {}
    # # {'Cpu': '0.01', 'Memory': '12.58MiB', 'MemoryUsage': '0.21', 'InputTraffic': '1.82kB', 'OutPutTraffic': '9.1kB', 'BusyThreadsCount': '1'}
    # for data in mainWebServerLogReader.readNumberOfLines(6):
    #     temp[(data.split())[0]] = ((data.split())[1]).replace("%", "")
    # print(temp)




# if len(temp) == 6:
#     webServers.append(
#         WebServer(cpu=temp[0], memory=temp[1], memoryUsage=temp[2], inputTraffic=temp[3],
#                   outPutTraffic=temp[4], busyThreadsCount=temp[5]))
# else:
#     logging.error("Web server " + logFile + " status is not correct")