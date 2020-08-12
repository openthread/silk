#!/bin/bash
#
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

OTNS_DIR=${OTNS_DIR:-$HOME/src/otns}
SRC_DIR=`pwd`
SRC_TOP_DIR="${SRC_DIR}"

PYTHON='python3'
PYTHON_CMD="${PYTHON}"

while getopts ':v' 'OPTKEY'; do
    case ${OPTKEY} in
        'v')
            PYTHON_CMD="./env/bin/${PYTHON}"
            ;;
        *) ;;
    esac
done

install_otns()
{
    if ! [[ -d $OTNS_DIR ]]; then
        mkdir -p "$(dirname "$OT_DIR")"
        git clone https://github.com/openthread/ot-ns.git $OTNS_DIR --branch master --depth 1
    fi

    cd "$OTNS_DIR"
    git checkout master
    git pull
    ./script/install-deps
    $PYTHON_CMD pylibs/setup.py install
    ./script/install
    cd -
}

install_python_dependencies()
{
    $PYTHON_CMD -m pip install coverage --upgrade
}

unit_tests()
{  
    $PYTHON_CMD $SRC_TOP_DIR/silk/unit_tests/test_otns.py
}

install_python_dependencies
install_otns
unit_tests
