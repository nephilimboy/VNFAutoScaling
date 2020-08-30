#!/usr/bin/env bash

# Commands
# Running Apache web server(httpd) -> sudo docker run -dit --name app1 -p 8080:80 httpd_final


# Modify these parameters before running
DIR=/home/amir/container_autoLog/
ContainerNamePrefix=app

# Clean The Log Folder
rm -rf $DIR*

# Main Loop
while :
do
    # get all running docker container names
    containers=$(sudo docker ps | awk '{if(NR>1) print $NF}')
    # get all log files and delete the ones that its container does not exist
    # (log file's name is always equal to container's name)
    for fileName in $(ls $DIR)
    do
        isContainerExist=false
        for container in $containers
        do
            if [ "$container" == "$fileName" ]; then
                isContainerExist=true
            fi
            temp=history_$container
            if [ "$temp" == "$fileName" ]; then
                isContainerExist=true
            fi
        done
        if [ "$isContainerExist" == false ] ; then
            rm -rf $DIR$fileName
        fi
    done

    # loop through all containers
	for container in $containers
    do
        # Check whether Container's name start with specific prefix or not
        if [[ $ContainerNamePrefix =~ $container* ]] ; then
            # Out put would be like below
                #CONTAINER ID        NAME                CPU %               MEM USAGE / LIMIT     MEM %               NET I/O             BLOCK I/O           PIDS
                #e230251af571        app1                0.01%               14.55MiB / 5.752GiB   0.25%               3.09kB / 10.1kB     7.2MB / 0B          82
            containerStats=$(docker stats --no-stream | grep $container)
            # Cpu
            cpu=$(echo $containerStats | awk '{print $3}')
            # Memory
            memory=$(echo $containerStats | awk '{print $4}')
            # Memory Usage
            memoryUsage=$(echo $containerStats | awk '{print $7}')
            # Input traffic
            inputTraffic=$(echo $containerStats | awk '{print $8}')
            # Output traffic
            outputTraffic=$(echo $containerStats | awk '{print $10}')

            # Get container's IP address
            containerIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $container)
            # Get httpd status web GUI and extract the "Thread" column useful data
            # Out put would be like below
                #   Slot PID Stopping   Connections    Threads      Async connections
                #                     total accepting busy idle writing keep-alive closing
                #   0    6   no       0     yes       1    24   0       0          0
                #   1    7   no       0     yes       0    25   0       0          0
                #   2    8   no       0     yes       0    25   0       0          0
                #   Sum  3   0        0               1    74   0       0          0
            busyThreadsCount=$(lynx --dump http://$containerIP/server-status | grep Sum |  head -1 | awk '{print $5}')

            # Saving extracted data to files (current data file with ">" command & history available file with ">>" command)
            # Creating current log file
            echo  "Cpu $cpu" > $DIR$container
            echo "Memory $memory" >> $DIR$container
            echo "MemoryUsage $memoryUsage" >> $DIR$container
            echo "InputTraffic $inputTraffic" >> $DIR$container
            echo "OutPutTraffic $outputTraffic" >> $DIR$container
            echo "BusyThreadsCount $busyThreadsCount" >> $DIR$container

            # Creating history log file (will be used for presenting data and graphing)
            historyFileName=history_$container
            date=$(date)
            echo "---------------------------------------- $date" >> $DIR$historyFileName
            echo  "Cpu $cpu" >> $DIR$historyFileName
            echo "Memory $memory" >> $DIR$historyFileName
            echo "MemoryUsage $memoryUsage" >> $DIR$historyFileName
            echo "InputTraffic $inputTraffic" >> $DIR$historyFileName
            echo "OutPutTraffic $outputTraffic" >> $DIR$historyFileName
            echo "BusyThreadsCount $busyThreadsCount" >> $DIR$historyFileName

        fi
    done
	#sleep 1
done



