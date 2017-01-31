#!/usr/bin/env bash

PREFIX=$HOME/.dappled

if [ ! -e $PREFIX/bin/conda ]; then
    echo "Downloading miniconda..."

    # http://stackoverflow.com/questions/3466166/how-to-check-if-running-in-cygwin-mac-or-linux
    if [ "$(uname)" == "Darwin" ]; then
        # MacOS
        curl -o ~/miniconda.sh https://repo.continuum.io/miniconda/Miniconda2-latest-MacOSX-x86_64.sh

    elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
        # GNU/Linux
        curl -o ~/miniconda.sh https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh

    else
        echo "Platform is not recognized, aborting."
        exit
    fi

    echo "Installing miniconda..."
    bash ~/miniconda.sh -b -p $PREFIX

    echo "Updating path..."
    echo "
# added by Dappled installer
export PATH=\"$PREFIX/bin:\$PATH\"" >> $HOME/.bash_profile

    echo "Installing dappled..."

else
    echo "Updating dappled..."
fi

~/.dappled/bin/conda install -y --no-update-deps dappled -c http://conda.dappled.io

echo
echo "The dappled tool was installed. In a new shell, type:"
echo
echo "  dappled -h"
echo
echo "to display the help text."
echo
