#
#    Copyright (c) 2016-2019, The OpenThread Authors.
#    All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
import os
from setuptools import find_packages, setup

here = os.path.abspath(os.path.dirname(__file__))

setup(name="testbed",

      version="0.0.1",

      description="Openthread testbed",

      # long_description=long_description,

      author="Google Nest, Inc.",

      platforms=["Linux"],

      classifiers=[
          "Development Status :: 5 - Production/Stable",

          "License :: OSI Approved :: Apache Software License",

          "Intended Audience :: Developers",
          "Intended Audience :: Education",

          "Operating System :: POSIX :: Linux",

          "Topic :: Software Development :: Testing",
          "Topic :: Software Development :: Embedded Systems",
          "Topic :: System :: Emulators",
          "Topic :: System :: Networking"
      ],

      license="Apache",

      packages=find_packages(),

      package_data={'src': ['config/clusters.confcx',
                            'shell/build_nrf52840.sh',
                            'shell/nrfjprog.sh',
                            'shell/flash_wpantund.sh',
                            'shell/shell_wpanctl_cmd.sh',
                            'shell/git_pull_wpantund.sh',
                            'shell/shell_scp.sh']},
      )
