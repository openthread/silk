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

import multiprocessing
import time


class MultipleProcess(object):

    @staticmethod
    def process(func, *args):
        processes = []
        new_args = ()
        for node in args[0]:
            new_args = [args[0][node]] + [arg for arg in args[1:]]
            p = multiprocessing.Process(target=func, args=(new_args))
            processes.append(p)
            if len(processes) == 4:
                is_alive = True
                for each in processes:
                    each.start()
                begin = time.time()
                while is_alive:
                    is_alive = False
                    for each in processes:
                        is_alive = is_alive or each.is_alive()
                    timeout = (time.time() - begin)
                    if timeout >= 5:
                        break
                processes = []
        for each in processes:
            each.start()
        is_alive = True
        while is_alive:
            is_alive = False
            for each in processes:
                is_alive = is_alive or each.is_alive()
