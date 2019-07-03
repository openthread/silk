#!/usr/bin/env bash
#
# Copyright 2019 Google LLC
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
#
#    Description:
#      This file installs all needed dependencies and toolchains needed for
#      example compilation and programming.
#

# Establish some key directories

srcdir=`dirname ${0}`
abs_srcdir=`pwd`
abs_top_srcdir="${abs_srcdir}"

link_sh_to_bash()
{
    sudo mv /bin/sh /bin/sh.orig
    sudo ln -s /bin/bash /bin/sh
}

install_packages_apt()
{
    # apt update and install dependencies
#    sudo apt-get update
    sudo apt-get install python-pip expect figlet graphviz python-tk -y
}

install_packages_pip()
{
    # pip install dependencies
    sudo python2.7 -m pip install pip --upgrade
    sudo python2.7 -m pip install -r requirements.txt
}

install_packages()
{
    install_packages_apt
    install_packages_pip
    link_sh_to_bash
}

main()
{
    install_packages
}

main
