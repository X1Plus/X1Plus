REGDB=https://mirrors.edge.kernel.org/pub/software/network/wireless-regdb/
rm -f regdb-index.html
wget $REGDB -O regdb-index.html
latest=`grep tar.gz regdb-index.html  | tail -1 | cut -f2 -d\"`
wget $REGDB$latest
pushd images/cfw/lib/firmware
tar -xzvf ../../../../$latest --strip-components=1 --wildcards '*/regulatory.db'
tar -xzvf ../../../../$latest --strip-components=1 --wildcards '*/regulatory.db.p7s'
popd
rm -f regdb-index.html
rm -f $latest
