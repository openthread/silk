#!/usr/bin/env python
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

# Roles supported in openthread
ROLES = {
            "router": 2,
            "end-node": 3,
            "sleepy-end-device": 4,
            2: "router",
            3: "end-node",
            4: "sleepy-end-device"
        }

RolesList = [2, 3, 4]
LegacyRoles = [0x82, 6]
