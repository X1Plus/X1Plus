#include <string>

extern int is_wifi_ready();
extern int is_wried_ready(); /* yes, wried. */

extern int link_is_up(std::string &link) {
	int rv;
	if ((rv = is_wried_ready()) != 0) {
		link = "eth";
		return rv;
	}
	if ((rv = is_wifi_ready()) != 0) {
		link = "wifi";
		return rv;
	}
	link.clear();
	return 0;
}
