# Copyright(c) 2016-2020 Jonathan Poland
VERSION = 0.8
UI := $(shell find WIZARD_UIFILES -type f -print)
SCRIPTS := $(shell find scripts -type f -print)
PACKAGE_FILES := $(shell ./package.sh)

all: package.tgz Medio-${VERSION}.spk

package.tgz: ${PACKAGE_FILES}
	# Use python itself as a basic syntax linter
	python -c "from package import medio"
	@echo 'Remaking package tarball'
	@tar czf package.tgz -C package $(subst package,.,${PACKAGE_FILES})

Medio-${VERSION}.spk: INFO PACKAGE_ICON.PNG LICENSE ${UI} ${SCRIPTS} package.tgz
	sed -i 's/version=.*/version="${VERSION}"/g' INFO
	tar cf Medio-${VERSION}.spk INFO PACKAGE_ICON.PNG LICENSE WIZARD_UIFILES scripts package.tgz

clean:
	rm -f package.tgz Medio-*.spk package/*.pyc
