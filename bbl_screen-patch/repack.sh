ZIP=`ls bbl_screen*.zip --sort=size -1 | head -n1`
UNPACKDIR=printer_ui/
set -x

if [ -d $UNPACKDIR ]; then
	echo "skipping unpacking into $UNPACKDIR, move it out of the way if you want me to do that"
else
	mkdir -p $UNPACKDIR
	unzip -d $UNPACKDIR $ZIP 
	echo '<!DOCTYPE RCC><RCC version="1.0"><qresource>' > $UNPACKDIR/repack.qrc
	find $UNPACKDIR -type f | grep -v "repack.qrc" | sed -e "s#$UNPACKDIR\(.*\)#<file>\1</file>#" >> $UNPACKDIR/repack.qrc
	echo '</qresource></RCC>' >> $UNPACKDIR/repack.qrc
fi
rcc $UNPACKDIR/repack.qrc  --format-version=2 > unpacked.cpp
arm-linux-gnueabihf-gcc -shared -o interpose.so interpose.c unpacked.cpp -fPIC -ldl  -nolibc