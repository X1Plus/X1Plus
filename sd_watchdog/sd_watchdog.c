#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <linux/kd.h>
#include <sys/ioctl.h>
#include <linux/vt.h>
#include <sys/mman.h>
#include <string.h>
#include <sys/reboot.h>
#include <syslog.h>
#include <stdlib.h>
#include <linux/tiocl.h>

static char *msg =
"\033[48;5;196m" // red background
"\033[38;5;255m" // white text
"\033[2J\033[H"
"         ██╗    ██╗ █████╗ ██████╗ ███╗   ██╗██╗███╗   ██╗ ██████╗ ██╗       \n"
"         ██║    ██║██╔══██╗██╔══██╗████╗  ██║██║████╗  ██║██╔════╝ ██║       \n"
"         ██║ █╗ ██║███████║██████╔╝██╔██╗ ██║██║██╔██╗ ██║██║  ███╗██║       \n"
"         ██║███╗██║██╔══██║██╔══██╗██║╚██╗██║██║██║╚██╗██║██║   ██║╚═╝       \n"
"         ╚███╔███╔╝██║  ██║██║  ██║██║ ╚████║██║██║ ╚████║╚██████╔╝██╗       \n"
"          ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝       \n"
"             ███████╗██████╗      ██████╗ █████╗ ██████╗ ██████╗             \n"
"             ██╔════╝██╔══██╗    ██╔════╝██╔══██╗██╔══██╗██╔══██╗            \n"
"             ███████╗██║  ██║    ██║     ███████║██████╔╝██║  ██║            \n"
"             ╚════██║██║  ██║    ██║     ██╔══██║██╔══██╗██║  ██║            \n"
"             ███████║██████╔╝    ╚██████╗██║  ██║██║  ██║██████╔╝            \n"
"             ╚══════╝╚═════╝      ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝             \n"
"         ██████╗ ███████╗███╗   ███╗ ██████╗ ██╗   ██╗███████╗██████╗        \n"
"         ██╔══██╗██╔════╝████╗ ████║██╔═══██╗██║   ██║██╔════╝██╔══██╗       \n"
"         ██████╔╝█████╗  ██╔████╔██║██║   ██║██║   ██║█████╗  ██║  ██║       \n"
"         ██╔══██╗██╔══╝  ██║╚██╔╝██║██║   ██║╚██╗ ██╔╝██╔══╝  ██║  ██║       \n"
"         ██║  ██║███████╗██║ ╚═╝ ██║╚██████╔╝ ╚████╔╝ ███████╗██████╔╝       \n"
"         ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝ ╚═════╝   ╚═══╝  ╚══════╝╚═════╝        \n"
"\033[38;5;0m" // black text
"  Because the X1Plus firmware is running from the SD card it is \033[38;5;226mnever\033[38;5;0m safe to\n"
"  remove the SD card while the X1Plus firmware is running. Always power down \n"
"  your printer before removing the SD card.                                  \n"
"               Printer will automatically reboot in 10 seconds.              "
;

void do_warning() {
	int fd;
	int console = 1; // First virtual console (text console)

	char arg[2];

//https://www.asciiart.eu/text-to-ascii-art

	// Open the console device file
	fd = open("/dev/tty0", O_RDWR);
	if (fd == -1) {
		perror("open");
		return;
	}

	// Switch to the console
	if (ioctl(fd, KDSETMODE, KD_GRAPHICS) == -1) {
		perror("KDSETMODE");
	}
	if (ioctl(fd, VT_ACTIVATE, console) == -1) {
		perror("VT_ACTIVATE");
	}
	console = 7;
	if (ioctl(fd, VT_ACTIVATE, console) == -1) {
		perror("VT_ACTIVATE");
	}
	if (ioctl(fd, KDSETMODE, KD_TEXT) == -1) {
		perror("KDSETMODE");
	}

	//display banner
	if (write(fd, msg, strlen(msg)) == -1) {
		perror("write");
    }

	//unblank screen if it is blanked
//	arg[0] = TIOCL_UNBLANKSCREEN;
//	if (ioctl(fd, TIOCLINUX, arg ) == -1) {
//		perror("TIOCL_UNBLANKSCREEN");
//	}
//	arg[0] = TIOCL_SETVESABLANK;
//	arg[1] = 0; //disable screen blanking
//	if (ioctl(fd, TIOCLINUX, arg ) == -1) {
//		perror("TIOCL_UNBLANKSCREEN");
//	}

	close(fd);
}

void do_backlight( void ) {
	int fd;

	char backlight_on[] = "255";

	fd = open( "/sys/devices/platform/backlight/backlight/backlight/brightness", O_RDWR );
	if ( fd == -1 ) {
		perror("Error opening file");
		return;
	}
	write( fd, backlight_on, strlen( backlight_on ) );

	close( fd );
}

void do_reboot( void ) {
	sleep(10);

	reboot( RB_AUTOBOOT );
}

#define SDCID_MAX 32
char sdcid_1[SDCID_MAX+1];
char sdcid_2[SDCID_MAX+1];
int sdcid_init = 0;

int getSDCID( void ) {
	int result = 0;
	int file;

	file = open( "/sys/class/block/mmcblk2/device/cid", O_RDONLY );
	if ( file == -1 ) {
		perror("Error opening file");
		return 0;
	}

	if( sdcid_init == 0 ) {
		read( file, sdcid_1, SDCID_MAX );
		sdcid_init = 1;
		result = 1;
	} else {
		read( file, sdcid_2, SDCID_MAX );
		if ( memcmp( sdcid_1, sdcid_2, SDCID_MAX ) != 0 ) {
			result = 0;
		} else {
			result = 1;
		}
	}

	close( file );

	return result;
}

#define MODEL_MAX 128
char model[MODEL_MAX+1];

int sysStillExists() {
	int file;
	int result = 0;

	memset( model, 0, sizeof( model ) );

	file = open( "/sys/firmware/devicetree/base/model", O_RDONLY );
	if ( file == -1 ) {
		perror("Error opening file");
		return 0;
	}

	read( file, model, MODEL_MAX );
	if( strlen( model ) > 0 ) {
		return 1;
	}

	return 0;
}

int main() {
	mlockall( MCL_CURRENT );

	if( !getSDCID() ) {
		syslog(LOG_INFO, "[x1p] sd_watchdog failed startup..." );
		exit( 1 );
	}

	syslog(LOG_INFO, "[x1p] sd_watchdog started..." );

	while( 1 ) {
		if( !getSDCID() && sysStillExists() ) {
			do_warning();
			do_backlight();
			do_reboot();
		}
		sleep( 1 );
	}
}
