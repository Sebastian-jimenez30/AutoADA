#!/usr/bin/ksh
cd /opt/osi/osi_cust/data/pythondir/dbdump
dbdump -c -e -R 10 4 > SCADA_STA.csv
dbdump -c -e -R 10 5 > SCADA_ANG.csv
dbdump -c -e -R 10 6 > SCADA_ACC.csv
dbdump -c -e -R 10 7 > SCADA_STP.csv
dbdump -c -e -R 32 10 > FEP_SCAN.csv
dbdump -c -e -R 32 20 > FEP_CTRL.csv
dbdump -c -e -R 36 15 > ICCP_EXP.csv
dbdump -c -e -R 36 16 > ICCP_IMP.csv
dbdump -c -e -R 8 11 > ONET_BRANCH.csv
dbdump -c -e -R 8 7 > ONET_BREAKER.csv
dbdump -c -e -R 8 50 > ONET_GDEV.csv
dbdump -c -e -R 8 9 > ONET_GEN.csv
dbdump -c -e -R 8 8 > ONET_LOAD.csv
dbdump -c -e -R 8 6 > ONET_SBUS.csv
dbdump -c -e -R 8 10 > ONET_SHUNT.csv
dbdump -c -e -R 8 12 > ONET_XFORM.csv
dbdump -c -e -R 46 1 > CALC_GISA.csv
exit 0
