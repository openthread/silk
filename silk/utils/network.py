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
"""Network utilities.
"""

import socket


def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            # server does not need to be reachable
            sock.connect(("8.8.8.8", 80))
            local_host = sock.getsockname()[0]
        except Exception:
            # exception raised if interface does not exist
            local_host = "127.0.0.1"
    return local_host
