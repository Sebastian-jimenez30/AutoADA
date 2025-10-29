#!/usr/bin/ksh
cd /opt/osi/osi_cust/data/pythondir/dbdump
dbdump -c -e -R 10 4 > SCADA_STATUS.csv
dbdump -c -e -R 10 5 > SCADA_ANALOGS.csv
dbdump -c -e -R 10 6 > SCADA_ACCUMULATOR.csv
dbdump -c -e -R 10 7 > SCADA_SETPOINTS.csv
dbdump -c -e -R 32 10 > FEP_SCAN.csv
dbdump -c -e -R 32 20 > FEP_CONTROLS.csv
dbdump -c -e -R 36 15 > ICCP_EXPORT.csv
dbdump -c -e -R 36 16 > ICCP_IMPORT.csv
dbdump -c -e -R 8 11 > OPENNET_BRANCH.csv
dbdump -c -e -R 8 7 > OPENNET_BREAKER.csv
dbdump -c -e -R 8 50 > OPENNET_GROUND.csv
dbdump -c -e -R 8 9 > OPENNET_GENER.csv
dbdump -c -e -R 8 8 > OPENNET_LOAD.csv
dbdump -c -e -R 8 6 > OPENNET_SBUS.csv
dbdump -c -e -R 8 10 > OPENNET_SHUNT.csv
dbdump -c -e -R 8 12 > OPENNET_XFORM.csv
dbdump -c -e -R 46 1 > CALC_GISA.csv
dbdump -c -e -R 140 3 > OPENCALC_FORMULAS.csv
exit 0
