#!/bin/sh
# Make doesn't support piping, so this helps make create the
# file list used to make package.tgz
find package -type f -print | egrep -v "(@|\.pyc$)" 
