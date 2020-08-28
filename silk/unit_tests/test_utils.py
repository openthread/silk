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
"""Test utility methods.
"""

import random
import string


def random_string(length: int) -> str:
    """Generate a random string with defined length.

    Args:
        length (int): desired string length.

    Returns:
        str: generated random string.
    """
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))


def commands_almost_equal(command1: str, command2: str, delta: float = 1.0) -> bool:
    """Check if two commands are almost equal.

        Almost equal means we allow numerical parts in the commands to differ by the defined delta.

        Args:
            command1 (str): first command.
            command2 (str): second command.
            delta (float): allowed numerical delta.

        Returns:
            bool: if the two commands are almost equal.
        """
    if command1 == command2:
        return True

    command1_parts, command2_parts = command1.split(), command2.split()

    if len(command1_parts) != len(command2_parts):
        return False

    for part1, part2 in zip(command1_parts, command2_parts):
        if part1 == part2:
            continue
        else:
            try:
                part1_int = int(part1)
                part2_int = int(part2)
                if abs(part1_int - part2_int) <= delta:
                    continue
                else:
                    return False
            except ValueError:
                return False

    return True
