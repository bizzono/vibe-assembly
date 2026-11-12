# Makefile -- Build libvibeasm (static + shared), examples, and verification checks.
#
# Usage:
#   make                # build build/libvibeasm.a, shared lib, and example binaries
#   make lib            # build static and shared libraries in build/
#   make examples       # build and run example applications
#   make check          # toolchain check + quick verification of installed solutions
#   make test           # run full harness unit & zoo test suite
#   make install        # install headers, libraries, and pkg-config file (PREFIX=/usr/local)
#   make clean          # remove build/ directory

CC       ?= clang
AR       ?= ar
PREFIX   ?= /usr/local
BUILD    := build

UNAME_S  := $(shell uname -s | tr '[:upper:]' '[:lower:]')
UNAME_M  := $(shell uname -m | tr '[:upper:]' '[:lower:]')

ifeq ($(UNAME_M),aarch64)
  ISA := arm64
else ifeq ($(UNAME_M),arm64)
  ISA := arm64
else ifeq ($(UNAME_M),x86_64)
  ISA := x86_64
else ifeq ($(UNAME_M),amd64)
  ISA := x86_64
else
  ISA := $(UNAME_M)
endif

TARGET   := $(ISA)-$(UNAME_S)

ifeq ($(UNAME_S),darwin)
  DYLIB_EXT    := .dylib
  SHARED_FLAGS := -dynamiclib -install_name @rpath/libvibeasm.dylib
else
  DYLIB_EXT    := .so
  SHARED_FLAGS := -shared
endif

CFLAGS   := -O3 -std=c11 -fPIC -Wall -Wextra -Iinclude
TASKS    := base64_encode crc32 mandelbrot nqueens utf8_validate wordcount

# For each task, use the verified assembly in solutions/$(TARGET)/<task>.s if present;
# otherwise fall back to the C reference implementation in tasks/<task>/ref.c.
define task_rule
ifneq ($$(wildcard solutions/$(TARGET)/$(1).s),)
  OBJS += $$(BUILD)/$(1).o
$$(BUILD)/$(1).o: solutions/$(TARGET)/$(1).s | $$(BUILD)
	$$(CC) -fPIC -c $$< -o $$@
else
  OBJS += $$(BUILD)/$(1).o
$$(BUILD)/$(1).o: tasks/$(1)/ref.c | $$(BUILD)
	$$(CC) $$(CFLAGS) -c $$< -o $$@
endif
endef

$(foreach t,$(TASKS),$(eval $(call task_rule,$(t))))

OBJS += $(BUILD)/vibeasm_version.o
$(BUILD)/vibeasm_version.o: include/vibeasm_version.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

STATIC_LIB := $(BUILD)/libvibeasm.a
SHARED_LIB := $(BUILD)/libvibeasm$(DYLIB_EXT)
DEMO_BIN   := $(BUILD)/vibe-demo

.PHONY: all lib examples check test shootout install clean

all: lib $(DEMO_BIN)

$(BUILD):
	mkdir -p $(BUILD)

lib: $(STATIC_LIB) $(SHARED_LIB)

$(STATIC_LIB): $(OBJS)
	$(AR) rcs $@ $(OBJS)

$(SHARED_LIB): $(OBJS)
	$(CC) $(SHARED_FLAGS) $(OBJS) -o $@

$(DEMO_BIN): examples/fast_cli.c $(STATIC_LIB) | $(BUILD)
	$(CC) $(CFLAGS) examples/fast_cli.c $(STATIC_LIB) -o $@

examples: $(DEMO_BIN)
	./$(DEMO_BIN)
ifeq ($(TARGET),arm64-darwin)
	$(CC) examples/standalone_mandelbrot.s -o $(BUILD)/standalone_mandelbrot
	./$(BUILD)/standalone_mandelbrot
endif

check:
	bin/vibeasm doctor
	bin/vibeasm verify --quick

test:
	python3 -m unittest discover -s tests -v

shootout:
	python3 shootout/shootout.py --quick --no-write

install: lib
	install -d "$(DESTDIR)$(PREFIX)/include"
	install -m 0644 include/vibeasm.h "$(DESTDIR)$(PREFIX)/include/vibeasm.h"
	install -d "$(DESTDIR)$(PREFIX)/lib"
	install -m 0644 $(STATIC_LIB) "$(DESTDIR)$(PREFIX)/lib/"
	install -m 0755 $(SHARED_LIB) "$(DESTDIR)$(PREFIX)/lib/"

clean:
	rm -rf $(BUILD)
