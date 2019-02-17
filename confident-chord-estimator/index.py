# Copyright (c) Alex Ellis 2017. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import sys
from function import handler

if __name__ == "__main__":
    st = sys.stdin.buffer.read()
    try:
        st = st.decode()
    except UnicodeDecodeError:
        pass
    ret = handler.handle(st)
    if ret != None:
        if type(ret) == 'bytes':
            sys.stdout.buffer.write(ret)
        else:
            sys.stdout.write(ret)
