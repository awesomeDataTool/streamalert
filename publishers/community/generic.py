"""
Copyright 2017-present, Airbnb Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from collections import deque, OrderedDict

from stream_alert.shared.publisher import Register
from stream_alert.shared.normalize import Normalizer


@Register
def add_record(alert, publication):
    """Publisher that adds the alert.record to the publication."""
    publication['record'] = alert.record

    return publication


@Register
def blank(_, __):
    """Erases all fields on existing publications and returns a blank dict"""
    return {}


@Register
def remove_internal_fields(_, publication):
    """This publisher removes fields from DefaultPublisher that are only useful internally"""

    publication.pop('staged', None)
    publication.pop('publishers', None)
    publication.pop('outputs', None)

    return publication


@Register
def remove_streamalert_normalization(_, publication):
    """This publisher removes the super heavyweight 'streamalert:normalization' fields"""

    # Python is bad at recursion so I managed to tip toe around that with BFS using a queue.
    # This heavily takes advantage of internal references being maintained properly as the loop
    # does not actually track the "current scope" of the next_item.
    fringe = deque()
    fringe.append(publication)
    while len(fringe) > 0:
        next_item = fringe.popleft()

        if isinstance(next_item, dict):
            if Normalizer.NORMALIZATION_KEY in next_item.keys():
                next_item.pop(Normalizer.NORMALIZATION_KEY, None)

            for key, item in next_item.iteritems():
                fringe.append(item)
        elif isinstance(next_item, list):
            fringe.extend(next_item)
        else:
            # It's a leaf node, or it's some strange object that doesn't belong here
            pass

    return publication


@Register
def enumerate_fields(_, publication):
    """Flattens all currently published fields.

    By default, publications are deeply nested dict structures. This can be very hard to read
    when rendered in certain outputs. PagerDuty is one example where the default UI does a very
    poor job rendering nested dicts.

    This publisher collapses deeply nested fields into a single-leveled dict with keys that
    correspond to the original path of each value in a deeply nested dict. For example:

    {
      "top1": {
        "mid1": "low",
        "mid2": [ "low1", "low2", "low3" ],
        "mid3": {
          "low1": "verylow"
        }
      },
      "top2": "mid"
    }

    .. would collapse into the following structure:

    {
      "top1.mid1": "low",
      "top1.mid2[0]": "low1",
      "top1.mid2[1]": "low1",
      "top1.mid2[2]": "low1",
      "top1.mid3.low1: "verylow",
      "top2": "mid"
    }

    The output dict is an OrderedDict with keys sorted in alphabetical order.
    """
    def _recursive_enumerate_fields(structure, output_reference, path=''):
        if isinstance(structure, list):
            for index, item in enumerate(structure):
                _recursive_enumerate_fields(item, output_reference, '{}[{}]'.format(path, index))

        elif isinstance(structure, dict):
            for key in structure:
                _recursive_enumerate_fields(structure[key], output_reference, '{prefix}{key}'.format(
                    prefix='{}.'.format(path) if path else '',  # Omit first period
                    key=key
                ))

        else:
            output_reference[path] = structure

    output = {}
    _recursive_enumerate_fields(publication, output)

    return OrderedDict(sorted(output.items()))
