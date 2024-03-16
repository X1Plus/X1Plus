CFLAGS ?= -O2 -Wall

.PHONY: all clean

all: redir.so

%.so: %.c
	$(CC) $(CFLAGS) -shared -fpic -o $@ $<

clean:
	rm -f redir.so
