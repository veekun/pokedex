#!/usr/bin/env bash
set -e

POKEDEX_DIR=${POKEDEX_DIR:-"/project"}

cd ${POKEDEX_DIR}

if [ ! -f "${POKEDEX_DIR}/bin/python" ] || [ ! -f "${POKEDEX_DIR}/bin/pokedex" ] ; then
    echo "Building the bin/pokedex executable ..."
    virtualenv $POKEDEX_DIR --python=python2
    bin/python setup.py develop
fi

case "$1" in
   "") bin/pokedex help
   ;;
   "exec") exec ${@:2}
   ;;
   *) bin/pokedex $@
   ;;
esac
