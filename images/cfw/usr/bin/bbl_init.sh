#!/bin/sh
REMOUNT_OPT_ORG=`mount | grep "root" | awk '{print $6}'`
OPT=${REMOUNT_OPT_ORG:1:2}

c_cnt=5
a_cnt=3

TSL_DIR="/tmp/device"
SSL_DIR="/usr/etc/ssl"
CERT_DIR=$SSL_DIR"/certs"
CERT=$CERT_DIR"/ssl-cert-bbl.pem"
KEY_DIR=$SSL_DIR"/private"
KEY=$KEY_DIR"/ssl-priv-bbl.pem"
CTPD=$SSL_DIR"/.certprepare_done"

if [ -f /oem/device/mp_state ]; then
    mp_state=`cat /oem/device/mp_state`
else
    mp_state=""
fi
MPSTATE_R=`bbl_mpstate`

#prepare ssl certificate and keys refer to secure storage
while [ $c_cnt -ge 0 ] ; do
    if [ ! -f $CERT -o ! -f $KEY -o ! -f $CTPD ]; then
        mount -o remount,rw /
        mkdir -p $CERT_DIR $KEY_DIR $TSL_DIR && \
        bbl_certprepare 15 && mv $TSL_DIR/ssl-priv-bbl.pem $KEY && \
        bbl_certprepare 16 && mv $TSL_DIR/ssl-cert-bbl.pem $CERT && \
        touch $CTPD
        mount -o remount,$OPT /
        sync
    else
        break
    fi
    c_cnt=$((c_cnt - 1))

    if [ $c_cnt -gt 0 ]; then
        sleep 1
    fi
done

#To be compatible with legacy isstaue devices
if [ ! -f $CERT -o ! -f $KEY -o ! -f $CTPD ]; then
    mount -o remount,rw /
    cp /config/keys/PUAK $KEY && cp /config/keys/PUCT $CERT && touch $CTPD
    mount -o remount,$OPT /
    sync
fi

#prepare access code
while [ $a_cnt -ge 0 ] ; do
    passwd_attr=`cat /etc/shadow | grep bblp | awk -F: '{print $3}'`
    if [ $a_cnt -gt 0 ]; then
        sleep 1
    fi

    if [ x$MPSTATE_R == x"uninitialized" ]; then
        if [ x"engineer" = x$mp_state ]; then
            /usr/bin/sec_access_token.sh eng && break;
        else
            if [ ! -f /config/device/access_token ]; then
                    /usr/bin/sec_access_token.sh
            else
                if [ -z "$passwd_attr" ]; then
                    /usr/bin/sec_access_token.sh reconf
                else
                    break
                fi
            fi
        fi
    else
        if [ x"engineer" = x$MPSTATE_R ]; then
            /usr/bin/sec_access_token.sh eng && break;
        else
            if [ ! -f /config/device/access_token ]; then
                    /usr/bin/sec_access_token.sh
            else
                if [ -z "$passwd_attr" ]; then
                    /usr/bin/sec_access_token.sh reconf
                else
                    break
                fi
            fi
        fi
    fi
    a_cnt=$((a_cnt - 1))
done

# tune cpu priority to access bus
# io -4 0xfe830008 0x202

# irq cpu bind
irq_affinity.sh &

#collect crash dump log
crash_dump.sh &

# tune linux memory zone watermark
echo 8192 > /proc/sys/vm/min_free_kbytes
echo 16384 > /proc/sys/vm/extra_free_kbytes

#set max socket buffer size to 1.5MByte
sysctl -w net.core.wmem_max=1572864

export enable_encoder_debug=0

# ispp using fbc420 mode to save ddr bandwidth
echo 1 > /sys/module/video_rkispp/parameters/mode

echo 1 > /sys/class/rfkill/rfkill1/state

# set sys led on by default
echo 255 > /sys/devices/platform/gpio-leds/leds/sys_led/brightness


# run bambu_lab_fixme.bin in sdcard
# wait 3 seconds to make sure that sdcard is mounted
sleep 3 && /usr/bin/bbl_fixme &
