BINDIR      := $(shell [ -x ../../mkbootmsg ] && echo ../../ )

MKBOOTMSG    = $(BINDIR)mkbootmsg
BFLAGS       = -O -v -L ../..
INCLUDES     = $(wildcard *.inc)
TRANSLATIONS = $(addsuffix .tr,en $(notdir $(basename $(wildcard po/*.po))))

DEFAULT_LANG =

PIC_COMMON   = back.jpg

FILES_CORE   = init

INST_EXT     = langlist $(TRANSLATIONS) 16x16.fnt $(PIC_COMMON)

FILES_INST   = $(FILES_CORE) $(INST_EXT)

FILES_BOOT   = $(FILES_CORE) langlist $(TRANSLATIONS) 16x16.fnt \
	       $(PIC_COMMON)

FILES_BOOT_EN = $(FILES_CORE) en.tr 16x16.fnt $(PIC_COMMON)

ifdef DEFAULT_LANG
FILES_INST += lang
FILES_BOOT += lang
FILES_BOOT_EN += lang $(DEFAULT_LANG).tr
endif

.PHONY: all themes font clean po

all: themes

boot install: po
	mkdir -p $@

po:
	make -C po

themes: bootdir installdir

bootdir: boot.config boot $(INCLUDES)
	@cp -a po/*.tr boot
	@for i in $(FILES_BOOT) ; do [ -f $$i ] && cp $$i boot ; done ; true
	@echo en >boot/langlist
	$(MKBOOTMSG) $(BFLAGS) -l boot/log -c $< boot/init
ifdef DEFAULT_LANG
	@echo $(DEFAULT_LANG) >boot/lang
	@echo $(DEFAULT_LANG) >>boot/langlist
endif
	@cd boot && echo $(FILES_BOOT_EN) | sed -e "s/ /\n/g" | cpio --quiet -o >message

installdir: install.config install $(INCLUDES)
	@cp -a po/*.tr install
	@for i in $(FILES_INST) ; do [ -f $$i ] && cp $$i install ; done ; true
	$(MKBOOTMSG) $(BFLAGS) -l install/log -c $< install/init
ifdef DEFAULT_LANG
	@echo $(DEFAULT_LANG) >install/lang
endif
	@cd install && echo $(FILES_CORE) | sed -e "s/ /\n/g" | cpio --quiet -o >bootlogo
	@tar -C install -czf install/bootlogo.tar.gz bootlogo $(INST_EXT)

font:
	cat po/*.po >tmp.txt
	getx11font -v -l 18 -p 2,4 \
	-c ISO-8859-15 -c ISO-8859-2 -c koi8-r \
	`./keymapchars keytables.inc` \
	-t tmp.txt \
	-t install/log -t boot/log \
	-t langlist -t dia_lang.inc \
	-f -gnu-unifont-medium-r-normal--16-160-75-75-c-80-iso10646-1 \
	--fsize 16,5 \
	16x16.fnt >16x16.fnt.log
	rm -f tmp.txt

clean:
	make -C po clean
	rm -f bootdir installdir *~ *.log
	rm -rf boot install

