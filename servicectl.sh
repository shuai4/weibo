# /bin/bash

supervisorctl status all |grep $2 |awk '{print $1}' | while read line
do 
    supervisorctl $1 $line
done