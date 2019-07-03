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

TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

# Hex
REGEX_HEX = "[\dA-Fa-f]"

# e.g 18:B4:30:00:00:6D:52:C0
MAC_REGEX_CHUNK = "%s%s" % (REGEX_HEX, REGEX_HEX)
MAC_REGEX = "((%s:){7}(%s))" % (MAC_REGEX_CHUNK, MAC_REGEX_CHUNK)
