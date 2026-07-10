import datetime
import uuid
import random

# Intentional internal import
from rationalevault.internal.ast_guards import whatever

class BadProjection:
    def reduce(self, event, state):
        # Intentional impurity
        now = datetime.datetime.now()
        uid = uuid.uuid4()
        r = random.random()
        with open("bad.txt", "w") as f:
            f.write(str(now))
        return state
