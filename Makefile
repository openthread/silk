#
#    Copyright (c) 2016-2019, The OpenThread Authors.
#    All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#

PYTHON ?= python
PYTHON_VERSION ?= $(shell $(PYTHON) -c "import sys; sys.stdout.write(sys.version[:3])")
SUDO ?= sudo
MAKE ?= make
PEP8_LINT ?= pep8
PEP8_LINT_ARGS ?= --max-line-length=132

all: install

check-prerequisites:
	@if `which dpkg >& /dev/null`; then \
		echo -n "Checking for python-pip..."; \
		if `dpkg -s python-pip >& /dev/null`; then \
			echo "ok"; \
		else \
			echo "The package python-pip is required and is not installed. Please run 'sudo apt-get install python-pip' to install it."; \
			exit 1; \
		fi; \
		echo -n "Checking for expect..."; \
		if `dpkg -s expect >& /dev/null`; then \
			echo "ok"; \
		else \
			echo "The package expect is required and is not installed. Please run 'sudo apt-get install expect' to install it."; \
			exit 1; \
		fi; \
		echo -n "Checking for figlet..."; \
		if `dpkg -s figlet >& /dev/null`; then \
			echo "ok"; \
		else \
			echo "The package figlet is required and is not installed. Please run 'sudo apt-get install figlet' to install it."; \
			exit 1; \
		fi; \
		echo -n "Checking for graphviz..."; \
		if `dpkg -s graphviz >& /dev/null`; then \
			echo "ok"; \
		else \
			echo "The package graphviz is required and is not installed. Please run 'sudo apt-get install graphviz' to install it."; \
			exit 1; \
		fi; \
	fi

# If TESTBED_PATH defined, install or uninstall the specific, $TESTBED_PATH,
# location of the TESTBED package. If TESTBED_PATH is not defined, by default
# install TESTBED into Python's system with install-system.

install-cluster: check-prerequisites
ifeq ($(TESTBED_PATH),)
	$(MAKE) install-system
else
	$(MAKE) install-path
endif

uninstall-cluster:
ifeq ($(TESTBED_PATH),)
	$(MAKE) uninstall-system
else
	$(MAKE) uninstall-path
endif

# If TESTBED_PATH defined, install or uninstall the specific, $TESTBED_PATH,
# location of the TESTBED package. If TESTBED_PATH is not defined, by default
# install TESTBED into Python's system with install-system.

install: check-prerequisites
ifeq ($(TESTBED_PATH),)
	$(MAKE) install-system
	$(MAKE) link
else
	$(MAKE) install-path
endif

uninstall:
ifeq ($(TESTBED_PATH),)
	$(MAKE) uninstall-system
else
	$(MAKE) uninstall-path
endif

# Install TESTBED into Python's shared library in a developed version.
# Develop version instead of copying TESTBED package into /usr/local/lib ...,
# creates a reference to the TESTBED source directory. This allows a developer
# to modify TESTBED modules and test them without reinstalling TESTBED.

install-develop: check-prerequisites
	# Installing TESTBED for development
	$(SUDO) $(PYTHON) setup.py develop
	$(MAKE) link

uninstall-develop:
	$(SUDO) $(PYTHON) setup.py develop --uninstall
	$(MAKE) unlink
	$(MAKE) clean

# Install TESTBED into a user's home directory (~/.local). This allows a user
# to install TESTBED without requiring root privilages. The installed TESTBED
# package is only visible to the user that installed it; other same system's
# users cannot find TESTBED package unless they install it as well.

install-user: check-prerequisites
	# Installing TESTBED into user home directory
	$(PYTHON) setup.py install --user
	@echo
	@echo "TESTBED package installed into users ~/.local/lib/*"
	@echo "TESTBED shell scripts are not installed into the system."
	@echo "To use TESTBED shell scripts, add TESTBED bin/ into PATH."
	@echo

uninstall-user:
	rm -rf ~/.local/lib/python$(PYTHON_VERSION)/site-packages/TESTBED*.egg

# Install TESTBED into Python system-wide distribution packages. This installation
# requires root privilages. After installation every user in the system can
# use TESTBED package.

install-system: check-prerequisites
	# Installing TESTBED
	$(SUDO) $(PYTHON) setup.py install

uninstall-system:
	$(MAKE) unlink
	$(MAKE) clean
	$(SUDO) rm -rf /usr/local/lib/python$(PYTHON_VERSION)/dist-packages/TESTBED-*egg

# Install TESTBED package into non-standard location. Because the installed package
# location is not know to Python, the package path must be passed to PYTHON through
# PYTHONPATH environment variable. To install TESTBED under /some/path run:
# make TESTBED_PATH=/some/path
# This will create /some/path/lib/pythonX.X/site-packages location and install
# the TESTBED package over there.

install-path: check-prerequisites
ifeq ($(TESTBED_PATH),)
	@echo Variable TESTBED_PATH not set. && false
endif
	mkdir -p $(TESTBED_PATH)/lib/python$(PYTHON_VERSION)/site-packages/; \
	export PYTHONPATH="$(TESTBED_PATH)/lib/python$(PYTHON_VERSION)/site-packages/" ;\
	$(PYTHON) setup.py install --prefix=$(TESTBED_PATH)
	@echo
	@echo "Using custom path for a Python package is unusual."
	@echo "Remember to update PYTHONPATH for every environment that will use this package, thus run"
	@echo "export PYTHONPATH=$$PYTHONPATH:"$(TESTBED_PATH)/lib/python$(PYTHON_VERSION)/site-packages/""
	@echo

uninstall-path:
ifeq ($(TESTBED_PATH),)
	@echo Variable TESTBED_PATH not set. && false
endif
	rm -rf $(TESTBED_PATH)

distribution-build: clean
	# creates a built distribution
	$(PYTHON) setup.py bdist

distribution-source: clean
	# creates a source distribution
	$(PYTHON) setup.py sdist

distribution: distribution-build distribution-source

release: distribution

link:
	# $(MAKE) link -C src/bin

unlink:
	# $(MAKE) unlink -C src/bin

clean:
	$(SUDO) rm -rf *.egg*
	$(SUDO) rm -rf *.pyc*
	$(SUDO) rm -rf dist
	$(SUDO) rm -rf build

pretty-check:
	$(PEP8_LINT) $(PEP8_LINT_ARGS) .
