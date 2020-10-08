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
"""Directory path utility.
"""

import inspect
import os
import time

WAIT_TIME = 5


class DirectoryPath(object):

    @staticmethod
    def get_dir(path, folder_name="silk"):
        file_abs_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        timeout = time.time() + WAIT_TIME
        while True:
            if time.time() > timeout:
                raise RuntimeError(f"folder_name {folder_name} not found")
            if file_abs_path.split("/")[-1] != folder_name:
                file_abs_path = os.path.dirname(file_abs_path)
                time.sleep(1)
            else:
                dir_path = file_abs_path + "/" + path + "/"
                return dir_path
