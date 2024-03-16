TGZ_CONTENTS = x1plus/kexec_ui.so x1plus/launch.sh

setup.tgz: $(TGZ_CONTENTS)
	rm -f $@
	tar czvf $@ --dereference $(TGZ_CONTENTS)
