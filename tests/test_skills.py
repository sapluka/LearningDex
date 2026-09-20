import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import skills


class TestSkills(unittest.TestCase):
    def test_crud(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(skills, "SKILLS_DIR", d):
                self.assertEqual(skills.list_skills(), [])
                self.assertTrue(skills.save("讲解", "内容A"))
                self.assertEqual(skills.get("讲解"), "内容A")
                self.assertEqual([s["name"] for s in skills.list_skills()], ["讲解"])
                self.assertTrue(skills.delete("讲解"))
                self.assertIsNone(skills.get("讲解"))

    def test_invalid_name(self):
        self.assertFalse(skills.save("../evil", "x"))
        self.assertIsNone(skills.get("../evil"))
        self.assertFalse(skills.delete("./a/b"))

    def test_readme_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(skills, "SKILLS_DIR", d):
                with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
                    f.write("x")
                self.assertEqual(skills.list_skills(), [])


if __name__ == "__main__":
    unittest.main()