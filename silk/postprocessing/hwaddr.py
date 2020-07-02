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


def hwaddr_plain_add_colons(plain_hwaddr):
    eui = ""
    for (i,c) in enumerate(plain_hwaddr):

        c = int(c, 16)
        if i == 1:
            c = c & ~2

        eui = eui + "%x" % c
        if (i + 1) % 2 == 0 and i != len(plain_hwaddr) - 1:
            eui = eui + ':'

    eui = eui.upper()
    return eui.upper()


def hwaddr_from_iid(iid):
    hwaddr = None

    hwaddr_plain = iid.replace(':','')
    hwaddr = hwaddr_plain_add_colons(hwaddr_plain)

    return hwaddr.upper()
