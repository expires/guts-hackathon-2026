"""Record the Learn course for the iOS mock (apps/ios/Lifeline/Features/Learn/learn-mock-course.json).

Run from services/api: uv run python ../../tools/dump_learn.py ../../apps/ios/Lifeline/Features/Learn/learn-mock-course.json
"""

import json, sys
from lifeline_sim import learn
from lifeline_sim.learn_content import UNITS
out = {"units": [], "lessons": []}
for u in UNITS:
    out["units"].append({"id": u.id, "title": u.title, "description": u.description, "lesson_ids": [l.id for l in u.lessons]})
for lid in learn.lesson_ids():
    lesson = learn.build_lesson(lid, [], (), "en").model_dump(mode="json", exclude_none=True)
    res, _ = learn.grade(lid, {}, [], (), "en")
    out["lessons"].append({"lesson": lesson, "answers": [r.model_dump(mode="json") for r in res.results]})
json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, separators=(",", ":"))
print(len(out["lessons"]), sorted({l["lesson"]["summary"]["icon"] for l in out["lessons"]}))
