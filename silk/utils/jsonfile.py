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

import os
import json

CONF_PATH = '/opt/openthread_test/'


class JsonFile:

    def __init__(self):
        pass

    @staticmethod
    def load_json_file(file_path):
        try:
            with open(file_path, 'r') as jfile:

                json_data = jfile.read()
                json_line = json.loads(json_data)

                return json_line
        except Exception:
            emsg = "Failed to load JSON file: %s" % (file_path)
            print(emsg)

    @staticmethod
    def save_json_file(file_path, json_line):
        if not os.path.isfile(file_path):
            return
        try:
            json_data = json.dumps(json_line, sort_keys=True, indent=2)
        except Exception:
            print ("Failed to save json file: %s" % (file_path))
            return

        with open(file_path, 'w') as jfile:
            jfile.write(json_data)

    @staticmethod
    def get_conf_file(conf_file_name):
        conf_path = CONF_PATH
        return conf_path + conf_file_name

    @staticmethod
    def get_json(conf_file):
        file_path = JsonFile.get_conf_file(conf_file)
        return JsonFile.load_json_file(file_path)

    @staticmethod
    def set_json(json_line, conf_file):
        file_path = JsonFile.get_conf_file(conf_file)
        JsonFile.save_json_file(file_path, json_line)

    @staticmethod
    def is_json_file_existed(conf_file):
        file_path = JsonFile.get_conf_file(conf_file)
        return os.path.isfile(file_path)

