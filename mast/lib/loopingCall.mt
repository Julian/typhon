# Copyright (C) 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

def makeLoopingCall(timer, task):
    var loopDuration :NullOk[Double] := null
    var running :Bool := false

    return object loopingCall:
        to run() :Void:
            task()
            if (running):
                when (timer.fromNow(loopDuration)) ->
                    loopingCall()

        to start(duration :Double) :Void:
            loopDuration := duration
            running := true
            loopingCall()

        to stop() :Void:
            running := false

[=> makeLoopingCall]
