#!/usr/bin/ksh

Host=`hostname`
server=$1
DB=$2
mongoexport --host $server --port=27030 --collection=groups --db=$DB --out=/opt/osi/osi_cust/data/pythondir/hsh/groups.json --ssl --sslCAFile $OSI/sys/rc/ssl/ca-chain.cert.pem --sslPEMKeyFile $OSI/sys/rc/ssl/${Host}.pem --authenticationDatabase admin -u osiadmin -p GJgSHWxVHmYqbg --query "{"uid": /^SCADA\//}"
mongoexport --host $server --port=27030 --collection=lookup_tables --db=$DB --out=/opt/osi/osi_cust/data/pythondir/hsh/lookup_tables.json --ssl --sslCAFile $OSI/sys/rc/ssl/ca-chain.cert.pem --sslPEMKeyFile $OSI/sys/rc/ssl/${Host}.pem --authenticationDatabase admin -u osiadmin -p GJgSHWxVHmYqbg --query "{ 'table_name': 'Tabla1', 'deleted': false }"
exit 0